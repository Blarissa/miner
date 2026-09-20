export interface AnalyzedRepo {
    name: string;
    repository_url: string;
    java_version: string;
    effective_java_version: string;
    build: string;
    test_framework: string;
    test_frameworks?: string;
    mock_libraries?: string;
    assertion_libraries?: string;
    integration_test_tools?: string;
    compile_duration_seconds?: number | null;
    test_duration_seconds?: number | null;
    analyzed: boolean;
    compiled: boolean;
    has_tests: boolean;
    tests_passed: boolean;
    eliminated: boolean;
    accepted?: boolean | null;
    matched_filter?: string | null;
    matched_file?: string | null;
    commit_sha?: string | null;
    analyzed_at?: string | null;
    metadata?: Record<string, unknown>;
    error_stage?: string | null;
    error_message?: string | null;
}

export type StatisticsScope = "all" | "accepted" | "eliminated";

export interface CountPercentageStat {
    value: string;
    count: number;
    percentage: number;
}

export interface RateStat {
    value: string;
    total: number;
    success: number;
    failure: number;
    success_rate: number;
}

export interface DurationStat {
    count: number;
    total_seconds: number;
    average_seconds: number;
    min_seconds: number;
    max_seconds: number;
}

export interface RepositoryStatistics {
    scope: StatisticsScope;
    total: number;
    summary: {
        analyzed: number;
        accepted: number;
        eliminated: number;
        compiled: number;
        has_tests: number;
        tests_passed: number;
        test_success_rate_over_searched: number;
        test_success_rate_over_with_tests: number;
        eliminated_rate: number;
    };
    analysis_funnel: {
        searched: number;
        analyzed: number;
        compiled: number;
        has_tests: number;
        tests_passed: number;
        accepted: number;
    };
    java_versions: CountPercentageStat[];
    declared_java_versions?: CountPercentageStat[];
    effective_java_versions?: CountPercentageStat[];
    java_declared_effective_comparison?: CountPercentageStat[];
    test_frameworks?: CountPercentageStat[];
    mock_libraries?: CountPercentageStat[];
    assertion_libraries?: CountPercentageStat[];
    integration_test_tools?: CountPercentageStat[];
    stage_durations?: {
        compilation: DurationStat;
        testing: DurationStat;
    };
    test_repository_relation: {
        with_tests: number;
        without_tests: number;
        with_tests_rate: number;
        distribution: CountPercentageStat[];
    };
    error_stages: CountPercentageStat[];
    elimination: {
        accepted: number;
        eliminated: number;
        accepted_rate: number;
        eliminated_rate: number;
    };
    compiled_but_tests_failed_by_java_version: RateStat[];
    compilation_rate_by_build_tool: RateStat[];
    compilation_rate_by_test_framework: RateStat[];
}

export type MiningRunStatusValue = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface MiningRunStatus {
    id: number;
    status: MiningRunStatusValue | string;
    progress_stage?: string | null;
    total_candidates: number;
    processed_repositories: number;
    analyzed_repositories: number;
    accepted_repositories: number;
    eliminated_repositories: number;
    statistics_scope: StatisticsScope;
    include_statistics: boolean | number;
    require_buildable: boolean | number;
    require_tests_passed: boolean | number;
    allow_jdk_upgrade?: boolean | number;
    persist_eliminated_repositories: boolean | number;
    max_repos: number;
    max_workers: number;
    analyzer_workers: number;
    delay_seconds: number;
    provider?: string;
    page_cursor?: number;
    per_page?: number;
    last_processed_index?: number;
    acceptance_rate?: number;
    batch_size?: number | null;
    exhausted?: boolean | number;
    started_at: string;
    finished_at?: string | null;
    error_message?: string | null;
}

export interface SearchRepositoriesResult {
    run_id: number | null;
    status: MiningRunStatus | null;
    total: number;
    repositories: AnalyzedRepo[];
    statistics: RepositoryStatistics | null;
}

export interface SearchRepositoriesProgress {
    run_id: number;
    status: MiningRunStatus;
    repositories?: AnalyzedRepo[];
    statistics?: SearchRepositoriesResult["statistics"];
}

export interface SearchFormData {
    queries: string[];
    search_type: "code" | "repositories";
    file_path: string;
    max_repos: number;
    max_workers: number;
    analyzer_workers: number;
    delay: number;
    analyze: boolean;
    require_buildable: boolean;
    require_tests_passed: boolean;
    allow_jdk_upgrade: boolean;
    persist_eliminated_repositories: boolean;
    include_statistics: boolean;
    statistics_scope: StatisticsScope;
    github_token: string;
    language: string;
    java_version: "" | "6" | "7" | "8" | "11" | "17" | "21";
    stars: string;
    forks: string;
    size: string;
    created: string;
    pushed: string;
    topic: string;
    license: string;
    visibility: "" | "public" | "private" | "internal";
    user: string;
    org: string;
    repo: string;
    followers: string;
    topics: string;
    fork: "" | "true" | "false" | "only";
    archived: "" | "true" | "false";
    mirror: "" | "true" | "false";
    template: "" | "true" | "false";
    good_first_issues: string;
    help_wanted_issues: string;
    filename: string;
    extension: string;
    path: string;
    sort: string;
    order: "" | "asc" | "desc";
    per_page: number;
    search_in: Array<"name" | "description" | "readme" | "topics">;
}

export interface RepositoryFilterOptions {
    java_version?: string | null;
    java_versions?: string[] | null;
    repo_name?: string | null;
    eliminated?: boolean | null;
    has_tests?: boolean | null;
    tests_passed?: boolean | null;
}
