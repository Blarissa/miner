from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.api.routes.repositories import (
    calculate_acceptance_rate,
    calculate_analyzer_batch_size,
    payload_from_saved_run,
)
from app.core import database
from app.schemas.repositories import ContentRuleRequest, GitHubSearchFilterRequest, MinedRepo, SearchRepositoriesRequest
from app.services.filters import filters_from_payload
from app.services.filters import ContentRule, GitHubSearchFilter, GitHubSearchType
from app.services.miner import (
    analyze_candidate,
    analyze_mined_repositories,
    candidate_matches_metadata_filter,
    content_has_spring_import,
    enrich_candidate_metadata,
    pom_indicates_spring,
    safe_get,
)
from app.services.analyzer import detect_test_framework_from_pom, resolve_jdk, scan_project_structure
from app.schemas.repositories import RepoCandidate
from app.services.persistence import (
    cancel_mining_run,
    create_mining_run,
    get_analysis_cache,
    get_mining_run,
    get_search_filters_for_run,
    is_mining_run_cancelled,
    persist_search_results,
    save_search_filters,
)
from app.services.mining_runner import (
    cached_results_fill_remaining_slots,
    split_analyzable_repositories,
    should_stop_unproductive_search,
    unproductive_rejection_limit,
)


class PipelineControlsTest(unittest.TestCase):
    def test_code_search_keeps_repository_language_out_of_query(self) -> None:
        filters = filters_from_payload(
            {
                "filters": [
                    {
                        "name": "code-filter",
                        "search_type": "code",
                        "query": "junit mockito",
                        "language": "Java",
                        "stars": ">=100",
                        "forks": "50",
                        "filename": "pom.xml",
                        "extension": "xml",
                    }
                ]
            }
        )

        search_filter = filters[0]

        self.assertEqual(search_filter.query, "junit mockito filename:pom.xml extension:xml")
        self.assertEqual(search_filter.language, "Java")
        self.assertEqual(search_filter.stars, ">=100")
        self.assertEqual(search_filter.forks, "50")

    def test_multi_query_filter_expands_same_options_per_query(self) -> None:
        payload = SearchRepositoriesRequest(
            filters=[
                GitHubSearchFilterRequest(
                    name="code-filter",
                    search_type="code",
                    query="mockito",
                    queries=["junit"],
                    language="Java",
                    stars=">=100",
                    filename="pom.xml",
                    extension="xml",
                )
            ]
        )

        filters = filters_from_payload(payload.model_dump())

        self.assertEqual(len(payload.filters), 2)
        self.assertEqual(len(filters), 2)
        self.assertEqual(filters[0].name, "code-filter-1")
        self.assertEqual(filters[0].query, "mockito filename:pom.xml extension:xml")
        self.assertEqual(filters[1].name, "code-filter-2")
        self.assertEqual(filters[1].query, "junit filename:pom.xml extension:xml")
        self.assertEqual(filters[0].language, "Java")
        self.assertEqual(filters[1].language, "Java")
        self.assertEqual(filters[0].stars, ">=100")
        self.assertEqual(filters[1].stars, ">=100")

    def test_code_search_repository_metadata_filter(self) -> None:
        search_filter = GitHubSearchFilter(
            name="code-filter",
            search_type=GitHubSearchType.CODE,
            query="junit mockito filename:pom.xml extension:xml",
            language="Java",
            stars=">=100",
            forks="50",
        )
        accepted_candidate = RepoCandidate(
            full_name="owner/repository",
            html_url="https://github.com/owner/repository",
            source_filter="code-filter",
            language="Java",
            stars=120,
            forks=50,
        )
        rejected_candidate = RepoCandidate(
            full_name="owner/other",
            html_url="https://github.com/owner/other",
            source_filter="code-filter",
            language="Java",
            stars=99,
            forks=50,
        )

        self.assertTrue(candidate_matches_metadata_filter(accepted_candidate, search_filter))
        self.assertFalse(candidate_matches_metadata_filter(rejected_candidate, search_filter))

    def test_code_search_candidate_metadata_is_enriched_before_filtering(self) -> None:
        search_filter = GitHubSearchFilter(
            name="code-filter",
            search_type=GitHubSearchType.CODE,
            query="junit mockito filename:pom.xml extension:xml",
            language="Java",
            stars=">=100",
            forks="50",
        )
        candidate = RepoCandidate(
            full_name="owner/repository",
            html_url="https://github.com/owner/repository",
            source_filter="code-filter",
            raw={
                "_matched_path": "pom.xml",
                "_matched_file_url": "https://github.com/owner/repository/blob/main/pom.xml",
                "_matches": [
                    {
                        "path": "pom.xml",
                        "html_url": "https://github.com/owner/repository/blob/main/pom.xml",
                        "source_filter": "code-filter",
                    }
                ],
            },
        )
        session = Mock()
        repository_metadata = {
            "full_name": "owner/repository",
            "html_url": "https://github.com/owner/repository",
            "language": "Java",
            "stargazers_count": 120,
            "forks_count": 50,
            "private": False,
            "fork": False,
            "archived": False,
        }

        with patch("app.services.miner.fetch_repository_metadata", return_value=repository_metadata):
            enriched = enrich_candidate_metadata(session, candidate, search_filter, delay=0)

        self.assertTrue(candidate_matches_metadata_filter(enriched, search_filter))
        self.assertEqual(enriched.raw["_matched_path"], "pom.xml")

    def test_rejected_content_does_not_fetch_commit_sha(self) -> None:
        candidate = RepoCandidate(
            full_name="owner/repository",
            html_url="https://github.com/owner/repository",
            source_filter="content-filter",
            raw={"default_branch": "main"},
        )
        search_filter = GitHubSearchFilter(
            name="content-filter",
            search_type=GitHubSearchType.CODE,
            query="pom.xml",
            file_path="pom.xml",
            content_rules=[
                ContentRule(
                    field_name="java_version",
                    patterns=[r"<java\.version>(\d+)</java\.version>"],
                    required=True,
                )
            ],
        )
        session = Mock()

        with patch("app.services.miner.fetch_file_content", return_value="<project />"):
            with patch("app.services.miner.fetch_ref_commit_sha") as fetch_commit:
                result = analyze_candidate(session, candidate, search_filter, delay=0)

        self.assertIsNone(result)
        fetch_commit.assert_not_called()

    def test_candidate_does_not_require_spring_pom_or_main_java_import(self) -> None:
        candidate = RepoCandidate(
            full_name="owner/maven-app",
            html_url="https://github.com/owner/maven-app",
            source_filter="maven-filter",
            language="Java",
            stars=42,
            raw={
                "default_branch": "main",
                "pushed_at": "2026-09-10T12:00:00Z",
                "license": {"key": "mit", "name": "MIT License"},
            },
        )
        search_filter = GitHubSearchFilter(
            name="maven-filter",
            search_type=GitHubSearchType.CODE,
            query="mockito filename:pom.xml",
            file_path="pom.xml",
        )
        pom = """
            <project>
              <dependencies>
                <dependency>
                  <groupId>org.mockito</groupId>
                  <artifactId>mockito-core</artifactId>
                </dependency>
              </dependencies>
              <properties><java.version>17</java.version></properties>
            </project>
        """

        def file_content(_session: Mock, _full_name: str, path: str, _delay: float) -> str | None:
            if path == "pom.xml":
                return pom
            return None

        with patch("app.services.miner.fetch_file_content", side_effect=file_content):
            with patch("app.services.miner.fetch_directory_items") as fetch_directory_items:
                with patch("app.services.miner.fetch_ref_commit_sha", return_value="abc123"):
                    result = analyze_candidate(Mock(), candidate, search_filter, delay=0)

        self.assertIsNotNone(result)
        assert result is not None
        fetch_directory_items.assert_not_called()
        self.assertEqual(result.commit_sha, "abc123")
        self.assertEqual(result.metadata["default_branch"], "main")
        self.assertEqual(result.metadata["commit_sha"], "abc123")
        self.assertEqual(result.metadata["license"], "mit")
        self.assertEqual(result.metadata["stars"], 42)
        self.assertEqual(result.metadata["pushed_at"], "10/09/2026")

    def test_candidate_without_main_java_spring_import_is_not_rejected_before_commit_lookup(self) -> None:
        candidate = RepoCandidate(
            full_name="owner/not-used",
            html_url="https://github.com/owner/not-used",
            source_filter="maven-filter",
            raw={"default_branch": "main"},
        )
        search_filter = GitHubSearchFilter(
            name="maven-filter",
            search_type=GitHubSearchType.CODE,
            query="mockito filename:pom.xml",
            file_path="pom.xml",
        )
        pom = "<project><properties><java.version>17</java.version></properties></project>"

        with patch("app.services.miner.fetch_file_content", return_value=pom):
            with patch("app.services.miner.fetch_directory_items") as fetch_directory_items:
                with patch("app.services.miner.fetch_ref_commit_sha") as fetch_commit:
                    fetch_commit.return_value = "abc123"
                    result = analyze_candidate(Mock(), candidate, search_filter, delay=0)

        self.assertIsNotNone(result)
        fetch_directory_items.assert_not_called()
        fetch_commit.assert_called_once()

    def test_spring_detection_helpers(self) -> None:
        self.assertTrue(pom_indicates_spring("<artifactId>spring-boot-starter</artifactId>"))
        self.assertTrue(content_has_spring_import("import org.springframework.context.ApplicationContext;"))
        self.assertFalse(content_has_spring_import("import com.example.SpringLike;"))

    def test_safe_get_does_not_sleep_before_successful_request(self) -> None:
        response = Mock(status_code=200)
        response.headers = {}
        response.text = ""
        response.url = "https://api.github.com/test"
        session = Mock()
        session.headers = {"Authorization": "Bearer test-token"}
        session.get.return_value = response

        with patch("app.services.miner.time.sleep") as sleep:
            self.assertIs(safe_get(session, "https://api.github.com/test"), response)

        sleep.assert_not_called()

    def test_batch_size_is_decided_by_max_repos(self) -> None:
        self.assertEqual(calculate_analyzer_batch_size(1, 4), 10)
        self.assertEqual(calculate_analyzer_batch_size(4, 4), 12)
        self.assertEqual(calculate_analyzer_batch_size(10, 4), 30)
        self.assertEqual(calculate_analyzer_batch_size(20, 4), 40)
        self.assertEqual(calculate_analyzer_batch_size(50, 4), 50)
        self.assertEqual(calculate_analyzer_batch_size(100, 4), 50)

    def test_acceptance_rate_is_smoothed(self) -> None:
        rate = calculate_acceptance_rate(
            accepted_count=3,
            rejected_count=7,
            previous_rate=0.25,
        )

        self.assertAlmostEqual(rate, 0.265)

    def test_unproductive_search_stops_after_rejection_limit(self) -> None:
        limit = unproductive_rejection_limit(max_repos=4)

        self.assertFalse(should_stop_unproductive_search(0, limit - 1, 4))
        self.assertTrue(should_stop_unproductive_search(0, limit, 4))
        self.assertFalse(should_stop_unproductive_search(1, limit, 4))

    def test_cached_results_only_skip_pending_analysis_when_they_fill_remaining_slots(self) -> None:
        payload = SearchRepositoriesRequest(
            max_repos=2,
            require_buildable=True,
            filters=[
                GitHubSearchFilterRequest(
                    name="cache-filter",
                    search_type="repositories",
                    query="language:java",
                )
            ],
        )
        accepted_cached = {
            "compiled": True,
            "has_tests": False,
            "tests_passed": False,
            "eliminated": False,
        }
        eliminated_cached = {
            "compiled": False,
            "has_tests": False,
            "tests_passed": False,
            "eliminated": True,
        }

        self.assertTrue(
            cached_results_fill_remaining_slots(
                [accepted_cached],
                accepted_count=1,
                payload=payload,
            )
        )
        self.assertFalse(
            cached_results_fill_remaining_slots(
                [eliminated_cached],
                accepted_count=1,
                payload=payload,
            )
        )

    def test_invalid_java_version_is_rejected_before_analyzer(self) -> None:
        valid = MinedRepo(
            repo_name="owner/valid",
            repo_url="https://github.com/owner/valid",
            matched_filter="java",
            metadata={"java_version": "1.8"},
            commit_sha="abc",
        )
        invalid = MinedRepo(
            repo_name="owner/invalid",
            repo_url="https://github.com/owner/invalid",
            matched_filter="java",
            metadata={},
            commit_sha="def",
        )

        analyzable, rejected = split_analyzable_repositories([valid, invalid])

        self.assertEqual(analyzable, [valid])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["repo_name"], "owner/invalid")
        self.assertEqual(rejected[0]["error_stage"], "java_version_filter")

    def test_jdk_resolution_uses_selected_version_without_upgrade(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            jdk8 = tmp_path / "jdk8"
            jdk8.mkdir()

            with patch("app.services.analyzer.JDK_MAP", {"7": tmp_path / "jdk7", "8": jdk8}):
                path, version = resolve_jdk("7")

        self.assertIsNone(path)
        self.assertEqual(version, "7")

    def test_jdk_resolution_can_upgrade_when_user_allows_it(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            tmp_path = Path(tmp)
            jdk8 = tmp_path / "jdk8"
            jdk8.mkdir()

            with patch("app.services.analyzer.JDK_MAP", {"7": tmp_path / "jdk7", "8": jdk8}):
                with patch("app.services.analyzer.VERSIONS_ASC", ["7", "8"]):
                    path, version = resolve_jdk("7", allow_jdk_upgrade=True)

        self.assertEqual(path, jdk8)
        self.assertEqual(version, "8")

    def test_tests_are_detected_only_under_src_test_java(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            project = Path(tmp)
            (project / "pom.xml").write_text(
                "<project><dependency><artifactId>junit</artifactId></dependency></project>",
                encoding="utf-8",
            )
            (project / "src" / "main" / "java").mkdir(parents=True)
            (project / "src" / "main" / "java" / "AppTest.java").write_text(
                "class AppTest {}",
                encoding="utf-8",
            )

            self.assertFalse(scan_project_structure(project).has_tests)

            (project / "src" / "test" / "java").mkdir(parents=True)
            (project / "src" / "test" / "java" / "AppTest.java").write_text(
                "class AppTest {}",
                encoding="utf-8",
            )

            self.assertTrue(scan_project_structure(project).has_tests)

    def test_test_framework_is_detected_from_pom_dependencies(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            pom = Path(tmp) / "pom.xml"
            pom.write_text(
                """
                <project>
                  <dependencies>
                    <dependency>
                      <groupId>org.mockito</groupId>
                      <artifactId>mockito-junit-jupiter</artifactId>
                    </dependency>
                    <dependency>
                      <groupId>org.testng</groupId>
                      <artifactId>testng</artifactId>
                    </dependency>
                    <dependency>
                      <groupId>org.junit.jupiter</groupId>
                      <artifactId>junit-jupiter-api</artifactId>
                    </dependency>
                  </dependencies>
                </project>
                """,
                encoding="utf-8",
            )

            self.assertEqual(detect_test_framework_from_pom(pom), "Mockito, TestNG, JUnit")

    def test_unknown_test_framework_returns_empty_text(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            pom = Path(tmp) / "pom.xml"
            pom.write_text("<project><dependencies /></project>", encoding="utf-8")

            self.assertEqual(detect_test_framework_from_pom(pom), "")

    def test_eliminated_analysis_is_cached_even_when_not_persisted_in_run(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            original_path = database.DATABASE_PATH
            database.DATABASE_PATH = Path(tmp) / "miner.db"
            try:
                payload = SearchRepositoriesRequest(
                    max_repos=1,
                    persist_eliminated_repositories=False,
                    filters=[
                        GitHubSearchFilterRequest(
                            name="cache-filter",
                            search_type="code",
                            query="junit",
                            filename="pom.xml",
                            extension="xml",
                        )
                    ],
                )
                built_filters = filters_from_payload(payload.model_dump())
                run_id = create_mining_run(payload, status="running")
                repo = {
                    "repo_name": "owner/rejected",
                    "repo_url": "https://github.com/owner/rejected",
                    "matched_filter": "cache-filter",
                    "metadata": {"java_version": "17"},
                    "commit_sha": "abc123",
                    "java_version": "17",
                    "effective_java_version": "17",
                    "build": "Maven",
                    "test_framework": "JUnit",
                    "compiled": False,
                    "has_tests": False,
                    "tests_passed": False,
                    "eliminated": True,
                    "error_stage": "jdk_resolution",
                    "error_message": "JDK indisponivel",
                }

                persist_search_results(
                    run_id=run_id,
                    payload=payload,
                    raw_filters=payload.filters,
                    built_filters=built_filters,
                    repositories=[repo],
                    statistics=None,
                    run_test_suite=True,
                )

                cached = get_analysis_cache("owner/rejected", "abc123", True)

                self.assertIsNotNone(cached)
                self.assertEqual(cached["error_stage"], "jdk_resolution")  # type: ignore[index]
                self.assertTrue(cached["eliminated"])  # type: ignore[index]
            finally:
                database.DATABASE_PATH = original_path

    def test_existing_repository_analysis_is_reused_without_commit_sha(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            original_path = database.DATABASE_PATH
            database.DATABASE_PATH = Path(tmp) / "miner.db"
            try:
                payload = SearchRepositoriesRequest(
                    max_repos=1,
                    persist_eliminated_repositories=False,
                    filters=[
                        GitHubSearchFilterRequest(
                            name="cache-filter",
                            search_type="repositories",
                            query="language:java",
                        )
                    ],
                )
                built_filters = filters_from_payload(payload.model_dump())
                run_id = create_mining_run(payload, status="running")
                repo = {
                    "repo_name": "owner/cached",
                    "repo_url": "https://github.com/owner/cached",
                    "matched_filter": "cache-filter",
                    "metadata": {"java_version": "17"},
                    "commit_sha": "abc123",
                    "java_version": "17",
                    "effective_java_version": "17",
                    "build": "Maven",
                    "test_framework": "JUnit",
                    "compiled": True,
                    "has_tests": True,
                    "tests_passed": True,
                    "eliminated": False,
                }
                persist_search_results(
                    run_id=run_id,
                    payload=payload,
                    raw_filters=payload.filters,
                    built_filters=built_filters,
                    repositories=[repo],
                    statistics=None,
                    run_test_suite=True,
                )
                mined_repo = MinedRepo(
                    repo_name="owner/cached",
                    repo_url="https://github.com/owner/cached",
                    matched_filter="new-search",
                    metadata={"java_version": "17"},
                    commit_sha=None,
                )

                with patch("app.services.analyzer.analyze_project") as analyze_project:
                    results = analyze_mined_repositories([mined_repo], run_test_suite=True)

                analyze_project.assert_not_called()
                self.assertEqual(len(results), 1)
                self.assertTrue(results[0]["cache_hit"])
                self.assertEqual(results[0]["commit_sha"], "abc123")
                self.assertTrue(results[0]["tests_passed"])
                self.assertEqual(results[0]["matched_filter"], "new-search")
            finally:
                database.DATABASE_PATH = original_path

    def test_saved_run_preserves_analyze_and_filters_for_resume(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            original_path = database.DATABASE_PATH
            database.DATABASE_PATH = Path(tmp) / "miner.db"
            try:
                payload = SearchRepositoriesRequest(
                    max_repos=4,
                    max_workers=2,
                    analyzer_workers=2,
                    delay=0,
                    analyze=True,
                    require_buildable=True,
                    require_tests_passed=False,
                    include_statistics=True,
                    statistics_scope="all",
                    filters=[
                        GitHubSearchFilterRequest(
                            name="resume-filter",
                            search_type="code",
                            query="mockito",
                            filename="pom.xml",
                            extension="xml",
                            file_path="pom.xml",
                            content_rules=[
                                ContentRuleRequest(
                                    field_name="java_version",
                                    patterns=[r"<java\.version>(\d+)</java\.version>"],
                                )
                            ],
                        )
                    ],
                )
                built_filters = filters_from_payload(payload.model_dump())

                run_id = create_mining_run(payload, status="queued")
                save_search_filters(run_id, payload.filters, built_filters)

                run = get_mining_run(run_id)
                saved_filters = get_search_filters_for_run(run_id)
                resumed_payload = payload_from_saved_run(run, saved_filters)  # type: ignore[arg-type]

                self.assertTrue(resumed_payload.analyze)
                self.assertTrue(resumed_payload.require_buildable)
                self.assertFalse(resumed_payload.require_tests_passed)
                self.assertFalse(resumed_payload.allow_jdk_upgrade)
                self.assertEqual(resumed_payload.max_repos, 4)
                self.assertEqual(len(resumed_payload.filters), 1)
                self.assertEqual(resumed_payload.filters[0].content_rules[0].field_name, "java_version")
            finally:
                database.DATABASE_PATH = original_path

    def test_cancelled_run_is_detected(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            original_path = database.DATABASE_PATH
            database.DATABASE_PATH = Path(tmp) / "miner.db"
            try:
                payload = SearchRepositoriesRequest(
                    max_repos=1,
                    filters=[
                        GitHubSearchFilterRequest(
                            name="cancel-filter",
                            search_type="repositories",
                            query="language:java",
                        )
                    ],
                )
                run_id = create_mining_run(payload, status="running")

                cancel_mining_run(run_id)

                run = get_mining_run(run_id)
                self.assertEqual(run["status"], "cancelled")  # type: ignore[index]
                self.assertTrue(is_mining_run_cancelled(run_id))
            finally:
                database.DATABASE_PATH = original_path


if __name__ == "__main__":
    unittest.main()
