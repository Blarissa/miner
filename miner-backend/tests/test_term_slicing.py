import unittest
from unittest.mock import patch

from app.services import miner
from app.services.filters import GitHubSearchFilter


def _filter(size: str | None, evidence: str = "codigo", text: str = "JdbcTemplate") -> GitHubSearchFilter:
    query = f'"{text}" extension:java' + (f" size:{size}" if size else "")
    return GitHubSearchFilter(name=query, search_type="code", query=query, term_evidence=evidence, term_text=text)


class SliceSkippingTests(unittest.TestCase):
    def _run(self, base_total: int):
        calls: list[str] = []

        def fake(*, session, search_filter, page, per_page, delay):
            calls.append(search_filter.query)
            total = base_total if " size:" not in search_filter.query else 50
            return [], total, False

        filters = [_filter(None), _filter("<1500"), _filter("1500..4000"), _filter(None, "import", "a.b.C"), _filter("<1500", "import", "a.b.C")]
        progress: list[tuple[int, int]] = []
        with patch.object(miner, "search_filter_candidates_page", side_effect=fake):
            miner.fetch_mining_page(
                token="x", filters=filters, page=1, per_page=100, delay=0, seen_keys=set(),
                session=object(), on_filter_done=lambda done, total, found: progress.append((done, total)),
            )
        return calls, progress

    def test_slices_are_skipped_when_base_query_fits_in_the_cap(self) -> None:
        calls, progress = self._run(base_total=400)
        self.assertEqual(len(calls), 2)  # so as duas consultas base
        self.assertTrue(all(" size:" not in query for query in calls))
        self.assertEqual(progress[-1], (5, 5))  # o progresso ainda chega ao fim

    def test_slices_run_when_base_query_exceeds_the_cap(self) -> None:
        calls, _ = self._run(base_total=15000)
        self.assertEqual(len(calls), 5)

    def test_cancellation_stops_between_queries(self) -> None:
        calls: list[str] = []

        def fake(*, session, search_filter, page, per_page, delay):
            calls.append(search_filter.query)
            return [], 15000, False

        filters = [_filter(None), _filter("<1500"), _filter("1500..4000"), _filter(">30000")]
        with patch.object(miner, "search_filter_candidates_page", side_effect=fake):
            miner.fetch_mining_page(
                token="x", filters=filters, page=1, per_page=100, delay=0, seen_keys=set(),
                session=object(), on_filter_done=lambda done, total, found: done >= 2,
            )
        self.assertEqual(len(calls), 2)

    def test_cap_boundary_is_inclusive(self) -> None:
        calls, _ = self._run(base_total=1000)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
