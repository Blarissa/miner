from __future__ import annotations

import os
import unittest

from pydantic import ValidationError

from app.schemas.repositories import SearchRepositoriesRequest
from app.services.filters import filters_from_payload
from app.services.term_expansion import SIZE_SLICES, expand_term, find_catalog_entry, validate_term


os.environ["MINER_MAVEN_DISCOVERY"] = "off"  # nenhum teste deste módulo usa a rede


class TermExpansionTests(unittest.TestCase):
    def test_catalog_term_covers_the_three_evidences(self) -> None:
        result = expand_term("JDBC Template", coverage="rapida")
        evidences = {query.evidence for query in result.queries}
        queries = {query.query for query in result.queries}

        self.assertTrue(result.from_catalog)
        self.assertEqual(evidences, {"codigo", "import", "dependencia"})
        self.assertIn('"JdbcTemplate"', queries)
        self.assertIn('"org.springframework.jdbc.core.JdbcTemplate"', queries)
        self.assertIn('"spring-boot-starter-jdbc"', queries)

    def test_aliases_and_spacing_find_the_same_entry(self) -> None:
        self.assertIs(find_catalog_entry("jdbctemplate"), find_catalog_entry("  JDBC   template "))
        self.assertIsNone(find_catalog_entry("termo que nao existe"))

    def test_unknown_term_gets_spelling_variants_and_pom_artifact(self) -> None:
        result = expand_term("Acme Widget", coverage="rapida")
        queries = {query.query for query in result.queries}

        self.assertFalse(result.from_catalog)
        self.assertEqual(queries, {'"Acme Widget"', '"AcmeWidget"', '"acme-widget"'})

    def test_variants_are_deduplicated_ignoring_case(self) -> None:
        result = expand_term("Zorro", coverage="rapida")
        code_queries = [query.query for query in result.queries if query.evidence == "codigo"]
        self.assertEqual(code_queries, ['"Zorro"'])

    def test_broad_coverage_slices_code_queries_but_not_pom(self) -> None:
        rapid = expand_term("mockito", coverage="rapida")
        broad = expand_term("mockito", coverage="ampla")
        code_rapid = [q for q in rapid.queries if q.evidence != "dependencia"]
        pom_rapid = [q for q in rapid.queries if q.evidence == "dependencia"]

        self.assertEqual(len(broad.queries), len(code_rapid) * (len(SIZE_SLICES) + 1) + len(pom_rapid))
        self.assertTrue(all(q.file_size is None for q in broad.queries if q.evidence == "dependencia"))
        sliced = [q for q in broad.queries if q.evidence != "dependencia"]
        self.assertEqual(len([q for q in sliced if q.file_size is None]), len(code_rapid))  # uma consulta base por termo
        self.assertEqual(sum(1 for q in sliced if q.file_size), len(code_rapid) * len(SIZE_SLICES))
        for index, query in enumerate(broad.queries):  # a base vem antes das suas fatias
            if query.file_size:
                self.assertTrue(any(b.file_size is None and b.text == query.text and b.evidence == query.evidence for b in broad.queries[:index]))

    def test_rejects_search_operators_and_empty_terms(self) -> None:
        for bad in ["", "   ", 'a" OR "b', "repo:foo/bar", "a AND b", "x" * 81]:
            with self.assertRaises(ValueError, msg=bad):
                validate_term(bad)

    def test_search_request_builds_filters_from_term(self) -> None:
        payload = SearchRepositoriesRequest(term="JDBC Template", term_coverage="rapida")
        filters = filters_from_payload(payload.model_dump())

        self.assertEqual(len(filters), 8)
        self.assertTrue(all(f.search_type.value == "code" for f in filters))
        pom = [f for f in filters if "filename:pom.xml" in f.query]
        java = [f for f in filters if "extension:java" in f.query]
        self.assertEqual(len(pom), 2)
        self.assertEqual(len(java), 6)

    def test_file_size_slice_reaches_the_github_query(self) -> None:
        payload = SearchRepositoriesRequest(term="mockito", term_coverage="ampla")
        queries = [f.query for f in filters_from_payload(payload.model_dump())]

        self.assertTrue(any("size:<1500" in query for query in queries))
        self.assertTrue(any("size:1500..4000" in query for query in queries))

    def test_term_keeps_extra_filters_from_first_filter(self) -> None:
        payload = SearchRepositoriesRequest.model_validate({
            "term": "jpa",
            "term_coverage": "rapida",
            "filters": [{"name": "base", "query": "ignorado", "stars": ">10"}],
        })
        self.assertTrue(all(f.stars == ">10" for f in payload.filters))
        self.assertTrue(all(f.query != "ignorado" for f in payload.filters))

    def test_invalid_term_is_rejected_by_request(self) -> None:
        with self.assertRaises(ValidationError):
            SearchRepositoriesRequest(term='mockito" extension:xml')

    def test_request_without_term_is_unchanged(self) -> None:
        payload = SearchRepositoriesRequest.model_validate({"filters": [{"name": "a", "query": "mockito"}]})
        self.assertIsNone(payload.term)
        self.assertEqual([f.query for f in payload.filters], ["mockito"])


