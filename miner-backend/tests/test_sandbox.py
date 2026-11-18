from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import analyzer, sandbox


class EnvTests(unittest.TestCase):
    def test_secrets_are_removed_and_normal_vars_kept(self) -> None:
        env = {
            "PATH": "/usr/bin", "JAVA_HOME": "/opt/jdks/17", "HOME": "/x",
            "GITHUB_TOKEN": "t", "GH_TOKEN": "t", "DATABASE_URL": "sqlite:///x", "AWS_SECRET_ACCESS_KEY": "s",
            "DB_PASSWORD": "p", "OPENAI_API_KEY": "k", "GIT_ASKPASS": "/x", "MY_PRIVATE_KEY": "k", "GPG_KEY": "pub",
        }
        safe = sandbox.scrub_env(env)
        self.assertEqual(set(safe), {"PATH", "JAVA_HOME", "HOME", "GPG_KEY"})

    def test_prepare_env_blocks_non_https_git_protocols_and_prompts(self) -> None:
        safe = sandbox.prepare_env({"PATH": "/usr/bin", "GITHUB_TOKEN": "t"})
        self.assertEqual(safe["GIT_ALLOW_PROTOCOL"], "https")
        self.assertEqual(safe["GIT_TERMINAL_PROMPT"], "0")
        self.assertNotIn("GITHUB_TOKEN", safe)


class WrapCommandTests(unittest.TestCase):
    def test_command_runs_as_sandbox_user_without_secrets_or_privileges(self) -> None:
        with patch.dict(os.environ, {"MINER_SANDBOX_USER": "sandbox"}):
            command = sandbox.wrap_command(
                ["mvn", "test"], {"PATH": "/usr/bin", "JAVA_HOME": "/j", "GITHUB_TOKEN": "segredo"}, 300
            )
        joined = " ".join(command)
        self.assertEqual(command[:7], ["sudo", "-n", "-H", "-u", "sandbox", "--", "env"])
        self.assertIn("-i", command)
        self.assertIn("HOME=/home/sandbox", command)
        self.assertIn("JAVA_HOME=/j", command)
        self.assertNotIn("segredo", joined)
        self.assertNotIn("GITHUB_TOKEN", joined)
        self.assertEqual(command[command.index("timeout") + 1:command.index("timeout") + 4], ["-k", "10", "300"])
        self.assertEqual(command[-5:], ["setpriv", "--no-new-privs", "--", "mvn", "test"][-5:])
        self.assertLess(command.index("setpriv"), command.index("mvn"))

    def test_launcher_env_carries_only_path(self) -> None:
        with patch.dict(os.environ, {"PATH": "/usr/bin", "GITHUB_TOKEN": "t"}):
            self.assertEqual(sandbox.launcher_env(), {"PATH": "/usr/bin"})


class ModeTests(unittest.TestCase):
    def setUp(self) -> None:
        sandbox._probe.cache_clear()
        sandbox._warn_once.cache_clear()

    def tearDown(self) -> None:
        sandbox._probe.cache_clear()

    def test_without_user_it_is_inactive_and_silent_in_auto_mode(self) -> None:
        with patch.dict(os.environ, {"MINER_SANDBOX": "auto"}, clear=False):
            os.environ.pop("MINER_SANDBOX_USER", None)
            self.assertFalse(sandbox.is_active())
            self.assertFalse(sandbox.status()["active"])

    def test_required_mode_fails_closed_when_probe_fails(self) -> None:
        with patch.dict(os.environ, {"MINER_SANDBOX": "required", "MINER_SANDBOX_USER": "sandbox"}), \
             patch("app.services.sandbox._probe", return_value=(False, "sudo não encontrado")):
            with self.assertRaises(sandbox.SandboxUnavailable):
                sandbox.is_active()
            ok, message = analyzer.run(["echo", "oi"], Path("."), {}, 5)
        self.assertFalse(ok)
        self.assertIn("Sandbox obrigatório indisponível", message)

    def test_auto_mode_falls_back_and_warns_when_probe_fails(self) -> None:
        with patch.dict(os.environ, {"MINER_SANDBOX": "auto", "MINER_SANDBOX_USER": "sandbox"}), \
             patch("app.services.sandbox._probe", return_value=(False, "falhou")), \
             self.assertLogs("sandbox", level="WARNING") as logs:
            self.assertFalse(sandbox.is_active())
        self.assertIn("SANDBOX DESLIGADO", logs.output[0])

    def test_off_mode_never_probes(self) -> None:
        with patch.dict(os.environ, {"MINER_SANDBOX": "off", "MINER_SANDBOX_USER": "sandbox"}), \
             patch("app.services.sandbox._probe") as probe:
            self.assertFalse(sandbox.is_active())
        probe.assert_not_called()

    def test_active_probe_enables_the_sandbox(self) -> None:
        with patch.dict(os.environ, {"MINER_SANDBOX": "auto", "MINER_SANDBOX_USER": "sandbox"}), \
             patch("app.services.sandbox._probe", return_value=(True, "ok")):
            self.assertTrue(sandbox.is_active())


class RunIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        sandbox._probe.cache_clear()

    def test_run_scrubs_secrets_even_without_sandbox(self) -> None:
        with patch.dict(os.environ, {"MINER_SANDBOX": "off"}):
            ok, out = analyzer.run(
                ["sh", "-c", "echo token=[$GITHUB_TOKEN] path_set=[${PATH:+yes}]"],
                Path("."), {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "GITHUB_TOKEN": "segredo"}, 10,
            )
        self.assertTrue(ok)
        self.assertIn("token=[]", out)
        self.assertNotIn("segredo", out)

    def test_run_uses_sudo_wrapper_when_active(self) -> None:
        captured: dict = {}

        class FakeProc:
            returncode = 0
            stdout = iter(["ok\n"])

            def poll(self) -> int:
                return 0

        def fake_popen(command, **kwargs):
            captured["command"] = command
            captured["env"] = kwargs["env"]
            return FakeProc()

        with patch.dict(os.environ, {"MINER_SANDBOX": "auto", "MINER_SANDBOX_USER": "sandbox"}), \
             patch("app.services.sandbox._probe", return_value=(True, "ok")), \
             patch("app.services.analyzer.subprocess.Popen", side_effect=fake_popen):
            ok, _ = analyzer.run(["mvn", "test"], Path("."), {"PATH": "/usr/bin", "GITHUB_TOKEN": "segredo"}, 100)
        self.assertTrue(ok)
        self.assertEqual(captured["command"][0], "sudo")
        self.assertNotIn("segredo", " ".join(captured["command"]))
        self.assertEqual(set(captured["env"]), {"PATH"})
        self.assertEqual(captured["command"][captured["command"].index("timeout") + 3], "98")

    def test_sandbox_timeout_exit_code_is_reported_as_timeout(self) -> None:
        class FakeProc:
            returncode = 124
            stdout = iter([])

            def poll(self) -> int:
                return 124

        with patch.dict(os.environ, {"MINER_SANDBOX": "auto", "MINER_SANDBOX_USER": "sandbox"}), \
             patch("app.services.sandbox._probe", return_value=(True, "ok")), \
             patch("app.services.analyzer.subprocess.Popen", return_value=FakeProc()):
            ok, out = analyzer.run(["mvn", "test"], Path("."), {"PATH": "/usr/bin"}, 100)
        self.assertFalse(ok)
        self.assertIn("Timeout apos", out)

    def test_mvnw_is_called_through_sh_when_sandbox_is_on(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "mvnw").write_text("#!/bin/sh\n")
            with patch("app.services.analyzer._sandbox_on", return_value=True):
                self.assertEqual(analyzer.mvn_cmd(project, ["test"])[:2], ["sh", str(project / "mvnw")])
            with patch("app.services.analyzer._sandbox_on", return_value=False):
                self.assertEqual(analyzer.mvn_cmd(project, ["test"])[0], str(project / "mvnw"))


class RemoveTreeTests(unittest.TestCase):
    def test_refuses_paths_outside_the_base(self) -> None:
        with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as other:
            with self.assertRaises(ValueError):
                sandbox.remove_tree(Path(other), Path(base))
            with self.assertRaises(ValueError):
                sandbox.remove_tree(Path(base), Path(base))  # nem a própria base

    def test_removes_directory_when_sandbox_is_off(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            target = Path(base) / "repo"
            (target / "sub").mkdir(parents=True)
            (target / "sub" / "a.txt").write_text("x")
            with patch.dict(os.environ, {"MINER_SANDBOX": "off"}):
                self.assertTrue(sandbox.remove_tree(target, Path(base)))
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
