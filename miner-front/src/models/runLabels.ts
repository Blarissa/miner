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

export function runStatusLabel(status?: string | null): string {
    if (!status) return "";
    return RUN_STATUS_LABELS[status] ?? status;
}

export function progressStageLabel(stage?: string | null): string {
    if (!stage) return "";
    return PROGRESS_STAGE_LABELS[stage] ?? stage;
}
