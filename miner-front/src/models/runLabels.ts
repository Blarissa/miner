/**
 * Rótulos em português para os valores técnicos de status e etapa de uma execução
 * (campos `status` e `progress_stage` devolvidos pelo backend).
 * Valores desconhecidos são exibidos como vieram, para nunca esconder informação.
 */

export const RUN_STATUS_LABELS: Record<string, string> = {
    queued: "Na fila",
    running: "Em execução",
    completed: "Concluída",
    failed: "Falhou",
    cancelled: "Cancelada",
};

export const PROGRESS_STAGE_LABELS: Record<string, string> = {
    mining: "Buscando no GitHub",
    mined: "Filtrando candidatos",
    analyzing: "Analisando (build e testes)",
    building_statistics: "Calculando estatísticas",
    persisting: "Gravando resultados",
    // O backend também reaproveita o status como etapa (início e fim da execução).
    queued: RUN_STATUS_LABELS.queued,
    completed: RUN_STATUS_LABELS.completed,
    failed: RUN_STATUS_LABELS.failed,
    cancelled: RUN_STATUS_LABELS.cancelled,
};

const REJECTION_REASON_LABELS: Record<string, string> = {
    compile: "não compilam",
    tests: "com testes falhando",
    tests_infra: "com testes que exigem infraestrutura (Selenium, Docker...)",
    no_tests: "sem testes",
    jdk_resolution: "exigem outra versão do Java",
    clone: "falharam ao clonar",
    structure: "sem pom.xml na raiz",
    content_filter: "fora das regras de conteúdo",
    java_version_filter: "com versão de Java fora do filtro",
    unexpected: "com erro inesperado",
    unknown: "sem motivo registrado",
};

/** "8 não compilam · 5 com testes falhando", do maior para o menor. */
export function summarizeRejectionReasons(reasons?: Record<string, number> | null): string {
    if (!reasons) return "";
    return Object.entries(reasons)
        .filter(([, count]) => count > 0)
        .sort((a, b) => b[1] - a[1])
        .map(([stage, count]) => `${count} ${REJECTION_REASON_LABELS[stage] ?? stage}`)
        .join(" · ");
}

function formatDuration(totalSeconds: number): string {
    if (totalSeconds < 90) return `${Math.max(1, Math.round(totalSeconds))} s`;
    const minutes = Math.round(totalSeconds / 60);
    if (minutes < 90) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    return `${hours} h ${String(minutes % 60).padStart(2, "0")} min`;
}

/**
 * Tempo médio por repositório e, quando já existe ao menos um aceito, uma
 * estimativa do que falta para chegar à meta. Sem aceitos não há como estimar
 * (a taxa de aceitação ainda é desconhecida), então só mostra a média.
 */
export function describeRunTiming(run: {
    started_at?: string | null;
    processed_repositories?: number;
    accepted_repositories?: number;
    max_repos?: number;
}, nowMs: number = Date.now()): string {
    const processed = run.processed_repositories ?? 0;
    const accepted = run.accepted_repositories ?? 0;
    const goal = run.max_repos ?? 0;
    if (!run.started_at || processed < 3) return "";
    // SQLite grava CURRENT_TIMESTAMP em UTC, sem fuso: "AAAA-MM-DD HH:MM:SS".
    const startedMs = Date.parse(`${run.started_at.replace(" ", "T")}Z`);
    if (Number.isNaN(startedMs)) return "";
    const elapsedSeconds = (nowMs - startedMs) / 1000;
    if (elapsedSeconds <= 0) return "";
    const perRepo = elapsedSeconds / processed;
    const average = `média de ${formatDuration(perRepo)} por repositório`;
    if (accepted <= 0 || goal <= accepted) return average;
    const remainingProcessed = ((goal - accepted) * processed) / accepted;
    return `${average} · faltam cerca de ${formatDuration(remainingProcessed * perRepo)} (estimativa)`;
}

export function runStatusLabel(status?: string | null): string {
    if (!status) return "";
    return RUN_STATUS_LABELS[status] ?? status;
}

export function progressStageLabel(stage?: string | null): string {
    if (!stage) return "";
    return PROGRESS_STAGE_LABELS[stage] ?? stage;
}
