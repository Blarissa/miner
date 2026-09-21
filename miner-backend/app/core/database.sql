CREATE TABLE IF NOT EXISTS mining_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,
    progress_stage TEXT,
    total_candidates INTEGER NOT NULL DEFAULT 0,
    processed_repositories INTEGER NOT NULL DEFAULT 0,
    accepted_repositories INTEGER NOT NULL DEFAULT 0,
    eliminated_repositories INTEGER NOT NULL DEFAULT 0,
    statistics_scope TEXT NOT NULL DEFAULT 'accepted',
    analyze INTEGER NOT NULL DEFAULT 0,
    include_statistics INTEGER NOT NULL DEFAULT 1,
    require_buildable INTEGER NOT NULL DEFAULT 0,
    require_tests_passed INTEGER NOT NULL DEFAULT 0,
    allow_jdk_upgrade INTEGER NOT NULL DEFAULT 0,
    persist_eliminated_repositories INTEGER NOT NULL DEFAULT 0,
    max_repos INTEGER NOT NULL,
    max_workers INTEGER NOT NULL,
    analyzer_workers INTEGER NOT NULL,
    delay_seconds REAL NOT NULL DEFAULT 0.0,
    provider TEXT NOT NULL DEFAULT 'github',
    page_cursor INTEGER NOT NULL DEFAULT 1,
    per_page INTEGER NOT NULL DEFAULT 100,
    last_processed_index INTEGER NOT NULL DEFAULT 0,
    acceptance_rate REAL NOT NULL DEFAULT 0.25,
    batch_size INTEGER,
    exhausted INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS search_filters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mining_run_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    search_type TEXT NOT NULL,
    raw_query TEXT NOT NULL,
    built_query TEXT NOT NULL,
    language TEXT,
    stars TEXT,
    forks TEXT,
    size TEXT,
    created_range TEXT,
    pushed_range TEXT,
    topic TEXT,
    license_key TEXT,
    visibility TEXT,
    user_filter TEXT,
    org_filter TEXT,
    repo_filter TEXT,
    followers TEXT,
    topics TEXT,
    fork_filter TEXT,
    archived INTEGER,
    mirror INTEGER,
    template INTEGER,
    good_first_issues TEXT,
    help_wanted_issues TEXT,
    filename TEXT,
    extension TEXT,
    path_filter TEXT,
    content_rules_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mining_run_id) REFERENCES mining_runs(id)
);

-- Regra de persistencia:
-- dados de repositorios eliminados so devem ser inseridos em repositories,
-- run_repositories, analysis_results ou analysis_cache quando
-- mining_runs.persist_eliminated_repositories = 1.
-- Quando 0, mantenha eliminados apenas na resposta da API/estatisticas em memoria.

CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL UNIQUE,
    html_url TEXT NOT NULL,
    description TEXT,
    language TEXT,
    stars INTEGER,
    forks INTEGER,
    open_issues INTEGER,
    topics TEXT,
    github_created_at TEXT,
    github_updated_at TEXT,
    github_pushed_at TEXT,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS run_repositories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mining_run_id INTEGER NOT NULL,
    repository_id INTEGER NOT NULL,
    search_filter_id INTEGER,
    matched_filter TEXT,
    matched_file TEXT,
    commit_sha TEXT,
    java_version TEXT,
    metadata TEXT,
    accepted INTEGER,
    eliminated INTEGER,
    FOREIGN KEY (mining_run_id) REFERENCES mining_runs(id),
    FOREIGN KEY (repository_id) REFERENCES repositories(id),
    FOREIGN KEY (search_filter_id) REFERENCES search_filters(id),
    UNIQUE (mining_run_id, repository_id, matched_file)
);

