import type {
    AnalyzedRepo,
    MiningRunStatus,
    RepositoryFilterOptions,
    SearchRepositoriesProgress,
    SearchRepositoriesResult,
    SearchFormData,
} from "../models/types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const POLL_INTERVAL_MS = 5000;
const TERMINAL_RUN_STATUSES = ["completed", "failed", "cancelled"];

type RawRepository = Record<string, unknown> & {
    name?: string;
    repo_name?: string;
    repository_url?: string;
    repo_url?: string;
    java_version?: string;
    effective_java_version?: string;
    build?: string;
    test_framework?: string;
    compiled?: boolean | number;
    has_tests?: boolean | number;
    tests_passed?: boolean | number;
    eliminated?: boolean | number;
    accepted?: boolean | number | null;
    matched_filter?: string | null;
    matched_file?: string | null;
    commit_sha?: string | null;
    analyzed_at?: string | null;
    metadata?: Record<string, unknown>;
    error_stage?: string | null;
    error_message?: string | null;
};

function optionalText(value: string): string | undefined {
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
}

function optionalBoolean(value: "" | "true" | "false"): boolean | undefined {
    if (value === "") {
        return undefined;
    }
    return value === "true";
}

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function requestJson<T>(
    path: string,
    options?: RequestInit,
): Promise<T> {
    const response = await fetch(`${API_URL}${path}`, options);

    if (!response.ok) {
        const errData = await response.json().catch(() => null);
        throw new Error(errData?.detail || `Erro HTTP ${response.status}`);
    }

    return response.json();
}

function stringValue(value: unknown): string {
    return typeof value === "string" ? value : "";
}

function optionalBooleanValue(value: unknown): boolean | null {
    if (value === null || value === undefined) return null;
    return Boolean(value);
}

function dateFromPicker(value: string): string | undefined {
    const trimmed = value.trim();
    return trimmed ? `>=${trimmed}` : undefined;
}

function javaVersionContentRule(javaVersion: SearchFormData["java_version"]) {
    const versionPattern = javaVersion === "8"
        ? "(?:1\\.)?8(?:\\.\\d+)?"
        : `${javaVersion}(?:\\.\\d+)?`;

    if (javaVersion) {
        return {
            field_name: "java_version",
            patterns: [
                `<java\\.version>\\s*${versionPattern}\\s*<\\/java\\.version>`,
                `<maven\\.compiler\\.release>\\s*${versionPattern}\\s*<\\/maven\\.compiler\\.release>`,
                `<maven\\.compiler\\.source>\\s*${versionPattern}\\s*<\\/maven\\.compiler\\.source>`,
                `<maven\\.compiler\\.target>\\s*${versionPattern}\\s*<\\/maven\\.compiler\\.target>`,
            ],
            required: true,
            fixed_value: javaVersion,
        };
    }

    return {
        field_name: "java_version",
        patterns: [
            "<java\\.version>\\s*([0-9][0-9.]*)\\s*<\\/java\\.version>",
            "<maven\\.compiler\\.release>\\s*([0-9][0-9.]*)\\s*<\\/maven\\.compiler\\.release>",
            "<maven\\.compiler\\.source>\\s*([0-9][0-9.]*)\\s*<\\/maven\\.compiler\\.source>",
            "<maven\\.compiler\\.target>\\s*([0-9][0-9.]*)\\s*<\\/maven\\.compiler\\.target>",
        ],
        required: false,
    };
}

function isTerminalRunStatus(status: MiningRunStatus["status"]): boolean {
    return TERMINAL_RUN_STATUSES.includes(status);
}

