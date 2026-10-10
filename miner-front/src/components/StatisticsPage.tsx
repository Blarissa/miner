import {
    BarChart3,
    CheckCircle2,
    Code2,
    GitBranch,
    Layers3,
    TestTube2,
    XCircle,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { CountPercentageStat, DurationStat, OutcomeStat, RateStat, RepositoryStatistics } from "../models/types";

interface StatisticsPageProps {
    statistics: RepositoryStatistics | null;
    showEliminatedRepositoryStats: boolean;
}

function scopeLabel(scope: RepositoryStatistics["scope"]) {
    if (scope === "all") return "Todos filtrados";
    if (scope === "eliminated") return "Eliminados";
    return "Aceitos";
}

function SummaryCard({
    label,
    value,
    detail,
    tone = "default",
}: {
    label: string;
    value: string | number;
    detail?: string;
    tone?: "default" | "success" | "danger" | "warning";
}) {
    const toneClass = {
        default: "text-slate-100",
        success: "text-emerald-400",
        danger: "text-rose-400",
        warning: "text-amber-400",
    }[tone];

    return (
        <div className="bg-slate-800/80 border border-slate-700/60 rounded-xl p-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                {label}
            </span>
            <p className={`text-2xl font-bold mt-1 ${toneClass}`}>{value}</p>
            {detail && <p className="text-xs text-slate-400 mt-1">{detail}</p>}
        </div>
    );
}

function FunnelChart({ steps }: { steps: ReadonlyArray<readonly [string, number]> }) {
    const first = steps[0]?.[1] ?? 0;

    if (first <= 0) {
        return <p className="text-sm text-slate-400">Sem repositórios pesquisados no escopo.</p>;
    }

    return (
        <ol className="space-y-2" aria-label="Funil de análise">
            {steps.map(([label, value], index) => {
                const previous = index === 0 ? value : steps[index - 1][1];
                const widthPercent = Math.max((value / first) * 100, value > 0 ? 2 : 0);
                const retained = previous > 0 ? Math.round((value / previous) * 100) : 0;
                return (
                    <li key={label} className="grid grid-cols-[7rem_1fr_9rem] items-center gap-3 text-xs">
                        <span className="text-slate-300 truncate">{label}</span>
                        <div className="h-6 rounded bg-slate-900 overflow-hidden">
                            <div
                                className="h-full rounded bg-cyan-500/80"
                                style={{ width: `${widthPercent}%` }}
                            />
                        </div>
                        <span className="font-mono text-slate-300 text-right">
                            {value}
                            {index > 0 && (
                                <span className="text-slate-500"> · {retained}% da etapa anterior</span>
                            )}
                        </span>
                    </li>
                );
            })}
        </ol>
    );
}

const OUTCOME_SEGMENTS = [
    { key: "tests_passed", label: "Testes passaram", className: "bg-emerald-500" },
    { key: "tests_failed", label: "Testes falharam", className: "bg-amber-500" },
    { key: "no_tests", label: "Sem testes", className: "bg-slate-500" },
    { key: "not_compiled", label: "Não compilou", className: "bg-rose-500" },
    { key: "not_analyzed", label: "Não analisado", className: "bg-slate-700" },
] as const;

function OutcomeStackedBars({ rows }: { rows: OutcomeStat[] }) {
    const visibleRows = rows.filter((row) => row.value.trim().toLowerCase() !== "unknown" || row.total > 0);

    if (visibleRows.length === 0) {
        return <p className="text-sm text-slate-400">Sem dados de resultado por versão do Java no escopo.</p>;
    }

    return (
        <div className="space-y-3">
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-300">
                {OUTCOME_SEGMENTS.map((segment) => (
                    <li key={segment.key} className="inline-flex items-center gap-1.5">
                        <span className={`h-2.5 w-2.5 rounded-sm ${segment.className}`} />
                        {segment.label}
                    </li>
                ))}
            </ul>
            {visibleRows.map((row) => (
                <div key={row.value} className="grid grid-cols-[5rem_1fr_3rem] items-center gap-3 text-xs">
                    <span className="text-slate-300 truncate">Java {row.value}</span>
                    <div
                        className="flex h-5 overflow-hidden rounded bg-slate-900"
                        role="img"
                        aria-label={OUTCOME_SEGMENTS.map((segment) => `${segment.label}: ${row[segment.key]}`).join(", ")}
                    >
                        {OUTCOME_SEGMENTS.map((segment) =>
                            row[segment.key] > 0 ? (
                                <div
                                    key={segment.key}
                                    className={segment.className}
                                    style={{ width: `${(row[segment.key] / row.total) * 100}%` }}
                                    title={`${segment.label}: ${row[segment.key]}`}
                                />
                            ) : null,
                        )}
                    </div>
                    <span className="font-mono text-slate-400 text-right">{row.total}</span>
                </div>
            ))}
        </div>
    );
}

function BarRow({ label, value, percentage }: { label: string; value: number; percentage: number }) {
    return (
        <div className="space-y-1">
            <div className="flex items-center justify-between gap-3 text-xs">
                <span className="text-slate-300 truncate">{label}</span>
                <span className="font-mono text-slate-400">
                    {value} ({percentage}%)
                </span>
            </div>
            <div className="h-2 rounded-full bg-slate-900 overflow-hidden">
                <div
                    className="h-full rounded-full bg-cyan-500"
                    style={{ width: `${Math.min(Math.max(percentage, 0), 100)}%` }}
                />
            </div>
        </div>
    );
}

function CountList({ items, emptyText }: { items: CountPercentageStat[]; emptyText: string }) {
    const visibleItems = items.filter((item) => item.value.trim().toLowerCase() !== "unknown");

    const hiddenCount = items
        .filter((item) => item.value.trim().toLowerCase() === "unknown")
        .reduce((total, item) => total + item.count, 0);

    if (visibleItems.length === 0) {
        return <p className="text-sm text-slate-400">{emptyText}</p>;
    }

    return (
        <div className="space-y-3">
            {visibleItems.map((item) => (
                <BarRow
                    key={item.value}
                    label={item.value}
                    value={item.count}
                    percentage={item.percentage}
                />
            ))}
            {hiddenCount > 0 && (
                <p className="border-t border-slate-700/60 pt-2 text-xs text-slate-400">
                    Desconhecido (não exibido): {hiddenCount}. As porcentagens acima consideram todos os itens.
                </p>
            )}
        </div>
    );
}

function RateList({ items, emptyText }: { items: RateStat[]; emptyText: string }) {
    if (items.length === 0) {
        return <p className="text-sm text-slate-400">{emptyText}</p>;
    }

    return (
        <div className="space-y-3">
            {items.map((item) => (
                <BarRow
                    key={item.value}
                    label={`${item.value} · ${item.success}/${item.total}`}
                    value={item.success}
                    percentage={item.success_rate}
                />
            ))}
        </div>
    );
}

function secondsLabel(value: number) {
    return `${value.toFixed(2)}s`;
}

function DurationSummary({
    title,
    duration,
}: {
    title: string;
    duration?: DurationStat;
}) {
    if (!duration || duration.count === 0) {
        return null;
    }

    return (
        <div className="bg-slate-900/60 border border-slate-700/60 rounded-lg p-4">
            <span className="text-xs text-slate-400">{title}</span>
            <p className="text-xl font-bold text-slate-100 mt-1">
                {secondsLabel(duration.average_seconds)}
            </p>
            <div className="grid grid-cols-2 gap-2 mt-3 text-xs text-slate-400">
                <span>Total: {secondsLabel(duration.total_seconds)}</span>
                <span>Execuções: {duration.count}</span>
                <span>Mín: {secondsLabel(duration.min_seconds)}</span>
                <span>Máx: {secondsLabel(duration.max_seconds)}</span>
            </div>
        </div>
    );
}

function Panel({
    title,
    icon,
    children,
}: {
    title: string;
    icon: ReactNode;
    children: ReactNode;
}) {
    return (
        <section className="bg-slate-800/80 border border-slate-700/60 rounded-xl p-5">
            <div className="flex items-center gap-2 mb-4">
                {icon}
                <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
            </div>
            {children}
        </section>
    );
}

export default function StatisticsPage({
    statistics,
    showEliminatedRepositoryStats,
}: StatisticsPageProps) {
    if (!statistics) {
        return (
            <div className="min-h-screen bg-slate-950 text-slate-200 p-6 sm:p-10 font-sans">
                <div className="max-w-7xl mx-auto space-y-7">
                    <div className="bg-slate-800/80 border border-slate-700/60 rounded-xl p-8 text-center">
                        <BarChart3 className="h-8 w-8 text-slate-500 mx-auto mb-3" />
                        <p className="text-slate-300 font-medium">Nenhuma estatística disponível ainda.</p>
                        <p className="mt-1 text-sm text-slate-400">
                            As estatísticas ficam disponíveis após uma mineração (ou ao carregar uma execução anterior).
                        </p>
                        <div className="mt-5 flex flex-wrap justify-center gap-3">
                            <Link
                                to="/dashboard"
                                className="inline-flex items-center rounded-lg bg-orange-500 px-4 py-2 text-sm font-semibold text-slate-900 transition-colors hover:bg-orange-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-300"
                            >
                                Ir para Mineração
                            </Link>
                            <Link
                                to="/"
                                className="inline-flex items-center rounded-lg border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                            >
                                Carregar execução por Run ID
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    const funnel = statistics.analysis_funnel;
    const summary = statistics.summary;
    const declaredJavaVersions = statistics.declared_java_versions ?? statistics.java_versions;
    const javaVersionComparison = statistics.java_declared_effective_comparison ?? [];
    const hasJavaUpgrade = javaVersionComparison.some(
        (item) => item.value.trim().toLowerCase() !== "mesma versao" && item.count > 0
    );
    const testFrameworks = statistics.test_frameworks ?? [];
    const mockLibraries = statistics.mock_libraries ?? [];
    const assertionLibraries = statistics.assertion_libraries ?? [];
    const integrationTestTools = statistics.integration_test_tools ?? [];
    const stageDurations = statistics.stage_durations;
    const hasCompilationDuration = Boolean(stageDurations?.compilation?.count);
    const hasTestingDuration = Boolean(stageDurations?.testing?.count);
    const hasAnyStageDuration = hasCompilationDuration || hasTestingDuration;

    const funnelItems = [
        ["Pesquisados", funnel.searched],
        ["Analisados", funnel.analyzed],
        ["Compilaram", funnel.compiled],
        ["Com testes", funnel.has_tests],
        ["Testes OK", funnel.tests_passed],
        ["Aceitos", funnel.accepted],
    ] as const;

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200 p-6 sm:p-10 font-sans">
            <div className="max-w-7xl mx-auto space-y-7">
                <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-5">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight text-slate-50 flex items-center gap-2.5">
                            <BarChart3 className="h-7 w-7 text-cyan-400" />
                            Estatísticas da Mineração
                        </h1>
                    </div>
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                        Escopo: {scopeLabel(statistics.scope)}
                    </span>
                </header>

                <div
                    className={`grid grid-cols-1 sm:grid-cols-2 gap-4 ${
                        showEliminatedRepositoryStats ? "lg:grid-cols-5" : "lg:grid-cols-2"
                    }`}
                >
                    <SummaryCard label="Total no escopo" value={statistics.total} />
                    <SummaryCard label="Total analisado" value={funnel.analyzed} />
                    {showEliminatedRepositoryStats && (
                        <>
                            <SummaryCard
                                label="Taxa de testes"
                                value={`${summary.test_success_rate_over_searched}%`}
                                detail="sobre os pesquisados"
                                tone="success"
                            />
                            <SummaryCard
                                label="Eliminados"
                                value={`${summary.eliminated_rate}%`}
                                detail={`${summary.eliminated} repositórios`}
                                tone="danger"
                            />
                            <SummaryCard
                                label="Com testes"
                                value={`${statistics.test_repository_relation.with_tests_rate}%`}
                                detail={`${summary.has_tests} repositórios`}
                                tone="warning"
                            />
                        </>
                    )}
                </div>

                {showEliminatedRepositoryStats && (
                    <Panel title="Funil de análise" icon={<Layers3 className="h-4 w-4 text-cyan-400" />}>
                        <FunnelChart steps={funnelItems} />
                    </Panel>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    <Panel title="Java declarado" icon={<Code2 className="h-4 w-4 text-cyan-400" />}>
                        <CountList items={declaredJavaVersions} emptyText="Sem versões Java declaradas no escopo." />
                    </Panel>

                    <Panel title="Resultado por versão do Java" icon={<BarChart3 className="h-4 w-4 text-cyan-400" />}>
                        <OutcomeStackedBars rows={statistics.outcome_by_java_version ?? []} />
                    </Panel>

                    {hasJavaUpgrade && (
                        <Panel title="Java declarado x efetivo" icon={<BarChart3 className="h-4 w-4 text-cyan-400" />}>
                            <CountList items={javaVersionComparison} emptyText="Sem comparação de versões no escopo." />
                        </Panel>
                    )}

                    <Panel title="Frameworks de teste" icon={<TestTube2 className="h-4 w-4 text-cyan-400" />}>
                        <CountList items={testFrameworks} emptyText="Sem frameworks de teste no escopo." />
                    </Panel>

                    <Panel title="Bibliotecas de mock" icon={<Code2 className="h-4 w-4 text-cyan-400" />}>
                        <CountList items={mockLibraries} emptyText="Sem bibliotecas de mock no escopo." />
                    </Panel>

                    <Panel title="Bibliotecas de asserção" icon={<CheckCircle2 className="h-4 w-4 text-emerald-400" />}>
                        <CountList items={assertionLibraries} emptyText="Sem bibliotecas de asserção no escopo." />
                    </Panel>

                    <Panel title="Ferramentas de teste de integração" icon={<Layers3 className="h-4 w-4 text-cyan-400" />}>
                        <CountList items={integrationTestTools} emptyText="Sem ferramentas de integração no escopo." />
                    </Panel>

                    <Panel title="Tempo por etapa" icon={<GitBranch className="h-4 w-4 text-amber-400" />}>
                        {hasAnyStageDuration ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                {hasCompilationDuration && (
                                    <DurationSummary title="Compilação média" duration={stageDurations?.compilation} />
                                )}
                                {hasTestingDuration && (
                                    <DurationSummary title="Testagem média" duration={stageDurations?.testing} />
                                )}
                            </div>
                        ) : (
                            <p className="text-sm text-slate-400">Sem tempos registrados.</p>
                        )}
                    </Panel>

                    {showEliminatedRepositoryStats && (
                        <>
                            <Panel title="Relação com testes" icon={<TestTube2 className="h-4 w-4 text-cyan-400" />}>
                                <CountList
                                    items={statistics.test_repository_relation.distribution}
                                    emptyText="Sem dados de testes no escopo."
                                />
                            </Panel>

                            <Panel title="Maiores estágios de erro" icon={<XCircle className="h-4 w-4 text-rose-400" />}>
                                <CountList items={statistics.error_stages} emptyText="Sem erros no escopo." />
                            </Panel>

                            <Panel title="Aceitos x eliminados" icon={<CheckCircle2 className="h-4 w-4 text-emerald-400" />}>
                                <div className="space-y-3">
                                    <BarRow
                                        label="Aceitos"
                                        value={statistics.elimination.accepted}
                                        percentage={statistics.elimination.accepted_rate}
                                    />
                                    <BarRow
                                        label="Eliminados"
                                        value={statistics.elimination.eliminated}
                                        percentage={statistics.elimination.eliminated_rate}
                                    />
                                </div>
                            </Panel>

                            <Panel title="Compilaram e reprovaram nos testes por Java" icon={<GitBranch className="h-4 w-4 text-amber-400" />}>
                                <RateList
                                    items={statistics.compiled_but_tests_failed_by_java_version}
                                    emptyText="Sem repositórios nessa condição."
                                />
                            </Panel>

                            <Panel title="Taxa de compilação por build" icon={<BarChart3 className="h-4 w-4 text-cyan-400" />}>
                                <RateList
                                    items={statistics.compilation_rate_by_build_tool}
                                    emptyText="Sem dados de build no escopo."
                                />
                            </Panel>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
