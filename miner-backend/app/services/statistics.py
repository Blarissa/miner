from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Literal


StatisticsScope = Literal["all", "accepted", "eliminated"]


def payload_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "sim", "yes", "y"}
    return bool(value)


def pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 2)


def metadata(repo: dict[str, Any]) -> dict[str, Any]:
    value = repo.get("metadata")
    return value if isinstance(value, dict) else {}


def repo_java_version(repo: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    meta = meta if meta is not None else metadata(repo)
    return str(
        repo.get("effective_java_version")
        or repo.get("java_version")
        or meta.get("java_version")
        or "unknown"
    )


def repo_declared_java_version(repo: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    meta = meta if meta is not None else metadata(repo)
    return str(repo.get("java_version") or meta.get("java_version") or "unknown")


def repo_effective_java_version(repo: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    meta = meta if meta is not None else metadata(repo)
    declared = repo_declared_java_version(repo, meta)
    return str(repo.get("effective_java_version") or declared or "unknown")


def java_version_comparison_label(declared: str, effective: str) -> str:
    return "Mesma versao" if declared == effective else "Versao ajustada"


def repo_build(repo: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    meta = meta if meta is not None else metadata(repo)
    return str(repo.get("build") or meta.get("build") or "unknown")


def repo_test_framework(repo: dict[str, Any], meta: dict[str, Any] | None = None) -> str:
    meta = meta if meta is not None else metadata(repo)
    return str(repo.get("test_framework") or meta.get("test_framework") or "unknown")


def repo_text_field(repo: dict[str, Any], field: str, meta: dict[str, Any] | None = None) -> str:
    meta = meta if meta is not None else metadata(repo)
    return str(repo.get(field) or meta.get(field) or "unknown")


def split_labels(value: str) -> list[str]:
    labels = [item.strip() for item in value.split(",") if item.strip()]
    return labels or ["unknown"]


def optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def duration_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "total_seconds": 0.0,
            "average_seconds": 0.0,
            "min_seconds": 0.0,
            "max_seconds": 0.0,
        }

    total = sum(values)
    return {
        "count": len(values),
        "total_seconds": round(total, 3),
        "average_seconds": round(total / len(values), 3),
        "min_seconds": round(min(values), 3),
        "max_seconds": round(max(values), 3),
    }


def is_analyzed(repo: dict[str, Any]) -> bool:
    return any(
        field in repo
        for field in ("compiled", "has_tests", "tests_passed", "eliminated")
    )


def is_eliminated(repo: dict[str, Any]) -> bool:
    return payload_bool(repo.get("eliminated"))


def is_accepted(repo: dict[str, Any]) -> bool:
    if not is_analyzed(repo):
        return True
    return not is_eliminated(repo)


def filter_by_scope(
    repositories: list[dict[str, Any]],
    scope: StatisticsScope,
) -> list[dict[str, Any]]:
    if scope == "all":
        return repositories
    if scope == "accepted":
        return [repo for repo in repositories if is_accepted(repo)]
    return [repo for repo in repositories if is_eliminated(repo)]


def counter_stats(counter: Counter[str], total: int) -> list[dict[str, Any]]:
    return [
        {
            "value": value,
            "count": count,
            "percentage": pct(count, total),
        }
        for value, count in counter.most_common()
    ]


def rate_group_stats(
    repositories: list[dict[str, Any]],
    group_fn,
    success_fn,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0})

    for repo in repositories:
        key = group_fn(repo)
        groups[key]["total"] += 1
        if success_fn(repo):
            groups[key]["success"] += 1

    return [
        {
            "value": key,
            "total": values["total"],
            "success": values["success"],
            "failure": values["total"] - values["success"],
            "success_rate": pct(values["success"], values["total"]),
        }
        for key, values in sorted(
            groups.items(),
            key=lambda item: (item[1]["total"], item[1]["success"]),
            reverse=True,
        )
    ]


def rate_group_stats_from_groups(groups: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    return [
        {
            "value": key,
            "total": values["total"],
            "success": values["success"],
            "failure": values["total"] - values["success"],
            "success_rate": pct(values["success"], values["total"]),
        }
        for key, values in sorted(
            groups.items(),
            key=lambda item: (item[1]["total"], item[1]["success"]),
            reverse=True,
        )
    ]


def build_statistics(
    repositories: list[dict[str, Any]],
    scope: StatisticsScope = "accepted",
) -> dict[str, Any]:
    total = 0
    analyzed_total = 0
    compiled_total = 0
    has_tests_total = 0
    tests_passed_total = 0
    eliminated_total = 0
    accepted_total = 0

    declared_java_counter: Counter[str] = Counter()
    effective_java_counter: Counter[str] = Counter()
    java_comparison_counter: Counter[str] = Counter()
    test_frameworks_counter: Counter[str] = Counter()
    mock_libraries_counter: Counter[str] = Counter()
    assertion_libraries_counter: Counter[str] = Counter()
    integration_test_tools_counter: Counter[str] = Counter()
    compile_duration_values: list[float] = []
    test_duration_values: list[float] = []
    tests_counter: Counter[str] = Counter()
    error_stage_counter: Counter[str] = Counter()
    compile_failed_by_java: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0})
    compile_by_build: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0})
    compile_by_framework: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0})

    for repo in repositories:
        accepted = is_accepted(repo)
        eliminated = is_eliminated(repo)
        if scope == "accepted" and not accepted:
            continue
        if scope == "eliminated" and not eliminated:
            continue

        meta = metadata(repo)  
        total += 1
        analyzed = is_analyzed(repo)
        compiled = payload_bool(repo.get("compiled"))
        has_tests = payload_bool(repo.get("has_tests"))
        tests_passed = payload_bool(repo.get("tests_passed"))
        declared_java_version = repo_declared_java_version(repo, meta)
        effective_java_version = repo_effective_java_version(repo, meta)
        java_version = effective_java_version
        build = repo_build(repo, meta)
        framework = repo_test_framework(repo, meta)
        compile_duration = optional_float(repo.get("compile_duration_seconds"))
        test_duration = optional_float(repo.get("test_duration_seconds"))

        analyzed_total += int(analyzed)
        compiled_total += int(compiled)
        has_tests_total += int(has_tests)
        tests_passed_total += int(tests_passed)
        eliminated_total += int(eliminated)
        accepted_total += int(accepted)

        declared_java_counter[declared_java_version] += 1
        effective_java_counter[effective_java_version] += 1
        java_comparison_counter[
            java_version_comparison_label(declared_java_version, effective_java_version)
        ] += 1
        for label in split_labels(repo_text_field(repo, "test_frameworks", meta)):
            test_frameworks_counter[label] += 1
        for label in split_labels(repo_text_field(repo, "mock_libraries", meta)):
            mock_libraries_counter[label] += 1
        for label in split_labels(repo_text_field(repo, "assertion_libraries", meta)):
            assertion_libraries_counter[label] += 1
        for label in split_labels(repo_text_field(repo, "integration_test_tools", meta)):
            integration_test_tools_counter[label] += 1
        if compile_duration is not None:
            compile_duration_values.append(compile_duration)
        if test_duration is not None:
            test_duration_values.append(test_duration)
        tests_counter["with_tests" if has_tests else "without_tests"] += 1
        if eliminated:
            error_stage_counter[str(repo.get("error_stage") or "unknown")] += 1

        compile_by_build[build]["total"] += 1
        compile_by_build[build]["success"] += int(compiled)
        compile_by_framework[framework]["total"] += 1
        compile_by_framework[framework]["success"] += int(compiled)

        if compiled and has_tests and not tests_passed:
            compile_failed_by_java[java_version]["total"] += 1
            compile_failed_by_java[java_version]["success"] += 1

    return {
        "scope": scope,
        "total": total,
        "summary": {
            "analyzed": analyzed_total,
            "accepted": accepted_total,
            "eliminated": eliminated_total,
            "compiled": compiled_total,
            "has_tests": has_tests_total,
            "tests_passed": tests_passed_total,
            "test_success_rate_over_searched": pct(tests_passed_total, total),
            "test_success_rate_over_with_tests": pct(tests_passed_total, has_tests_total),
            "eliminated_rate": pct(eliminated_total, total),
        },
        "analysis_funnel": {
            "searched": total,
            "analyzed": analyzed_total,
            "compiled": compiled_total,
            "has_tests": has_tests_total,
            "tests_passed": tests_passed_total,
            "accepted": accepted_total,
        },
        "java_versions": counter_stats(effective_java_counter, total),
        "declared_java_versions": counter_stats(declared_java_counter, total),
        "effective_java_versions": counter_stats(effective_java_counter, total),
        "java_declared_effective_comparison": counter_stats(
            java_comparison_counter,
            total,
        ),
        "test_frameworks": counter_stats(test_frameworks_counter, total),
        "mock_libraries": counter_stats(mock_libraries_counter, total),
        "assertion_libraries": counter_stats(assertion_libraries_counter, total),
        "integration_test_tools": counter_stats(integration_test_tools_counter, total),
        "stage_durations": {
            "compilation": duration_stats(compile_duration_values),
            "testing": duration_stats(test_duration_values),
        },
        "test_repository_relation": {
            "with_tests": has_tests_total,
            "without_tests": total - has_tests_total,
            "with_tests_rate": pct(has_tests_total, total),
            "distribution": counter_stats(tests_counter, total),
        },
        "error_stages": counter_stats(error_stage_counter, eliminated_total),
        "elimination": {
            "accepted": accepted_total,
            "eliminated": eliminated_total,
            "accepted_rate": pct(accepted_total, total),
            "eliminated_rate": pct(eliminated_total, total),
        },
        "compiled_but_tests_failed_by_java_version": rate_group_stats_from_groups(
            compile_failed_by_java
        ),
        "compilation_rate_by_build_tool": rate_group_stats_from_groups(compile_by_build),
        "compilation_rate_by_test_framework": rate_group_stats_from_groups(compile_by_framework),
    }
