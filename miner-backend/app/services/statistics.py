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


def repo_java_version(repo: dict[str, Any]) -> str:
    meta = metadata(repo)
    return str(
        repo.get("effective_java_version")
        or repo.get("java_version")
        or meta.get("java_version")
        or "unknown"
    )


def repo_build(repo: dict[str, Any]) -> str:
    meta = metadata(repo)
    return str(repo.get("build") or meta.get("build") or "unknown")


def repo_test_framework(repo: dict[str, Any]) -> str:
    meta = metadata(repo)
    return str(repo.get("test_framework") or meta.get("test_framework") or "unknown")


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

    java_counter: Counter[str] = Counter()
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

        total += 1
        analyzed = is_analyzed(repo)
        compiled = payload_bool(repo.get("compiled"))
        has_tests = payload_bool(repo.get("has_tests"))
        tests_passed = payload_bool(repo.get("tests_passed"))
        java_version = repo_java_version(repo)
        build = repo_build(repo)
        framework = repo_test_framework(repo)

        analyzed_total += int(analyzed)
        compiled_total += int(compiled)
        has_tests_total += int(has_tests)
        tests_passed_total += int(tests_passed)
        eliminated_total += int(eliminated)
        accepted_total += int(accepted)

        java_counter[java_version] += 1
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
        "java_versions": counter_stats(java_counter, total),
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
