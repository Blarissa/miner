import React, { useCallback, useEffect, useState, useMemo } from "react";
import {
    Search,
    Terminal,
    ExternalLink,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Play,
    Filter,
    Loader2,
    Code2,
    ChevronDown,
    SlidersHorizontal,
    Database,
    Calendar,
    Plus,
    Trash2,
    Info,
    TestTube2,
    Layers3,
    Clock,
    Hammer,
    Lock,
} from "lucide-react";
import {
    cancelRepositoryRun,
    getRepositoryRun,
    getRunRepositories,
    getRunStatistics,
    resumeRepositoryRun,
    searchRepositories,
} from "../api/repositories";
import type {
    AnalyzedRepo,
    MiningRunStatus,
    RepositoryStatistics,
    SearchFormData,
    SearchRepositoriesResult,
} from "../models/types";
import { Button, Card, Checkbox, FieldError, FieldLabel, Modal, Select, TextInput } from "./ui";
import { progressStageLabel, runStatusLabel } from "../models/runLabels";

interface MiningDashboardProps {
    initialRunId?: number | null;
    loadRequestKey?: number;
    onStatisticsChange: (statistics: RepositoryStatistics | null) => void;
    onEliminatedRepositoryStatsVisibilityChange: (visible: boolean) => void;
    onOpenStatistics: () => void;
}

const INITIAL_SEARCH_FORM_DATA: SearchFormData = {
    queries: ["mockito"],
    search_type: "code",
    file_path: "",
    max_repos: 20,
    max_workers: 4,
    analyzer_workers: 4,
    delay: 0,
    analyze: false,
    require_buildable: false,
    require_tests_passed: false,
    allow_jdk_upgrade: false,
    persist_eliminated_repositories: false,
    include_statistics: true,
    statistics_scope: "accepted",
    github_token: "",
    language: "Java",
    java_version: "",
    stars: "",
    forks: "",
    size: "",
    created: "",
    pushed: "",
    topic: "",
    license: "",
    visibility: "public",
    user: "",
    org: "",
    repo: "",
    followers: "",
    topics: "",
    fork: "false",
    archived: "false",
    mirror: "",
    template: "",
    good_first_issues: "",
    help_wanted_issues: "",
    filename: "",
    extension: "",
    path: "",
    sort: "",
    order: "",
    per_page: 100,
    search_in: [],
};

function errorMessage(error: unknown): string {
    return error instanceof Error ? error.message : "Erro inesperado";
}

function splitTags(value?: string | null): string[] {
    if (!value) return [];
    return value
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item && item.toLowerCase() !== "unknown");
}