function normalizeRepository(item: RawRepository): AnalyzedRepo {
    const metadata = item.metadata && typeof item.metadata === "object" ? item.metadata : {};
    const analyzed =
        "compiled" in item ||
        "has_tests" in item ||
        "tests_passed" in item ||
        "eliminated" in item;

    return {
        name: stringValue(item.name || item.repo_name),
        repository_url: stringValue(item.repository_url || item.repo_url),
        java_version: stringValue(item.java_version || metadata.java_version),
        effective_java_version:
            stringValue(item.effective_java_version || metadata.java_version || item.java_version) ||
            "",
        build: stringValue(item.build || metadata.build) || "Maven",
        test_framework: stringValue(item.test_framework || metadata.test_framework),
        analyzed,
        compiled: Boolean(item.compiled),
        has_tests: Boolean(item.has_tests),
        tests_passed: Boolean(item.tests_passed),
        eliminated: Boolean(item.eliminated),
        accepted: optionalBooleanValue(item.accepted),
        matched_filter: item.matched_filter ?? null,
        matched_file: stringValue(item.matched_file || metadata.matched_file) || null,
        commit_sha: item.commit_sha ?? null,
        analyzed_at: item.analyzed_at ?? null,
        metadata,
        error_stage: item.error_stage || null,
        error_message: item.error_message || null,
    };
}

export async function getHealth(): Promise<{ status: string }> {
    return requestJson<{ status: string }>("/health");
}

function buildSearchPayload(formData: SearchFormData) {
    const analyzerWillRun = formData.require_buildable || formData.require_tests_passed;
    const queries = formData.queries.map((query) => query.trim()).filter(Boolean);
    const filters = queries.map((query, index) => ({
        name: queries.length === 1 ? "custom-search" : `custom-search-${index + 1}`,
        search_type: formData.search_type,
        query,
        file_path: formData.file_path || undefined,
        search_in: formData.search_in.length > 0 ? formData.search_in : undefined,
        language: "Java",
        stars: optionalText(formData.stars),
        forks: optionalText(formData.forks),
        size: optionalText(formData.size),
        created: dateFromPicker(formData.created),
        pushed: dateFromPicker(formData.pushed),
        topic: optionalText(formData.topic),
        license: optionalText(formData.license),
        visibility: formData.visibility || undefined,
        user: optionalText(formData.user),
        org: optionalText(formData.org),
        repo: optionalText(formData.repo),
        followers: optionalText(formData.followers),
        topics: optionalText(formData.topics),
        fork:
            formData.search_type === "repositories"
                ? formData.fork || undefined
                : undefined,
        archived:
            formData.search_type === "repositories"
                ? optionalBoolean(formData.archived)
                : undefined,
        mirror:
            formData.search_type === "repositories"
                ? optionalBoolean(formData.mirror)
                : undefined,
        template:
            formData.search_type === "repositories"
                ? optionalBoolean(formData.template)
                : undefined,
        good_first_issues: optionalText(formData.good_first_issues),
        help_wanted_issues: optionalText(formData.help_wanted_issues),
        filename: optionalText(formData.filename),
        extension: optionalText(formData.extension),
        path: optionalText(formData.path),
        sort: optionalText(formData.sort),
        order: formData.order || undefined,
        per_page: Number(formData.per_page),
        content_rules: [javaVersionContentRule(formData.java_version)],
    }));

    return {
        github_token: formData.github_token.trim() || undefined,
        max_repos: Number(formData.max_repos),
        max_workers: 4,
        analyzer_workers: 4,
        delay: 0,
        analyze: formData.require_tests_passed,
        require_buildable: formData.require_buildable,
        require_tests_passed: formData.require_tests_passed,
        allow_jdk_upgrade: analyzerWillRun && formData.allow_jdk_upgrade,
        persist_eliminated_repositories: formData.persist_eliminated_repositories,
        include_statistics: formData.include_statistics,
        statistics_scope: formData.statistics_scope,
        filters,
    };

}

export async function startRepositorySearch(formData: SearchFormData): Promise<{
    run_id: number;
    status: string;
    status_url: string;
    repositories_url: string;
    statistics_url: string;
}> {
    return requestJson("/repositories/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildSearchPayload(formData)),
    });
}

export async function getRepositoryRun(runId: number): Promise<MiningRunStatus> {
    const data = await requestJson<MiningRunStatus>(`/repositories/runs/${runId}`);
    return {
        ...data,
        analyzed_repositories: data.analyzed_repositories ?? data.processed_repositories ?? 0,
    };
}

