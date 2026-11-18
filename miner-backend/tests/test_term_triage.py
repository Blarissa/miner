from __future__ import annotations

import unittest
from unittest.mock import patch

from app.schemas.repository_models import RepoCandidate
from app.services.filters import ContentRule, GitHubSearchFilter, GitHubSearchType
from app.services.miner import (
    analyze_candidate,
    candidate_from_search_item,
    merge_candidate_metadata,
    triage_term_matches,
)
from app.services.term_triage import confirm_evidence, strip_java_noise

POM = """<project>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-jdbc</artifactId>
    </dependency>
  </dependencies>
</project>"""


class JavaEvidenceTests(unittest.TestCase):
    def test_real_usage_is_confirmed(self) -> None:
        source = "import org.springframework.jdbc.core.JdbcTemplate;\nclass A { JdbcTemplate t; }"
        self.assertTrue(confirm_evidence("codigo", "JdbcTemplate", source).confirmed)
        self.assertEqual(confirm_evidence("import", "org.springframework.jdbc.core.JdbcTemplate", source).reason, "import")

    def test_comment_and_string_do_not_count(self) -> None:
        source = '// migrar de JdbcTemplate para JPA\n/* JdbcTemplate */\nclass A { String s = "JdbcTemplate"; }'
        result = confirm_evidence("codigo", "JdbcTemplate", source)
        self.assertFalse(result.confirmed)
        self.assertEqual(result.reason, "apenas_comentario_ou_texto")

    def test_url_in_string_does_not_hide_code_after_it(self) -> None:
        source = 'class A { String u = "http://x"; JdbcTemplate t; }'
        self.assertTrue(confirm_evidence("codigo", "JdbcTemplate", source).confirmed)

    def test_text_block_and_escaped_quote_are_stripped(self) -> None:
        source = 'class A { String a = "x\\"JdbcTemplate"; String b = """\n JdbcTemplate\n"""; }'
        self.assertNotIn("JdbcTemplate", strip_java_noise(source))

    def test_import_does_not_match_a_longer_class_name(self) -> None:
        source = "import org.mockito.MockitoAnnotations;"
        self.assertFalse(confirm_evidence("import", "org.mockito.Mock", source).confirmed)

    def test_wildcard_import_needs_the_class_to_be_used(self) -> None:
        text = "org.springframework.jdbc.core.JdbcTemplate"
        used = "import org.springframework.jdbc.core.*;\nclass A { JdbcTemplate t; }"
        unused = "import org.springframework.jdbc.core.*;\nclass A { }"
        self.assertTrue(confirm_evidence("import", text, used).confirmed)
        self.assertFalse(confirm_evidence("import", text, unused).confirmed)

    def test_absent_term(self) -> None:
        self.assertEqual(confirm_evidence("codigo", "Foo", "class A {}").reason, "termo_ausente_no_arquivo")


class DependencyEvidenceTests(unittest.TestCase):
    def test_declared_dependency_is_confirmed(self) -> None:
        self.assertTrue(confirm_evidence("dependencia", "spring-boot-starter-jdbc", POM).confirmed)

    def test_commented_dependency_does_not_count(self) -> None:
        pom = "<project><!-- <dependency><artifactId>spring-jdbc</artifactId></dependency> --></project>"
        self.assertFalse(confirm_evidence("dependencia", "spring-jdbc", pom).confirmed)

    def test_exclusion_and_management_do_not_count(self) -> None:
        excluded = """<dependencies><dependency><artifactId>web</artifactId>
            <exclusions><exclusion><artifactId>spring-jdbc</artifactId></exclusion></exclusions>
            </dependency></dependencies>"""
        managed = """<dependencyManagement><dependencies><dependency>
            <artifactId>spring-jdbc</artifactId></dependency></dependencies></dependencyManagement>"""
        self.assertEqual(confirm_evidence("dependencia", "spring-jdbc", excluded).reason, "dependencia_nao_efetiva")
        self.assertFalse(confirm_evidence("dependencia", "spring-jdbc", managed).confirmed)

    def test_projects_own_artifact_id_does_not_count(self) -> None:
        pom = "<project><artifactId>spring-jdbc</artifactId></project>"
        self.assertFalse(confirm_evidence("dependencia", "spring-jdbc", pom).confirmed)


def term_filter(evidence: str, text: str, name: str = "termo-1") -> GitHubSearchFilter:
    return GitHubSearchFilter(
        name=name, search_type=GitHubSearchType.CODE, query=f'"{text}"',
        term_evidence=evidence, term_text=text,
    )


def code_item(path: str) -> dict:
    return {
        "path": path,
        "html_url": f"https://github.com/o/r/blob/main/{path}",
        "repository": {"full_name": "o/r", "html_url": "https://github.com/o/r", "default_branch": "main"},
    }


