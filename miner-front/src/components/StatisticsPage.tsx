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
import type { CountPercentageStat, DurationStat, RateStat, RepositoryStatistics } from "../models/types";

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
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {funnelItems.map(([label, value]) => (
                                <div key={label} className="bg-slate-900/60 border border-slate-700/60 rounded-lg p-4">
                                    <span className="text-xs text-slate-400">{label}</span>
                                    <p className="text-xl font-bold text-slate-100 mt-1">{value}</p>
                                </div>
                            ))}
                        </div>
                    </Panel>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                    <Panel title="Java declarado" icon={<Code2 className="h-4 w-4 text-cyan-400" />}>
                        <CountList items={declaredJavaVersions} emptyText="Sem versões Java declaradas no escopo." />
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
