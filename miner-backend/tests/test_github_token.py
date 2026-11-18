from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests
from fastapi import HTTPException

from app.api.routes import health, repositories
from app.schemas.repositories import SearchRepositoriesRequest


def reply(status: int, body: dict | None = None) -> Mock:
    mock = Mock()
    mock.status_code = status
    mock.json.return_value = body or {}
    return mock


class ServerTokenTests(unittest.TestCase):
    def test_missing_or_blank_token_is_refused_with_a_clear_message(self) -> None:
        for value in (None, "", "   "):
            with patch.object(repositories.settings, "github_token", value):
                with self.assertRaises(HTTPException) as ctx:
                    repositories.server_github_token()
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("GITHUB_TOKEN", ctx.exception.detail)

    def test_token_comes_from_the_environment_only_and_is_trimmed(self) -> None:
        with patch.object(repositories.settings, "github_token", "  ghp_abc \n"):
            self.assertEqual(repositories.server_github_token(), "ghp_abc")

    def test_request_no_longer_accepts_a_token_from_the_browser(self) -> None:
        self.assertNotIn("github_token", SearchRepositoriesRequest.model_fields)
        payload = SearchRepositoriesRequest.model_validate(
            {"github_token": "ghp_do_navegador", "filters": [{"name": "a", "query": "mockito"}]}
        )
        self.assertNotIn("ghp_do_navegador", payload.model_dump_json())


class HealthGithubTests(unittest.TestCase):
    def test_not_configured(self) -> None:
        with patch.object(health.settings, "github_token", None):
            result = health.health_github()
        self.assertEqual((result["configured"], result["valid"]), (False, None))

    def test_valid_token_reports_code_search_quota_and_never_the_token(self) -> None:
        body = {"resources": {"code_search": {"limit": 10, "remaining": 7}}}
        with patch.object(health.settings, "github_token", "ghp_segredo"), \
             patch("requests.Session.get", return_value=reply(200, body)):
            result = health.health_github()
        self.assertEqual((result["configured"], result["valid"]), (True, True))
        self.assertEqual(result["code_search_remaining"], 7)
        self.assertNotIn("ghp_segredo", str(result))

    def test_rejected_token(self) -> None:
        with patch.object(health.settings, "github_token", "ghp_x"), \
             patch("requests.Session.get", return_value=reply(401)):
            self.assertIs(health.health_github()["valid"], False)

    def test_network_failure_is_unknown_not_invalid(self) -> None:
        with patch.object(health.settings, "github_token", "ghp_x"), \
             patch("requests.Session.get", side_effect=requests.ConnectionError("x")):
            result = health.health_github()
        self.assertEqual((result["configured"], result["valid"]), (True, None))


if __name__ == "__main__":
    unittest.main()