class TriageFlowTests(unittest.TestCase):
    def test_match_carries_the_evidence_of_its_filter(self) -> None:
        candidate = candidate_from_search_item(code_item("A.java"), term_filter("codigo", "JdbcTemplate"))
        match = candidate.raw["_matches"][0]
        self.assertEqual((match["term_evidence"], match["term_text"]), ("codigo", "JdbcTemplate"))

    def test_merge_keeps_two_evidences_for_the_same_file(self) -> None:
        first = candidate_from_search_item(code_item("A.java"), term_filter("codigo", "Spring Batch", "t1"))
        second = candidate_from_search_item(code_item("A.java"), term_filter("codigo", "SpringBatch", "t2"))
        merge_candidate_metadata(first, second)
        self.assertEqual({m["term_text"] for m in first.raw["_matches"]}, {"Spring Batch", "SpringBatch"})

    def test_advanced_mode_has_nothing_to_triage(self) -> None:
        plain = GitHubSearchFilter(name="x", search_type=GitHubSearchType.CODE, query="mockito")
        candidate = candidate_from_search_item(code_item("A.java"), plain)
        self.assertIsNone(triage_term_matches(None, candidate, 0))  # type: ignore[arg-type]

    def test_second_match_can_confirm_when_first_is_only_a_comment(self) -> None:
        candidate = candidate_from_search_item(code_item("Doc.java"), term_filter("codigo", "JdbcTemplate", "t1"))
        other = candidate_from_search_item(code_item("Repo.java"), term_filter("codigo", "JdbcTemplate", "t2"))
        merge_candidate_metadata(candidate, other)
        files = {"Doc.java": "// JdbcTemplate\nclass Doc {}", "Repo.java": "class Repo { JdbcTemplate t; }"}
        with patch("app.services.miner.fetch_file_content", side_effect=lambda s, n, p, d: files[p]):
            triage = triage_term_matches(None, candidate, 0)  # type: ignore[arg-type]
        assert triage is not None
        self.assertTrue(triage.confirmed)
        self.assertEqual(triage.path, "Repo.java")

    def test_unconfirmed_candidate_is_rejected_before_any_pom_or_clone_work(self) -> None:
        search_filter = term_filter("codigo", "JdbcTemplate")
        candidate = candidate_from_search_item(code_item("Doc.java"), search_filter)
        calls: list[str] = []

        def fake_fetch(session, name, path, delay):
            calls.append(path)
            return "// JdbcTemplate\nclass Doc {}"

        with patch("app.services.miner.fetch_file_content", side_effect=fake_fetch):
            result = analyze_candidate(None, candidate, search_filter, 0)  # type: ignore[arg-type]
        self.assertIsNone(result)
        self.assertEqual(calls, ["Doc.java"])  # nem chegou a procurar o pom.xml

    def test_confirmed_java_match_applies_java_version_rule_to_the_pom(self) -> None:
        rule = ContentRule("java_version", [r"<java\.version>\s*17\s*</java\.version>"], True, "17")
        search_filter = term_filter("codigo", "JdbcTemplate")
        search_filter.content_rules = [rule]
        files = {
            "src/A.java": "class A { JdbcTemplate t; }",
            "pom.xml": "<project><properties><java.version>11</java.version></properties></project>",
        }
        candidate = candidate_from_search_item(code_item("src/A.java"), search_filter)
        with patch("app.services.miner.fetch_file_content", side_effect=lambda s, n, p, d: files.get(p)):
            self.assertIsNone(analyze_candidate(None, candidate, search_filter, 0))  # type: ignore[arg-type]

            files["pom.xml"] = "<project><properties><java.version>17</java.version></properties></project>"
            candidate = candidate_from_search_item(code_item("src/A.java"), search_filter)
            with patch("app.services.miner.fetch_ref_commit_sha", return_value="abc123"):
                repo = analyze_candidate(None, candidate, search_filter, 0)  # type: ignore[arg-type]
        assert repo is not None
        self.assertEqual(repo.metadata["term_evidence"], "codigo")
        self.assertEqual(repo.metadata["term_confirmation"], "uso_no_codigo")
        self.assertEqual(repo.metadata["java_version"], "17")


if __name__ == "__main__":
    unittest.main()


class ResumeKeepsTermFiltersTests(unittest.TestCase):
    def test_file_size_and_term_evidence_survive_resume(self) -> None:
        import tempfile
        from pathlib import Path

        from app.api.routes.repositories import payload_from_saved_run
        from app.core import database
        from app.schemas.repositories import SearchRepositoriesRequest
        from app.services.filters import filters_from_payload
        from app.services.persistence import (
            create_mining_run,
            get_mining_run,
            get_search_filters_for_run,
            save_search_filters,
        )

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            original_path = database.DATABASE_PATH
            database.DATABASE_PATH = Path(tmp) / "miner.db"
            try:
                payload = SearchRepositoriesRequest(term="mockito", term_coverage="ampla")
                built = filters_from_payload(payload.model_dump())
                run_id = create_mining_run(payload, status="queued")
                save_search_filters(run_id, payload.filters, built)

                saved = get_search_filters_for_run(run_id)
                resumed = payload_from_saved_run(get_mining_run(run_id), saved)  # type: ignore[arg-type]
                rebuilt = filters_from_payload(resumed.model_dump())

                self.assertEqual([f.query for f in rebuilt], [f.query for f in built])
                self.assertTrue(any("size:<1500" in f.query for f in rebuilt))
                self.assertTrue(all(f.term_evidence and f.term_text for f in rebuilt))
            finally:
                database.DATABASE_PATH = original_path