function formatDuration(seconds?: number | null): string {
    if (seconds === null || seconds === undefined || Number.isNaN(seconds)) {
        return "—";
    }
    if (seconds < 60) {
        return `${seconds.toFixed(1)}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.round(seconds % 60);
    return `${minutes}m ${remainingSeconds.toString().padStart(2, "0")}s`;
}

function canResumeMiningRun(
    runStatus: MiningRunStatus | null,
    lastRunId: number | null,
): boolean {
    if (!runStatus || lastRunId === null) {
        return false;
    }

    const terminalForResume = !["queued", "running", "completed"].includes(runStatus.status);
    return Boolean(
        terminalForResume &&
        !runStatus.exhausted &&
        runStatus.accepted_repositories < runStatus.max_repos,
    );
}

function canCancelMiningRun(
    runStatus: MiningRunStatus | null,
    lastRunId: number | null,
): boolean {
    return Boolean(
        runStatus &&
        lastRunId !== null &&
        ["queued", "running"].includes(runStatus.status),
    );
}

function progressFromRunStatus(runStatus: MiningRunStatus | null) {
    const total = runStatus?.total_candidates || runStatus?.max_repos || 0;
    const current = runStatus?.analyzed_repositories || 0;
    const percent = total > 0
        ? Math.min(100, Math.round((current / total) * 100))
        : 0;

    return { total, current, percent };
}

function matchesTableFilters(
    repo: AnalyzedRepo,
    searchTerm: string,
    selectedJavaVersion: string,
    formData: SearchFormData,
): boolean {
    const matchesName = repo.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesJava =
        selectedJavaVersion === "ALL" ||
        repo.effective_java_version === selectedJavaVersion ||
        repo.java_version === selectedJavaVersion;
    const matchesBuildable = formData.require_buildable ? repo.compiled : true;
    const matchesPassed = formData.require_tests_passed
        ? repo.has_tests && repo.tests_passed
        : true;

    return matchesName && matchesJava && matchesBuildable && matchesPassed;
}

function calculateMetrics(repositories: AnalyzedRepo[]) {
    const total = repositories.length;
    if (total === 0) return { compiled: 0, passed: 0, upgraded: 0 };

    const totals = repositories.reduce(
        (acc, repo) => {
            if (repo.compiled) acc.compiled += 1;
            if (repo.tests_passed) acc.passed += 1;
            if (
                repo.effective_java_version &&
                repo.effective_java_version !== repo.java_version
            ) {
                acc.upgraded += 1;
            }
            return acc;
        },
        { compiled: 0, passed: 0, upgraded: 0 },
    );

    return {
        compiled: Math.round((totals.compiled / total) * 100),
        passed: Math.round((totals.passed / total) * 100),
        upgraded: totals.upgraded,
    };
}

export default function MiningDashboard({
    initialRunId = null,
    loadRequestKey = 0,
    onStatisticsChange,
    onEliminatedRepositoryStatsVisibilityChange,
    onOpenStatistics,
}: MiningDashboardProps) {
    const [formData, setFormData] = useState<SearchFormData>(INITIAL_SEARCH_FORM_DATA);

    const [loading, setLoading] = useState<boolean>(false);
    const [repositories, setRepositories] = useState<AnalyzedRepo[]>([]);
    const [lastRunId, setLastRunId] = useState<number | null>(null);
    const [lastTotal, setLastTotal] = useState<number>(0);
    const [lastRunIncludedTests, setLastRunIncludedTests] = useState<boolean>(false);
    const [runStatus, setRunStatus] = useState<MiningRunStatus | null>(null);
    const [selectedRepoDetails, setSelectedRepoDetails] = useState<AnalyzedRepo | null>(null);

    const [searchTerm, setSearchTerm] = useState<string>("");
    const [selectedJavaVersion, setSelectedJavaVersion] = useState<string>("ALL");
    const [showAdvancedFilters, setShowAdvancedFilters] = useState<boolean>(false);
    const isBuildOnlyMode = formData.require_buildable && !formData.require_tests_passed;
    const analyzerWillRun = formData.require_buildable || formData.require_tests_passed;
    const 
    { 
        total: progressTotal, 
        current: progressCurrent, 
        percent: progressPercent 
    } = progressFromRunStatus(runStatus);
    const canResumeRun = canResumeMiningRun(runStatus, lastRunId);
    const canCancelRun = canCancelMiningRun(runStatus, lastRunId);
    const [errorBanner, setErrorBanner] = useState<string | null>(null);
    const [statistics, setStatisticsState] = useState<RepositoryStatistics | null>(null);

    const setStatistics = useCallback((value: RepositoryStatistics | null) => {
        setStatisticsState(value);
        onStatisticsChange(value); 
    }, [onStatisticsChange]);

    const DEFAULT_JAVA_VERSIONS = ["6", "7", "8", "11", "17", "21"];
    const javaVersionOptions = useMemo(() => {
        if (statistics?.java_versions?.length) {
            return statistics.java_versions
                .map((item) => item.value)
                .filter((value) => value !== "unknown");
        }
        return DEFAULT_JAVA_VERSIONS;
    }, [statistics]);

    const handleProgress = useCallback(({ run_id, status, repositories: liveRepos, statistics: liveStats }: {
        run_id: number;
        status: MiningRunStatus;
        repositories?: AnalyzedRepo[];
        statistics?: RepositoryStatistics | null;
    }) => {
        setLastRunId(run_id);
        setRunStatus(status);
        setLastTotal(status.accepted_repositories || status.total_candidates || 0);
        if (liveRepos) setRepositories(liveRepos);       // <- tabela agora atualiza ao vivo
        if (liveStats !== undefined) setStatistics(liveStats ?? null);
    }, [setStatistics]);

    const [showValidation, setShowValidation] = useState<boolean>(false);

    const formErrors = useMemo(() => {
        const emptyQueryIndexes = formData.queries
            .map((query, index) => (query.trim() === "" ? index : -1))
            .filter((index) => index >= 0);
        return {
            emptyQueryIndexes,
            githubToken: formData.github_token.trim() === "",
            searchType: !formData.search_type,
            maxRepos: !Number.isInteger(formData.max_repos) || formData.max_repos < 1,
        };
    }, [formData.queries, formData.github_token, formData.search_type, formData.max_repos]);

    const hasFormErrors =
        formErrors.emptyQueryIndexes.length > 0 ||
        formErrors.githubToken ||
        formErrors.searchType ||
        formErrors.maxRepos;

    const handleSearch = async (e: React.FormEvent) => {
        e.preventDefault();
        setShowValidation(true);
        if (hasFormErrors) {
            const firstInvalidId = formErrors.emptyQueryIndexes.length > 0
                ? `field-query-${formErrors.emptyQueryIndexes[0]}`
                : formErrors.githubToken
                    ? "field-github-token"
                    : formErrors.searchType
                        ? "field-search-type"
                        : "field-max-repos";
            document.getElementById(firstInvalidId)?.focus();
            return;
        }
        setLoading(true);
        setErrorBanner(null);
        try {
            setRepositories([]);
            setRunStatus(null);
            const result = await searchRepositories(formData, handleProgress);
            applySearchResult(result, formData.require_tests_passed, formData.persist_eliminated_repositories);
        } catch (error: unknown) {
            console.error("Erro na busca:", error);
            setErrorBanner(`Falha ao minerar repositórios: ${errorMessage(error)}`);
        } finally {
            setLoading(false);
        }
    };

    const handleResumeRun = async () => {
        if (lastRunId === null) return;
        setLoading(true);
        setErrorBanner(null);
        try {
            const result = await resumeRepositoryRun(lastRunId, handleProgress);
            applySearchResult(result, Boolean(result.status?.require_tests_passed), Boolean(result.status?.persist_eliminated_repositories));
        } catch (error: unknown) {
            console.error("Erro ao retomar consulta:", error);
            setErrorBanner(`Falha ao retomar consulta: ${errorMessage(error)}`);
        } finally {
            setLoading(false);
        }
    };

    const applySearchResult = useCallback((
        result: SearchRepositoriesResult,
        includedTests: boolean,
        persistedEliminatedRepositories: boolean,
    ) => {
        setRepositories(result.repositories);
        setLastRunId(result.run_id);
        setLastTotal(result.total);
        setRunStatus(result.status);
        setLastRunIncludedTests(includedTests);
        onEliminatedRepositoryStatsVisibilityChange(persistedEliminatedRepositories);
        onStatisticsChange(result.statistics);
    }, [onEliminatedRepositoryStatsVisibilityChange, onStatisticsChange]);

    const loadSavedRun = useCallback(async (runId: number) => {
        setLoading(true);
        setErrorBanner(null);

        try {
            setRepositories([]);
            const [status, repositoriesResponse, statisticsResponse] = await Promise.all([
                getRepositoryRun(runId),
                getRunRepositories(runId),
                getRunStatistics(runId),
            ]);

            setRunStatus(status);
            setRepositories(repositoriesResponse.repositories);
            setLastRunId(runId);
            setLastTotal(repositoriesResponse.total);
            setLastRunIncludedTests(Boolean(status.require_tests_passed));
            onEliminatedRepositoryStatsVisibilityChange(Boolean(status.persist_eliminated_repositories));
            onStatisticsChange(statisticsResponse);
        } catch (error: unknown) {
            console.error("Erro ao carregar consulta antiga:", error);
            setErrorBanner(`Falha ao carregar consulta antiga: ${errorMessage(error)}`);
        } finally {
            setLoading(false);
        }
    }, [onEliminatedRepositoryStatsVisibilityChange, onStatisticsChange]);

    useEffect(() => {
        if (initialRunId && initialRunId > 0) {
            const timeoutId = window.setTimeout(() => {
                void loadSavedRun(initialRunId);
            }, 0);

            return () => window.clearTimeout(timeoutId);
        }
    }, [initialRunId, loadRequestKey, loadSavedRun]);

    const toggleSearchIn = (
        value: "name" | "description" | "readme" | "topics",
    ) => {
        setFormData((currentFormData) => {
            const selected = currentFormData.search_in.includes(value);
            return {
                ...currentFormData,
                search_in: selected
                    ? currentFormData.search_in.filter((item) => item !== value)
                    : [...currentFormData.search_in, value],
            };
        });
    };

    const updateQuery = (index: number, value: string) => {
        setFormData((currentFormData) => ({
            ...currentFormData,
            queries: currentFormData.queries.map((query, queryIndex) =>
                queryIndex === index ? value : query
            ),
        }));
    };

    const addQuery = () => {
        setFormData((currentFormData) => ({
            ...currentFormData,
            queries: [...currentFormData.queries, ""],
        }));
    };

    const removeQuery = (index: number) => {
        setFormData((currentFormData) => ({
            ...currentFormData,
            queries: currentFormData.queries.filter((_, queryIndex) => queryIndex !== index),
        }));
    };
    
    const handleCancelRun = async () => {
        if (lastRunId === null) return;

        setErrorBanner(null);
        try {
            const status = await cancelRepositoryRun(lastRunId);
            setRunStatus(status);
            setLoading(false);
        } catch (error: unknown) {
            console.error("Erro ao cancelar consulta:", error);
            setErrorBanner(`Falha ao cancelar consulta: ${errorMessage(error)}`);
        }
    };

    const filteredRepositories = useMemo(() => {
        return repositories.filter((repo) =>
            matchesTableFilters(repo, searchTerm, selectedJavaVersion, formData)
        );
    }, [repositories, searchTerm, selectedJavaVersion, formData]);

    const metrics = useMemo(() => {
        return calculateMetrics(repositories);
    }, [repositories]);

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200 p-6 sm:p-10 font-sans">
            <div className="max-w-7xl mx-auto space-y-7">

                {/* Cabeçalho */}
                <header className="flex items-center justify-between border-b border-slate-800 pb-5">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight text-slate-50 flex items-center gap-2.5">
                            <Hammer className="h-7 w-7 text-cyan-400" />
                            Mineração
                        </h1>
                        <p className="text-sm text-slate-400 mt-1">
                            Pipeline automatizado de descoberta, build e validação de testes.
                        </p>
                    </div>
                </header>

                {/* Banner de Erro */}
                {errorBanner && (
                    <div role="alert" className="flex items-start justify-between gap-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                        <div className="flex items-start gap-2">
                            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-400" />
                            <span>{errorBanner}</span>
                        </div>
                        <button
                            type="button"
                            onClick={() => setErrorBanner(null)}
                            aria-label="Fechar aviso de erro"
                            className="shrink-0 text-rose-300 hover:text-rose-100 text-xs font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 rounded"
                        >
                            Fechar
                        </button>
                    </div>
                )}

                {/* Formulário de Busca */}
                <section className="bg-slate-800/80 border border-slate-700/60 rounded-xl p-6 shadow-md">
                    <form onSubmit={handleSearch} noValidate className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="md:col-span-2">
                                <div className="flex items-center justify-between gap-3 mb-1.5">
                                    <FieldLabel htmlFor="field-query-0" required className="">
                                        Queries de Busca no GitHub
                                    </FieldLabel>
                                    <button
                                        type="button"
                                        onClick={addQuery}
                                        className="inline-flex items-center gap-1.5 text-xs font-semibold text-cyan-300 hover:text-cyan-200 transition"
                                    >
                                        <Plus className="h-3.5 w-3.5" />
                                        Adicionar query
                                    </button>
                                </div>
                                <div className="space-y-2">
                                    {formData.queries.map((query, index) => (
                                        <div key={index} className="flex items-center gap-2">
                                            <div className="flex-1">
                                                <TextInput
                                                    id={`field-query-${index}`}
                                                    icon={<Search />}
                                                    type="text"
                                                    value={query}
                                                    onChange={(e) => updateQuery(index, e.target.value)}
                                                    placeholder="Ex: mockito filename:pom.xml language:xml"
                                                    aria-required="true"
                                                    invalid={showValidation && formErrors.emptyQueryIndexes.includes(index)}
                                                    aria-describedby={
                                                        showValidation && formErrors.emptyQueryIndexes.includes(index)
                                                            ? "field-queries-error"
                                                            : undefined
                                                    }
                                                />
                                            </div>
                                            <button
                                                type="button"
                                                onClick={() => removeQuery(index)}
                                                disabled={formData.queries.length === 1}
                                                title="Remover query"
                                                aria-label={`Remover query ${index + 1}`}
                                                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 hover:text-rose-300 hover:border-rose-500/50 disabled:opacity-40 disabled:hover:text-slate-400 disabled:hover:border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                                {showValidation && formErrors.emptyQueryIndexes.length > 0 && (
                                    <FieldError id="field-queries-error">
                                        Preencha a query destacada ou remova-a.
                                    </FieldError>
                                )}
                            </div>

                            <div>
                                <FieldLabel htmlFor="field-github-token" required>
                                    GitHub Token
                                </FieldLabel>
                                <TextInput
                                    id="field-github-token"
                                    type="password"
                                    value={formData.github_token}
                                    onChange={(e) => setFormData({ ...formData, github_token: e.target.value })}
                                    placeholder="ghp_..."
                                    className="transition"
                                    aria-required="true"
                                    invalid={showValidation && formErrors.githubToken}
                                    aria-describedby={
                                        showValidation && formErrors.githubToken
                                            ? "field-github-token-error field-github-token-hint"
                                            : "field-github-token-hint"
                                    }
                                />
                                {showValidation && formErrors.githubToken && (
                                    <FieldError id="field-github-token-error">Informe o token do GitHub.</FieldError>
                                )}
                                <p id="field-github-token-hint" className="mt-1.5 flex items-start gap-1.5 text-xs text-slate-400">
                                    <Lock className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
                                    <span>Usado só durante a execução. Não é salvo no banco de dados.</span>
                                </p>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 pt-3 border-t border-slate-700/50">
                            <div>
                                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                    Versão Java
                                </label>
                                <Select
                                    value={formData.java_version}
                                    onChange={(e) =>
                                        setFormData({
                                            ...formData,
                                            java_version: e.target.value as SearchFormData["java_version"],
                                        })
                                    }
                                >
                                    <option value="">Qualquer</option>
                                    <option value="6">Java 6</option>
                                    <option value="7">Java 7</option>
                                    <option value="8">Java 8</option>
                                    <option value="11">Java 11</option>
                                    <option value="17">Java 17</option>
                                    <option value="21">Java 21</option>
                                </Select>
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                    Stars
                                </label>
                                <TextInput
                                    type="text"
                                    value={formData.stars}
                                    onChange={(e) => setFormData({ ...formData, stars: e.target.value })}
                                    placeholder=">=100"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                    Forks
                                </label>
                                <TextInput
                                    type="text"
                                    value={formData.forks}
                                    onChange={(e) => setFormData({ ...formData, forks: e.target.value })}
                                    placeholder="10..50"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                    Tamanho
                                </label>
                                <TextInput
                                    type="text"
                                    value={formData.size}
                                    onChange={(e) => setFormData({ ...formData, size: e.target.value })}
                                    placeholder="<30000"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                    Criado desde
                                </label>
                                <TextInput
                                    icon={<Calendar />}
                                    type="date"
                                    value={formData.created}
                                    onChange={(e) => setFormData({ ...formData, created: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="border-t border-slate-700/50 pt-3">
                            <button
                                type="button"
                                onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
                                className="inline-flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-slate-50 transition cursor-pointer"
                            >
                                <SlidersHorizontal className="h-4 w-4 text-cyan-400" />
                                Filtros avançados
                                <ChevronDown
                                    className={`h-4 w-4 transition ${showAdvancedFilters ? "rotate-180" : ""}`}
                                />
                            </button>

                            {showAdvancedFilters && (
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Último push desde
                                        </label>
                                        <TextInput
                                            icon={<Calendar />}
                                            type="date"
                                            value={formData.pushed}
                                            onChange={(e) => setFormData({ ...formData, pushed: e.target.value })}
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Tópico
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.topic}
                                            onChange={(e) => setFormData({ ...formData, topic: e.target.value })}
                                            placeholder="spring"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Licença
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.license}
                                            onChange={(e) => setFormData({ ...formData, license: e.target.value })}
                                            placeholder="mit"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Visibilidade
                                        </label>
                                        <Select
                                            value={formData.visibility}
                                            onChange={(e) =>
                                                setFormData({
                                                    ...formData,
                                                    visibility: e.target.value as SearchFormData["visibility"],
                                                })
                                            }
                                        >
                                            <option value="">Qualquer</option>
                                            <option value="public">Público</option>
                                            <option value="private">Privado</option>
                                            <option value="internal">Interno</option>
                                        </Select>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Usuário
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.user}
                                            onChange={(e) => setFormData({ ...formData, user: e.target.value })}
                                            placeholder="octocat"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Organização
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.org}
                                            onChange={(e) => setFormData({ ...formData, org: e.target.value })}
                                            placeholder="github"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Repositório
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.repo}
                                            onChange={(e) => setFormData({ ...formData, repo: e.target.value })}
                                            placeholder="owner/name"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Seguidores
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.followers}
                                            onChange={(e) => setFormData({ ...formData, followers: e.target.value })}
                                            placeholder=">=100"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Quantidade de tópicos
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.topics}
                                            onChange={(e) => setFormData({ ...formData, topics: e.target.value })}
                                            placeholder=">=3"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Fork
                                        </label>
                                        <Select
                                            value={formData.fork}
                                            onChange={(e) =>
                                                setFormData({
                                                    ...formData,
                                                    fork: e.target.value as SearchFormData["fork"],
                                                })
                                            }
                                        >
                                            <option value="">Qualquer</option>
                                            <option value="false">Não</option>
                                            <option value="true">Sim</option>
                                            <option value="only">Somente forks</option>
                                        </Select>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Arquivado
                                        </label>
                                        <Select
                                            value={formData.archived}
                                            onChange={(e) =>
                                                setFormData({
                                                    ...formData,
                                                    archived: e.target.value as SearchFormData["archived"],
                                                })
                                            }
                                        >
                                            <option value="">Qualquer</option>
                                            <option value="false">Não</option>
                                            <option value="true">Sim</option>
                                        </Select>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Mirror
                                        </label>
                                        <Select
                                            value={formData.mirror}
                                            onChange={(e) =>
                                                setFormData({
                                                    ...formData,
                                                    mirror: e.target.value as SearchFormData["mirror"],
                                                })
                                            }
                                        >
                                            <option value="">Qualquer</option>
                                            <option value="false">Não</option>
                                            <option value="true">Sim</option>
                                        </Select>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Template
                                        </label>
                                        <Select
                                            value={formData.template}
                                            onChange={(e) =>
                                                setFormData({
                                                    ...formData,
                                                    template: e.target.value as SearchFormData["template"],
                                                })
                                            }
                                        >
                                            <option value="">Qualquer</option>
                                            <option value="false">Não</option>
                                            <option value="true">Sim</option>
                                        </Select>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Good first issues
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.good_first_issues}
                                            onChange={(e) =>
                                                setFormData({ ...formData, good_first_issues: e.target.value })
                                            }
                                            placeholder=">=2"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Help wanted issues
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.help_wanted_issues}
                                            onChange={(e) =>
                                                setFormData({ ...formData, help_wanted_issues: e.target.value })
                                            }
                                            placeholder=">=2"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Arquivo
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.filename}
                                            onChange={(e) => setFormData({ ...formData, filename: e.target.value })}
                                            placeholder="pom.xml"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Extensão
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.extension}
                                            onChange={(e) => setFormData({ ...formData, extension: e.target.value })}
                                            placeholder="xml"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Caminho
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.path}
                                            onChange={(e) => setFormData({ ...formData, path: e.target.value })}
                                            placeholder="src/main"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Ordenar por
                                        </label>
                                        <TextInput
                                            type="text"
                                            value={formData.sort}
                                            onChange={(e) => setFormData({ ...formData, sort: e.target.value })}
                                            placeholder="stars"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Direção
                                        </label>
                                        <Select
                                            value={formData.order}
                                            onChange={(e) =>
                                                setFormData({
                                                    ...formData,
                                                    order: e.target.value as SearchFormData["order"],
                                                })
                                            }
                                        >
                                            <option value="">Padrão</option>
                                            <option value="desc">Desc</option>
                                            <option value="asc">Asc</option>
                                        </Select>
                                    </div>

                                    <div>
                                        <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                            Itens por página
                                        </label>
                                        <TextInput
                                            type="number"
                                            min={1}
                                            max={100}
                                            value={formData.per_page}
                                            onChange={(e) => setFormData({ ...formData, per_page: Number(e.target.value) })}
                                        />
                                    </div>

                                    <div className="sm:col-span-2 lg:col-span-4">
                                        <span className="block text-xs font-semibold text-slate-300 mb-2">
                                            Buscar em
                                        </span>
                                        <div className="flex flex-wrap gap-3 text-sm text-slate-300">
                                            {(["name", "description", "readme", "topics"] as const).map((value) => (
                                                <Checkbox
                                                    key={value}
                                                    labelClassName="flex items-center gap-2 cursor-pointer"
                                                    checked={formData.search_in.includes(value)}
                                                    onChange={() => toggleSearchIn(value)}
                                                    label={value}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 pt-3 border-t border-slate-700/50">
                            <div>
                                <FieldLabel htmlFor="field-search-type" required>
                                    Tipo de Busca
                                </FieldLabel>
                                <Select
                                    id="field-search-type"
                                    aria-required="true"
                                    invalid={showValidation && formErrors.searchType}
                                    aria-describedby={showValidation && formErrors.searchType ? "field-search-type-error" : undefined}
                                    value={formData.search_type}
                                    onChange={(e) =>
                                        setFormData({ ...formData, search_type: e.target.value as "code" | "repositories" })
                                    }
                                >
                                    <option value="code">Code Search (busca no pom.xml)</option>
                                    <option value="repositories">Repository Search</option>
                                </Select>
                                {showValidation && formErrors.searchType && (
                                    <FieldError id="field-search-type-error">Selecione o tipo de busca.</FieldError>
                                )}
                            </div>

                            <div>
                                <FieldLabel htmlFor="field-max-repos" required>
                                    Limite de Repositórios
                                </FieldLabel>
                                <TextInput
                                    id="field-max-repos"
                                    type="number"
                                    min={1}
                                    value={formData.max_repos}
                                    onChange={(e) => setFormData({ ...formData, max_repos: Number(e.target.value) })}
                                    aria-required="true"
                                    invalid={showValidation && formErrors.maxRepos}
                                    aria-describedby={showValidation && formErrors.maxRepos ? "field-max-repos-error" : undefined}
                                />
                                {showValidation && formErrors.maxRepos && (
                                    <FieldError id="field-max-repos-error">Informe um número inteiro maior que zero.</FieldError>
                                )}
                            </div>

                            <div>
                                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                                    Estatísticas
                                </label>
                                <Select
                                    value={formData.statistics_scope}
                                    onChange={(e) =>
                                        setFormData({
                                            ...formData,
                                            statistics_scope: e.target.value as SearchFormData["statistics_scope"],
                                        })
                                    }
                                >
                                    <option value="accepted">Aceitos</option>
                                    <option value="all">Todos filtrados</option>
                                    <option value="eliminated">Eliminados</option>
                                </Select>
                            </div>

                            <div className="sm:col-span-2 lg:col-span-3 flex flex-wrap items-end justify-between gap-4">
                                <div className="space-y-2 pb-1">
                                    <Checkbox
                                        checked={formData.require_buildable}
                                        onChange={(e) =>
                                            setFormData({
                                                ...formData,
                                                require_buildable: e.target.checked,
                                                require_tests_passed: e.target.checked
                                                    ? formData.require_tests_passed
                                                    : false,
                                            })
                                        }
                                        label="Apenas repositórios buildáveis"
                                    />

                                    <Checkbox
                                        checked={formData.require_tests_passed}
                                        onChange={(e) =>
                                            setFormData({
                                                ...formData,
                                                require_tests_passed: e.target.checked,
                                                require_buildable: e.target.checked
                                                    ? true
                                                    : formData.require_buildable,
                                            })
                                        }
                                        label="Apenas com testes aprovados"
                                    />

                                    <Checkbox
                                        checked={formData.persist_eliminated_repositories}
                                        onChange={(e) =>
                                            setFormData({
                                                ...formData,
                                                persist_eliminated_repositories: e.target.checked,
                                            })
                                        }
                                        label="Salvar repositórios eliminados"
                                    />

                                    <Checkbox
                                        checked={formData.allow_jdk_upgrade}
                                        disabled={!analyzerWillRun}
                                        onChange={(e) =>
                                            setFormData({
                                                ...formData,
                                                allow_jdk_upgrade: e.target.checked,
                                            })
                                        }
                                        label="Permitir upgrade automático do JDK"
                                    />

                                    <Checkbox
                                        checked={formData.include_statistics}
                                        onChange={(e) =>
                                            setFormData({
                                                ...formData,
                                                include_statistics: e.target.checked,
                                            })
                                        }
                                        label="Retornar estatísticas"
                                    />
                                </div>

                                <div className="flex flex-col items-end gap-2">
                                    <Button
                                        type="submit"
                                        variant="cta"
                                        disabled={loading}
                                        className="px-5"
                                    >
                                        {loading ? (
                                            <>
                                                <Loader2 className="h-4 w-4 animate-spin" /> Minerando...
                                            </>
                                        ) : (
                                            <>
                                                <Play className="h-4 w-4 fill-current" /> Iniciar Mineração
                                            </>
                                        )}
                                    </Button>
                                    <p className="text-xs text-slate-400">
                                        <span className="text-rose-400" aria-hidden="true">*</span> Campo obrigatório para iniciar a mineração
                                    </p>
                                </div>
                            </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-700/60 bg-slate-900/70 px-4 py-3 text-xs text-slate-300">
                            <span className="inline-flex items-center gap-2 font-semibold text-slate-100">
                                <Database className="h-4 w-4 text-cyan-400" />
                                Execução
                            </span>
                            <span>
                                {runStatus
                                    ? `Status: ${runStatusLabel(runStatus.status)}${runStatus.progress_stage ? ` / ${progressStageLabel(runStatus.progress_stage)}` : ""}`
                                    : formData.require_tests_passed
                                        ? "Build + detecção e execução de testes"
                                        : isBuildOnlyMode
                                            ? "Somente build, sem detectar testes"
                                            : "Somente busca, sem analyzer"}
                            </span>
                            <span className="text-slate-400">
                                {analyzerWillRun
                                    ? formData.allow_jdk_upgrade
                                        ? "análise com upgrade de JDK permitido"
                                        : "análise com JDK exato"
                                    : "analyzer desligado"}
                            </span>
                            {!formData.persist_eliminated_repositories && (
                                <span className="text-slate-400">
                                    eliminados não serão persistidos
                                </span>
                            )}
                            {loading && runStatus && (
                                <span className="text-slate-400">
                                    {progressCurrent}/{progressTotal || "?"} repositórios analisados ({progressPercent}%)
                                </span>
                            )}
                        </div>

                        {analyzerWillRun && (
                            <div className={`rounded-lg border px-4 py-3 text-xs ${
                                formData.allow_jdk_upgrade
                                    ? "border-amber-500/20 bg-amber-500/10 text-amber-100"
                                    : "border-emerald-500/20 bg-emerald-500/10 text-emerald-100"
                            }`}>
                                <div className="flex items-start gap-2">
                                    <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${
                                        formData.allow_jdk_upgrade ? "text-amber-400" : "text-emerald-400"
                                    }`} />
                                    <div>
                                        <p className={`font-semibold ${
                                            formData.allow_jdk_upgrade ? "text-amber-200" : "text-emerald-200"
                                        }`}>
                                            {formData.allow_jdk_upgrade
                                                ? "Upgrade de JDK permitido"
                                                : "JDK exato obrigatório"}
                                        </p>
                                        <p className={`mt-1 leading-relaxed ${
                                            formData.allow_jdk_upgrade ? "text-amber-100/80" : "text-emerald-100/80"
                                        }`}>
                                            {formData.allow_jdk_upgrade
                                                ? "Ao compilar ou testar, o backend pode usar um JDK mais novo que a versão declarada para iniciar o Maven ou atender ao pom.xml. A tabela mantém a versão declarada e mostra o JDK efetivo usado."
                                                : "Ao compilar ou testar, o backend usa somente o JDK da versão selecionada ou detectada. Se o Maven precisar de uma versão maior, o repositório é eliminado."}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </form>
                </section>

                {loading && runStatus && (
                    <div role="status" aria-live="polite" className="rounded-lg border border-slate-700 bg-slate-800 px-4 py-3">
                        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-slate-300">
                            <span className="font-semibold text-slate-100">
                                Run #{runStatus.id} {runStatus.status === "completed" ? "carregada" : "em andamento"}
                            </span>
                            <span>
                                {progressCurrent}/{progressTotal || "?"} processados · {runStatus.accepted_repositories} aceitos · {runStatus.eliminated_repositories} eliminados
                            </span>
                        </div>
                        <div className="mt-3 h-2 rounded-full bg-slate-900 overflow-hidden">
                            <div
                                className="h-full bg-cyan-500 transition-all"
                                style={{ width: `${progressPercent}%` }}
                            />
                        </div>
                    </div>
                )}

                {(repositories.length > 0 || lastRunId !== null) && (
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
                            {lastRunId !== null && (
                                <span className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                                    <Database className="h-4 w-4 text-cyan-400" />
                                    Run #{lastRunId}
                                </span>
                            )}
                            <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                                Total da resposta: {lastTotal}
                            </span>
                            {runStatus && (
                                <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                                    {runStatusLabel(runStatus.status)}
                                    {runStatus.progress_stage ? ` / ${progressStageLabel(runStatus.progress_stage)}` : ""}
                                </span>
                            )}
                            <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                                {lastRunIncludedTests ? "Testes analisados" : "Testes ignorados"}
                            </span>
                            {runStatus && (
                                <>
                                    <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                                        Página {runStatus.page_cursor ?? 1} / índice {runStatus.last_processed_index ?? 0}
                                    </span>
                                    <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                                        Lote {runStatus.batch_size ?? "-"}
                                    </span>
                                    <span className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2">
                                        Aceitação {Math.round((runStatus.acceptance_rate ?? 0) * 100)}%
                                    </span>
                                    {runStatus && !canResumeRun && Boolean(runStatus.exhausted) && (
                                        <span className="inline-flex w-full items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs font-semibold leading-5 text-amber-200">
                                            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
                                            <span>
                                                Não é possível retomar esta busca. Todas as páginas disponíveis no GitHub para estes filtros já foram esgotadas. Para encontrar mais repositórios, inicie uma nova busca com outra query ou filtros diferentes.
                                            </span>
                                        </span>
                                    )}
                                </>
                            )}
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                            {canCancelRun && (
                                <Button type="button" variant="danger" onClick={handleCancelRun}>
                                    <XCircle className="h-4 w-4" />
                                    Cancelar
                                </Button>
                            )}
                            {canResumeRun && (
                                <Button
                                    type="button"
                                    variant="primary"
                                    onClick={handleResumeRun}
                                    disabled={loading}
                                    title="A retomada usa o token configurado no servidor, pois o token digitado não é salvo."
                                >
                                    <Play className="h-4 w-4" />
                                    Retomar consulta
                                </Button>
                            )}
                            <Button
                                type="button"
                                variant="secondary"
                                onClick={onOpenStatistics}
                                disabled={!statistics}
                                title={!statistics ? "Nenhuma estatística carregada ainda" : undefined}
                            >
                                <SlidersHorizontal className="h-4 w-4 text-primary-400" />
                                Ver estatísticas
                            </Button>
                        </div>
                    </div>
                )}

                {/* Métricas Resumidas */}
                {repositories.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                        <Card padding="sm" className="shadow-sm">
                            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">Total Encontrado</span>
                            <p className="text-2xl font-bold text-neutral-100 mt-1">{repositories.length}</p>
                        </Card>
                        <Card padding="sm" className="shadow-sm">
                            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">Taxa de Compilação</span>
                            <p className="text-2xl font-bold text-success-400 mt-1">{metrics.compiled}%</p>
                        </Card>
                        <Card padding="sm" className="shadow-sm">
                            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">Testes com Sucesso</span>
                            <p className="text-2xl font-bold text-primary-400 mt-1">{metrics.passed}%</p>
                        </Card>
                        <Card padding="sm" className="shadow-sm">
                            <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">Upgrades de JDK</span>
                            <p className="text-2xl font-bold text-warning-400 mt-1">{metrics.upgraded}</p>
                            <p className="text-xs text-neutral-400 mt-1">
                                JDK efetivo diferente da versão declarada
                            </p>
                        </Card>
                    </div>
                )}

                {/* Tabela de Resultados */}
                <section className="bg-slate-800/80 border border-slate-700/60 rounded-xl overflow-hidden shadow-md">
                    {/* Barra de Filtros Locais */}
                    <div className="p-4 border-b border-slate-700/60 bg-slate-900/50 flex flex-wrap items-center justify-between gap-4">
                        <div className="flex-1 max-w-sm">
                            <TextInput
                                icon={<Filter />}
                                type="text"
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                placeholder="Filtrar por nome do repositório..."
                                aria-label="Filtrar por nome do repositório"
                            />
                        </div>

                        <div className="flex items-center gap-4 text-xs font-medium">
                            <div className="flex items-center gap-2">
                                <span className="text-slate-400" id="local-java-filter-label">Java:</span>
                                <Select
                                    aria-labelledby="local-java-filter-label"
                                    value={selectedJavaVersion}
                                    onChange={(e) => setSelectedJavaVersion(e.target.value)}
                                >
                                    <option value="ALL">Todas</option>
                                    {javaVersionOptions.map((version) => (
                                        <option key={version} value={version}>Java {version}</option>
                                    ))}
                                </Select>
                            </div>

                            <Checkbox
                                label="Buildáveis"
                                checked={formData.require_buildable}
                                onChange={(e) =>
                                    setFormData({
                                        ...formData,
                                        require_buildable: e.target.checked,
                                    })
                                }
                            />

                            <Checkbox
                                label="Testes OK"
                                checked={formData.require_tests_passed}
                                onChange={(e) =>
                                    setFormData({
                                        ...formData,
                                        require_tests_passed: e.target.checked,
                                    })
                                }
                            />
                        </div>
                    </div>

                    {/* Listagem */}
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-xs">
                            <thead className="bg-slate-900/80 text-slate-400 border-b border-slate-700/60 uppercase tracking-wider font-semibold">
                                <tr>
                                    <th className="py-3.5 px-4">Repositório</th>
                                    <th className="py-3.5 px-4">Versão Java</th>
                                    <th className="py-3.5 px-4">Compilação</th>
                                    <th className="py-3.5 px-4">Testes</th>
                                    <th className="py-3.5 px-4">Status Final</th>
                                    <th className="py-3.5 px-4">Origem</th>
                                    <th className="py-3.5 px-4 text-right">Ações</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-700/40">
                                {loading ? (
                                    <tr>
                                        <td colSpan={7} className="py-10 text-center text-slate-300">
                                            <span className="inline-flex items-center gap-2">
                                                <Loader2 className="h-4 w-4 animate-spin text-cyan-400" />
                                                Minerando repositórios...
                                            </span>
                                        </td>
                                    </tr>
                                ) : filteredRepositories.length === 0 ? (
                                    <tr>
                                        <td colSpan={7} className="py-10 text-center text-slate-400">
                                            {lastRunId === null
                                                ? "Nenhuma busca realizada ainda. Preencha o formulário acima e inicie uma mineração."
                                                : "Nenhum repositório encontrado para os filtros atuais."}
                                        </td>
                                    </tr>
                                ) : (
                                    filteredRepositories.map((repo) => (
                                        <tr key={`${repo.name}::${repo.matched_file ?? "root"}::${repo.commit_sha ?? ""}`} className="hover:bg-slate-700/30 transition">
                                            <td className="py-3 px-4 font-mono font-medium text-slate-100">
                                                {repo.name}
                                            </td>

                                            <td className="py-3 px-4">
                                                <div className="flex items-center gap-1.5">
                                                    <span className="bg-slate-900 border border-slate-700 text-slate-300 px-2 py-0.5 rounded font-mono">
                                                        JDK {repo.effective_java_version || repo.java_version || "?"}
                                                    </span>
                                                    {repo.effective_java_version &&
                                                        repo.java_version &&
                                                        repo.effective_java_version !== repo.java_version && (
                                                            <span
                                                                className="text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 px-1.5 py-0.2 rounded"
                                                                title={`Declarado: Java ${repo.java_version}`}
                                                            >
                                                                Upgraded
                                                            </span>
                                                        )}
                                                </div>
                                            </td>

                                            <td className="py-3 px-4">
                                                {!repo.analyzed ? (
                                                    <span className="text-slate-400">Não analisado</span>
                                                ) : repo.compiled ? (
                                                    <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                                                        <CheckCircle2 className="h-3.5 w-3.5" /> OK
                                                    </span>
                                                ) : (
                                                    <span className="inline-flex items-center gap-1 text-rose-400 font-medium">
                                                        <XCircle className="h-3.5 w-3.5" /> Falhou
                                                    </span>
                                                )}
                                                {repo.compile_duration_seconds !== null && repo.compile_duration_seconds !== undefined && (
                                                    <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                                                        {formatDuration(repo.compile_duration_seconds)}
                                                    </div>
                                                )}
                                            </td>

                                            <td className="py-3 px-4">
                                                {!lastRunIncludedTests ? (
                                                    <span className="text-slate-400">Ignorado</span>
                                                ) : !repo.has_tests ? (
                                                    <span className="text-slate-400">Sem testes</span>
                                                ) : repo.tests_passed ? (
                                                    <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                                                        <CheckCircle2 className="h-3.5 w-3.5" /> Passaram
                                                    </span>
                                                ) : (
                                                    <span className="inline-flex items-center gap-1 text-rose-400 font-medium">
                                                        <XCircle className="h-3.5 w-3.5" /> Falharam
                                                    </span>
                                                )}
                                                {repo.test_duration_seconds !== null && repo.test_duration_seconds !== undefined && (
                                                    <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                                                        {formatDuration(repo.test_duration_seconds)}
                                                    </div>
                                                )}
                                            </td>

                                            <td className="py-3 px-4">
                                                {!repo.analyzed ? (
                                                    <span className="text-slate-400">Minerado</span>
                                                ) : repo.eliminated ? (
                                                    <span className="inline-flex items-center gap-1 bg-rose-500/10 text-rose-400 border border-rose-500/20 px-2 py-0.5 rounded text-[11px] font-medium">
                                                        <AlertTriangle className="h-3 w-3" />
                                                        {repo.error_stage || "Eliminado"}
                                                    </span>
                                                ) : (
                                                    <span className="inline-flex items-center gap-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded text-[11px] font-medium">
                                                        Aprovado
                                                    </span>
                                                )}
                                            </td>

                                            <td className="py-3 px-4">
                                                <div className="max-w-44 space-y-1 text-[11px] text-slate-400">
                                                    {repo.matched_filter && (
                                                        <div className="truncate" title={repo.matched_filter}>
                                                            {repo.matched_filter}
                                                        </div>
                                                    )}
                                                    {repo.matched_file && (
                                                        <div className="truncate font-mono" title={repo.matched_file}>
                                                            {repo.matched_file}
                                                        </div>
                                                    )}
                                                    {repo.commit_sha && (
                                                        <div className="font-mono text-slate-400">
                                                            {repo.commit_sha.slice(0, 7)}
                                                        </div>
                                                    )}
                                                </div>
                                            </td>

                                            <td className="py-3 px-4 text-right space-x-2">
                                                <button
                                                    type="button"
                                                    onClick={() => setSelectedRepoDetails(repo)}
                                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-700/60 hover:bg-slate-700 text-slate-200 border border-slate-600 transition cursor-pointer font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                                                    title="Ver detalhes de testes e tempos"
                                                    aria-label={`Ver detalhes de ${repo.name}`}
                                                >
                                                    <Info className="h-3 w-3 text-slate-400" /> Detalhes
                                                </button>
                                                <a
                                                    href={repo.repository_url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 transition font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                                                    aria-label={`Abrir ${repo.name} no GitHub`}
                                                >
                                                    <ExternalLink className="h-3 w-3" /> Link
                                                </a>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </section>

                {/* Modal de Detalhes */}
                {selectedRepoDetails && (
                    <Modal
                        open={Boolean(selectedRepoDetails)}
                        onClose={() => setSelectedRepoDetails(null)}
                        titleId="repo-detail-title"
                        title={
                            <>
                                <Info className="h-4 w-4 text-cyan-400" />
                                <span>Detalhes: {selectedRepoDetails.name}</span>
                            </>
                        }
                    >
                        <>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {selectedRepoDetails.compile_duration_seconds !== null && selectedRepoDetails.compile_duration_seconds !== undefined && (
                                        <div className="bg-slate-800/60 border border-slate-700/60 rounded-lg p-3">
                                            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                                                <Clock className="h-3.5 w-3.5 text-amber-400" /> Tempo de compilação
                                            </div>
                                            <p className="text-lg font-bold text-slate-100 font-mono">
                                                {formatDuration(selectedRepoDetails.compile_duration_seconds)}
                                            </p>
                                            <p className="text-[11px] text-slate-400 mt-0.5">Do início ao fim da etapa de build.</p>
                                        </div>
                                    )}
                                    <div className="bg-slate-800/60 border border-slate-700/60 rounded-lg p-3">
                                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                                            <Clock className="h-3.5 w-3.5 text-amber-400" /> Tempo de testagem
                                        </div>
                                        <p className="text-lg font-bold text-slate-100 font-mono">
                                            {formatDuration(selectedRepoDetails.test_duration_seconds)}
                                        </p>
                                        <p className="text-[11px] text-slate-400 mt-0.5">Do início ao fim da etapa de testes.</p>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    <div>
                                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                                            <TestTube2 className="h-3.5 w-3.5 text-cyan-400" /> Frameworks de teste
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {splitTags(selectedRepoDetails.test_frameworks).length > 0 ? (
                                                splitTags(selectedRepoDetails.test_frameworks).map((tag) => (
                                                    <span key={tag} className="bg-slate-900 border border-slate-700 text-slate-300 px-2 py-0.5 rounded text-[11px] font-mono">
                                                        {tag}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-slate-400 text-xs">Nenhum detectado</span>
                                            )}
                                        </div>
                                    </div>

                                    <div>
                                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                                            <Code2 className="h-3.5 w-3.5 text-cyan-400" /> Bibliotecas de mock
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {splitTags(selectedRepoDetails.mock_libraries).length > 0 ? (
                                                splitTags(selectedRepoDetails.mock_libraries).map((tag) => (
                                                    <span key={tag} className="bg-slate-900 border border-slate-700 text-slate-300 px-2 py-0.5 rounded text-[11px] font-mono">
                                                        {tag}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-slate-400 text-xs">Nenhuma detectada</span>
                                            )}
                                        </div>
                                    </div>

                                    <div>
                                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> Bibliotecas de asserção
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {splitTags(selectedRepoDetails.assertion_libraries).length > 0 ? (
                                                splitTags(selectedRepoDetails.assertion_libraries).map((tag) => (
                                                    <span key={tag} className="bg-slate-900 border border-slate-700 text-slate-300 px-2 py-0.5 rounded text-[11px] font-mono">
                                                        {tag}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-slate-400 text-xs">Nenhuma detectada</span>
                                            )}
                                        </div>
                                    </div>

                                    <div>
                                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                                            <Layers3 className="h-3.5 w-3.5 text-cyan-400" /> Ferramentas de teste de integração
                                        </div>
                                        <div className="flex flex-wrap gap-1.5">
                                            {splitTags(selectedRepoDetails.integration_test_tools).length > 0 ? (
                                                splitTags(selectedRepoDetails.integration_test_tools).map((tag) => (
                                                    <span key={tag} className="bg-slate-900 border border-slate-700 text-slate-300 px-2 py-0.5 rounded text-[11px] font-mono">
                                                        {tag}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-slate-400 text-xs">Nenhuma detectada</span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {selectedRepoDetails.error_message && (
                                    <div>
                                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                                            <Terminal className="h-3.5 w-3.5 text-rose-400" /> Logs de erro
                                        </div>
                                        <div className="p-3 font-mono text-xs text-rose-300 bg-slate-950 border border-slate-800 rounded-lg leading-relaxed whitespace-pre-wrap max-h-56 overflow-y-auto">
                                            {selectedRepoDetails.error_message}
                                        </div>
                                    </div>
                                )}
                        </>
                    </Modal>
                )}

            </div>
        </div>
    );
}
