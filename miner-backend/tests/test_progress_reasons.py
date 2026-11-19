import tempfile
import unittest
from pathlib import Path

from app.core import database
from app.services.persistence import (
    get_mining_run_rejection_counts,
    upsert_mining_run_candidates_batch,
)


def _candidate(name: str, status: str, stage: str | None) -> dict:
    return {
        "page_number": 1, "page_index": 0, "repo_full_name": name, "repo_url": f"https://github.com/{name}",
        "commit_sha": "abc", "matched_filter": None, "matched_file": "pom.xml",
        "status": status, "rejection_stage": stage, "error_message": None, "metadata": {},
    }


class RejectionCountsTests(unittest.TestCase):
    def test_counts_eliminations_by_stage_and_ignores_overflow_and_accepted(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            original = database.DATABASE_PATH
            database.DATABASE_PATH = Path(tmp) / "miner.db"
            try:
                database.init_database()
                with database.get_connection() as conn:
                    conn.execute("INSERT INTO mining_runs (status, max_repos, max_workers, analyzer_workers) VALUES ('running', 5, 1, 1)")
                    run_id = conn.execute("SELECT id FROM mining_runs").fetchone()["id"]
                upsert_mining_run_candidates_batch(run_id, [
                    _candidate("a/compile1", "rejected", "compile"),
                    _candidate("a/compile2", "rejected", "compile"),
                    _candidate("a/tests", "rejected", "tests"),
                    _candidate("a/jdk", "rejected", "jdk_resolution"),
                    _candidate("a/noreason", "rejected", None),
                    _candidate("a/overflow", "rejected", "max_repos_reached"),
                    _candidate("a/ok", "accepted", None),
                ])
                counts = get_mining_run_rejection_counts(run_id)
                self.assertEqual(counts, {"compile": 2, "tests": 1, "jdk_resolution": 1, "unknown": 1})
                self.assertEqual(get_mining_run_rejection_counts(run_id + 99), {})
            finally:
                database.DATABASE_PATH = original


class JavaVersionLabelTests(unittest.TestCase):
    def test_old_and_new_notation_are_the_same_java(self) -> None:
        from app.services.statistics import canonical_java_version, java_version_comparison_label

        self.assertEqual(canonical_java_version("1.8"), "8")
        self.assertEqual(canonical_java_version("11.0.2"), "11")
        self.assertEqual(java_version_comparison_label("1.8", "8"), "Mesma versao")
        self.assertEqual(java_version_comparison_label("17", "17"), "Mesma versao")
        self.assertEqual(java_version_comparison_label("7", "8"), "Versao ajustada")


if __name__ == "__main__":
    unittest.main()
