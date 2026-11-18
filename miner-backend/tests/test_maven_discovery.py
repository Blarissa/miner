from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from app.services import maven_discovery
from app.services.maven_discovery import Artifact, candidate_artifact_ids, discover, groups_matching_term
from app.services.term_expansion import expand_term
from app.services.term_triage import confirm_evidence


def response(docs: list[dict], status: int = 200) -> Mock:
    mock = Mock()
    mock.status_code = status
    mock.json.return_value = {"response": {"numFound": len(docs), "docs": docs}}
    return mock


def doc(group: str, artifact: str, versions: int) -> dict:
    return {"g": group, "a": artifact, "latestVersion": "1.0", "versionCount": versions}


class DiscoveryBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.dict(os.environ, {
            "MINER_MAVEN_DISCOVERY": "on",
            "MINER_MAVEN_CACHE": str(Path(self.tmp.name) / "cache.json"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        sleeper = patch("app.services.maven_discovery.time.sleep")
        sleeper.start()
        self.addCleanup(sleeper.stop)


class CandidateTests(unittest.TestCase):
    def test_candidate_artifact_ids_cover_common_naming_patterns(self) -> None:
        ids = candidate_artifact_ids("Acme Widget")
        for expected in ("acme-widget", "acme-widget-core", "acme-widget-api", "spring-acme-widget",
                         "spring-boot-starter-acme-widget", "acmewidget"):
            self.assertIn(expected, ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(candidate_artifact_ids("   "), [])

    def test_camel_case_term_is_split(self) -> None:
        self.assertIn("acme-widget", candidate_artifact_ids("AcmeWidget"))

    def test_group_must_share_a_word_with_the_term(self) -> None:
        artifacts = [
            Artifact("org.mockito", "mockito-core", 100),
            Artifact("org.apache.commons", "commons-lang3", 50),
            Artifact("com", "x", 9),
        ]
        self.assertEqual(groups_matching_term("mockito", artifacts), ["org.mockito"])
        self.assertEqual(groups_matching_term("commons lang", artifacts), ["org.apache.commons"])
        self.assertEqual(groups_matching_term("guava", artifacts), [])
        self.assertEqual(groups_matching_term("x", artifacts), [])  # palavras curtas não valem


class DiscoverTests(DiscoveryBase):
    def test_finds_popular_artifacts_ranked_by_versions_and_ignores_noise(self) -> None:
        docs = [
            doc("org.acme", "acme-widget", 40),
            doc("org.acme", "acme-widget-core", 12),
            doc("io.noise", "acme-widget", 1),          # quase sem histórico: ignorado
            doc("org.other", "unrelated-artifact", 99),  # não está entre os candidatos: ignorado
        ]
        with patch("app.services.maven_discovery.requests.get", return_value=response(docs)):
            result = discover("Acme Widget")
        self.assertEqual(result.source, "maven_central")
        self.assertEqual([(a.group, a.artifact) for a in result.artifacts],
                         [("org.acme", "acme-widget"), ("org.acme", "acme-widget-core")])

    def test_no_match_is_reported_and_cached_briefly(self) -> None:
        with patch("app.services.maven_discovery.requests.get", return_value=response([])) as get:
            self.assertEqual(discover("Acme Widget").source, "sem_resultado")
            self.assertEqual(discover("Acme Widget").source, "sem_resultado")
        self.assertEqual(get.call_count, 1)

    def test_second_call_uses_the_file_cache(self) -> None:
        with patch("app.services.maven_discovery.requests.get",
                   return_value=response([doc("org.acme", "acme-widget", 10)])) as get:
            first = discover("Acme Widget")
            second = discover("acme-widget")
        self.assertEqual((first.source, second.source), ("maven_central", "cache"))
        self.assertEqual(get.call_count, 1)
        self.assertEqual(second.artifacts[0].artifact, "acme-widget")

    def test_expired_cache_entry_is_refetched(self) -> None:
        path = Path(os.environ["MINER_MAVEN_CACHE"])
        path.write_text(json.dumps({"acme|widget": {"at": 0, "artifacts": []}}))
        with patch("app.services.maven_discovery.requests.get",
                   return_value=response([doc("org.acme", "acme-widget", 10)])) as get:
            self.assertEqual(discover("Acme Widget").source, "maven_central")
        self.assertEqual(get.call_count, 1)

    def test_network_failure_falls_back_without_raising_and_is_not_cached(self) -> None:
        with patch("app.services.maven_discovery.requests.get",
                   side_effect=requests.ConnectionError("sem rede")) as get:
            self.assertEqual(discover("Acme Widget").source, "indisponivel")
        self.assertEqual(get.call_count, 2)  # tenta duas vezes
        with patch("app.services.maven_discovery.requests.get",
                   return_value=response([doc("org.acme", "acme-widget", 10)])):
            self.assertEqual(discover("Acme Widget").source, "maven_central")  # nada ficou em cache

    def test_server_error_then_success_is_retried(self) -> None:
        replies = [response([], status=500), response([doc("org.acme", "acme-widget", 10)])]
        with patch("app.services.maven_discovery.requests.get", side_effect=replies):
            self.assertEqual(discover("Acme Widget").source, "maven_central")

    def test_corrupt_cache_file_is_ignored(self) -> None:
        Path(os.environ["MINER_MAVEN_CACHE"]).write_text("{isto não é json")
        with patch("app.services.maven_discovery.requests.get",
                   return_value=response([doc("org.acme", "acme-widget", 10)])):
            self.assertEqual(discover("Acme Widget").source, "maven_central")

    def test_can_be_turned_off(self) -> None:
        with patch.dict(os.environ, {"MINER_MAVEN_DISCOVERY": "off"}), \
             patch("app.services.maven_discovery.requests.get") as get:
            self.assertEqual(discover("Acme Widget").source, "desligado")
        get.assert_not_called()


class ExpansionWithDiscoveryTests(DiscoveryBase):
    def test_unknown_term_gets_discovered_dependencies_and_group_import(self) -> None:
        docs = [doc("org.acme", "acme-widget", 40), doc("org.acme", "acme-widget-core", 12)]
        with patch("app.services.maven_discovery.requests.get", return_value=response(docs)):
            result = expand_term("Acme Widget", coverage="rapida")
        by_evidence: dict[str, set[str]] = {}
        for query in result.queries:
            by_evidence.setdefault(query.evidence, set()).add(query.text)
        self.assertFalse(result.from_catalog)
        self.assertEqual(result.source, "maven_central")
        self.assertEqual(by_evidence["dependencia"], {"acme-widget", "acme-widget-core"})
        self.assertEqual(by_evidence["import_prefix"], {"org.acme"})  # o grupo contém "acme", palavra do termo
        self.assertEqual(result.artifacts[0]["artifact"], "acme-widget")
        self.assertIn("source", result.to_dict())

    def test_group_unrelated_to_the_term_is_not_used_for_imports(self) -> None:
        docs = [doc("org.generic", "acme-widget", 40)]
        with patch("app.services.maven_discovery.requests.get", return_value=response(docs)):
            result = expand_term("Acme Widget", coverage="rapida")
        self.assertEqual([q for q in result.queries if q.evidence == "import_prefix"], [])
        self.assertIn("acme-widget", {q.text for q in result.queries if q.evidence == "dependencia"})

    def test_group_that_matches_the_term_becomes_an_import_search(self) -> None:
        docs = [doc("org.widgetworks", "acme-widget", 40)]
        with patch("app.services.maven_discovery.requests.get", return_value=response(docs)):
            result = expand_term("Acme Widget", coverage="rapida")
        prefixes = [q for q in result.queries if q.evidence == "import_prefix"]
        self.assertEqual([(q.query, q.text, q.extension) for q in prefixes],
                         [('"org.widgetworks"', "org.widgetworks", "java")])

    def test_import_prefix_is_sliced_in_broad_coverage_but_pom_is_not(self) -> None:
        docs = [doc("org.widgetworks", "acme-widget", 40)]
        with patch("app.services.maven_discovery.requests.get", return_value=response(docs)):
            result = expand_term("Acme Widget", coverage="ampla")
        prefix = [q for q in result.queries if q.evidence == "import_prefix"]
        self.assertEqual(sum(1 for q in prefix if q.file_size is None), 1)  # a consulta base
        self.assertGreater(sum(1 for q in prefix if q.file_size), 1)  # mais as fatias
        self.assertTrue(all(q.file_size is None for q in result.queries if q.evidence == "dependencia"))

    def test_catalog_terms_never_call_the_network(self) -> None:
        with patch("app.services.maven_discovery.requests.get") as get:
            result = expand_term("mockito", coverage="rapida")
        get.assert_not_called()
        self.assertEqual(result.source, "catalogo")

    def test_network_down_keeps_the_name_variants(self) -> None:
        with patch("app.services.maven_discovery.requests.get", side_effect=requests.ConnectionError("x")):
            result = expand_term("Acme Widget", coverage="rapida")
        self.assertEqual(result.source, "indisponivel")
        self.assertEqual({q.query for q in result.queries if q.evidence == "codigo"},
                         {'"Acme Widget"', '"AcmeWidget"'})


class ImportPrefixTriageTests(unittest.TestCase):
    def test_import_inside_the_group_is_confirmed(self) -> None:
        source = "import org.mockito.Mockito;\nclass A {}"
        self.assertTrue(confirm_evidence("import_prefix", "org.mockito", source).confirmed)
        static = "import static org.mockito.Mockito.when;\nclass A {}"
        self.assertTrue(confirm_evidence("import_prefix", "org.mockito", static).confirmed)

    def test_similar_group_or_comment_is_not_confirmed(self) -> None:
        self.assertFalse(confirm_evidence("import_prefix", "org.mockito", "import org.mockitoextra.X;").confirmed)
        self.assertEqual(
            confirm_evidence("import_prefix", "org.mockito", "// import org.mockito.Mockito;\nclass A {}").reason,
            "apenas_comentario_ou_texto",
        )


if __name__ == "__main__":
    unittest.main()