export async function getRunRepositories(runId: number): Promise<{
    run_id: number;
    status: string;
    analyzed_repositories: number;
    total: number;
    repositories: AnalyzedRepo[];
}> {
    const data = await requestJson<{
        run_id: number;
        status: string;
        analyzed_repositories: number;
        total: number;
        repositories: RawRepository[];
    }>(`/repositories/runs/${runId}/repositories`);

    return {
        ...data,
        repositories: (data.repositories || []).map(normalizeRepository),
    };
}

export async function getRunStatistics(
    runId: number,
): Promise<SearchRepositoriesResult["statistics"]> {
    const data = await requestJson<{
        statistics?: SearchRepositoriesResult["statistics"];
    }>(`/repositories/runs/${runId}/statistics`);

    return data.statistics ?? null;
}

async function waitForRunCompletion(
    runId: number,
    onProgress?: (progress: SearchRepositoriesProgress) => void,
): Promise<MiningRunStatus> {
    let status = await getRepositoryRun(runId);
    onProgress?.({ run_id: runId, status });

    while (!isTerminalRunStatus(status.status)) {
        await sleep(POLL_INTERVAL_MS);
        status = await getRepositoryRun(runId);
        onProgress?.({ run_id: runId, status });
    }

    return status;
}

function assertSuccessfulRun(status: MiningRunStatus, runId: number): void {
    if (status.status === "failed") {
        throw new Error(status.error_message || `Run #${runId} falhou.`);
    }
}

async function fetchRunResult(
    runId: number,
    status: MiningRunStatus,
    includeStatistics: boolean,
): Promise<SearchRepositoriesResult> {
    const [repositoriesResponse, statistics] = await Promise.all([
        getRunRepositories(runId),
        includeStatistics ? getRunStatistics(runId) : Promise.resolve(null),
    ]);

    return {
        run_id: runId,
        status,
        total: repositoriesResponse.total,
        repositories: repositoriesResponse.repositories,
        statistics,
    };
}

function matchesRequestedRequirements(repo: AnalyzedRepo, formData: SearchFormData): boolean {
    if (formData.require_buildable && !repo.compiled) {
        return false;
    }

    if (
        formData.require_tests_passed &&
        (!repo.has_tests || !repo.tests_passed)
    ) {
        return false;
    }

    return true;
}

export async function resumeRepositoryRun(
    runId: number,
    onProgress?: (progress: SearchRepositoriesProgress) => void,
): Promise<SearchRepositoriesResult> {
    await requestJson(`/repositories/runs/${runId}/resume`, {
        method: "POST",
    });

    const status = await waitForRunCompletion(runId, onProgress);
    assertSuccessfulRun(status, runId);

    return fetchRunResult(runId, status, Boolean(status.include_statistics));
}

export async function cancelRepositoryRun(runId: number): Promise<MiningRunStatus> {
    await requestJson(`/repositories/runs/${runId}/cancel`, {
        method: "POST",
    });
    return getRepositoryRun(runId);
}

export async function searchRepositories(
    formData: SearchFormData,
    onProgress?: (progress: SearchRepositoriesProgress) => void,
): Promise<SearchRepositoriesResult> {
    const started = await startRepositorySearch(formData);
    const runId = started.run_id;
    const status = await waitForRunCompletion(runId, onProgress);
    assertSuccessfulRun(status, runId);
    const result = await fetchRunResult(runId, status, formData.include_statistics);

    const repositories = result.repositories.filter((repo) =>
        matchesRequestedRequirements(repo, formData)
    );

    return {
        run_id: runId,
        status,
        total: result.total ?? repositories.length,
        repositories,
        statistics: result.statistics,
    };
}

export async function filterRepositories(
    repositories: AnalyzedRepo[],
    filters: RepositoryFilterOptions,
): Promise<AnalyzedRepo[]> {
    const data = await requestJson<{ repositories?: RawRepository[] }>("/repositories/filter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repositories, filters }),
    });

    return (data.repositories || []).map(normalizeRepository);
}