CREATE TABLE IF NOT EXISTS mining_run_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mining_run_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    page_index INTEGER NOT NULL,
    repo_full_name TEXT NOT NULL,
    repo_url TEXT NOT NULL,
    commit_sha TEXT,
    matched_filter TEXT,
    matched_file TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    rejection_stage TEXT,
    error_message TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at TEXT,
    FOREIGN KEY (mining_run_id) REFERENCES mining_runs(id),
    UNIQUE (mining_run_id, repo_full_name, commit_sha)
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_repository_id INTEGER NOT NULL UNIQUE,
    declared_java_version TEXT,
    effective_java_version TEXT,
    build_tool TEXT,
    test_framework TEXT,
    test_frameworks TEXT,
    mock_libraries TEXT,
    assertion_libraries TEXT,
    integration_test_tools TEXT,
    compile_duration_seconds REAL,
    test_duration_seconds REAL,
    compiled INTEGER NOT NULL DEFAULT 0,
    has_tests INTEGER NOT NULL DEFAULT 0,
    tests_passed INTEGER NOT NULL DEFAULT 0,
    eliminated INTEGER NOT NULL DEFAULT 0,
    error_stage TEXT,
    error_message TEXT,
    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_repository_id) REFERENCES run_repositories(id)
);

CREATE TABLE IF NOT EXISTS analysis_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repository_id INTEGER NOT NULL,
    commit_sha TEXT NOT NULL,
    run_test_suite INTEGER NOT NULL DEFAULT 1,
    allow_jdk_upgrade INTEGER NOT NULL DEFAULT 0,
    declared_java_version TEXT,
    effective_java_version TEXT,
    build_tool TEXT,
    test_framework TEXT,
    test_frameworks TEXT,
    mock_libraries TEXT,
    assertion_libraries TEXT,
    integration_test_tools TEXT,
    compile_duration_seconds REAL,
    test_duration_seconds REAL,
    compiled INTEGER NOT NULL DEFAULT 0,
    has_tests INTEGER NOT NULL DEFAULT 0,
    tests_passed INTEGER NOT NULL DEFAULT 0,
    eliminated INTEGER NOT NULL DEFAULT 0,
    error_stage TEXT,
    error_summary TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (repository_id) REFERENCES repositories(id),
    UNIQUE (repository_id, commit_sha, run_test_suite)
);

CREATE TABLE IF NOT EXISTS run_statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mining_run_id INTEGER NOT NULL,
    scope TEXT NOT NULL,
    statistics TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mining_run_id) REFERENCES mining_runs(id)
);

CREATE TRIGGER IF NOT EXISTS trg_analysis_cache_updated_at
AFTER UPDATE ON analysis_cache
FOR EACH ROW
BEGIN
    UPDATE analysis_cache
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

CREATE INDEX IF NOT EXISTS idx_search_filters_mining_run_id
    ON search_filters(mining_run_id);

CREATE INDEX IF NOT EXISTS idx_repositories_full_name
    ON repositories(full_name);

CREATE INDEX IF NOT EXISTS idx_run_repositories_mining_run_id
    ON run_repositories(mining_run_id);

CREATE INDEX IF NOT EXISTS idx_run_repositories_repository_id
    ON run_repositories(repository_id);

CREATE INDEX IF NOT EXISTS idx_run_repositories_commit_sha
    ON run_repositories(commit_sha);

CREATE INDEX IF NOT EXISTS idx_mining_run_candidates_run_status
    ON mining_run_candidates(mining_run_id, status);

CREATE INDEX IF NOT EXISTS idx_mining_run_candidates_page
    ON mining_run_candidates(mining_run_id, page_number, page_index);

CREATE INDEX IF NOT EXISTS idx_analysis_results_run_repository_id
    ON analysis_results(run_repository_id);

CREATE INDEX IF NOT EXISTS idx_analysis_results_flags
    ON analysis_results(compiled, has_tests, tests_passed, eliminated);

CREATE INDEX IF NOT EXISTS idx_analysis_cache_lookup
    ON analysis_cache(repository_id, commit_sha, run_test_suite);

CREATE INDEX IF NOT EXISTS idx_analysis_cache_flags
    ON analysis_cache(compiled, has_tests, tests_passed, eliminated);

CREATE INDEX IF NOT EXISTS idx_run_statistics_mining_run_id
    ON run_statistics(mining_run_id);

DELETE FROM analysis_cache
WHERE updated_at < datetime('now', '-30 days');