class CatalogIntegrityTests(unittest.TestCase):
    def test_catalog_is_broad_enough(self) -> None:
        from app.services.term_expansion import load_catalog

        names = set(load_catalog())
        for expected in ("jdbc template", "jpa", "mybatis", "junit 4", "junit 5", "mockito", "spring boot", "kafka", "hystrix", "resilience4j"):
            self.assertIn(expected, names)
        self.assertGreaterEqual(len(names), 50)

    def test_every_entry_is_well_formed_and_findable(self) -> None:
        import re

        from app.services.term_expansion import load_catalog

        for name, entry in load_catalog().items():
            with self.subTest(term=name):
                self.assertEqual(name, name.lower())
                self.assertIs(find_catalog_entry(name), entry)
                for alias in entry.get("aliases", []):
                    self.assertIs(find_catalog_entry(alias), entry, alias)
                for imported in entry["imports"]:
                    self.assertRegex(imported, r"^[a-z][\w]*(\.[A-Za-z_][\w]*)+$")
                for artifact in entry["dependencies"]:
                    self.assertRegex(artifact, r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
                for klass in entry["classes"]:
                    self.assertRegex(klass, r"^[A-Z][A-Za-z0-9_]*$")
                self.assertTrue(entry["classes"] or entry["imports"] or entry["dependencies"])
                self.assertEqual(len(re.findall(r"\s", "".join(entry["dependencies"]))), 0)

    def test_broad_coverage_stays_within_the_request_budget(self) -> None:
        from app.services.term_expansion import load_catalog

        for name in load_catalog():
            with self.subTest(term=name):
                self.assertLessEqual(len(expand_term(name, coverage="ampla").queries), 50)
                self.assertTrue(expand_term(name, coverage="rapida").from_catalog)

    def test_aliases_do_not_collide_between_entries(self) -> None:
        from app.services.term_expansion import load_catalog, normalize_term

        owners: dict[str, str] = {}
        for name, entry in load_catalog().items():
            for key in [name, *entry.get("aliases", [])]:
                compact = normalize_term(key).replace(" ", "")
                self.assertEqual(owners.setdefault(compact, name), name, key)

    def test_junit_versions_are_separate_for_migration_studies(self) -> None:
        four = {q.text for q in expand_term("junit 4", coverage="rapida").queries}
        five = {q.text for q in expand_term("JUnit5", coverage="rapida").queries}
        self.assertIn("org.junit.Test", four)
        self.assertIn("org.junit.jupiter.api.Test", five)
        self.assertNotIn("org.junit.jupiter.api.Test", four)


if __name__ == "__main__":
    unittest.main()
