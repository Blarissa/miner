import { History, PlayCircle } from 'lucide-react'
import type { FormEvent } from 'react'

interface ActionPanelProps {
  oldRunId: string
  onOldRunIdChange: (value: string) => void
  onLoadRun: () => void
  onNewSearch: () => void
}

/** Container flutuante com as ações: iniciar nova busca ou recarregar uma execução por Run ID. */
export default function ActionPanel({ oldRunId, onOldRunIdChange, onLoadRun, onNewSearch }: ActionPanelProps) {
  const canLoadRun = Number(oldRunId) > 0

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (canLoadRun) onLoadRun()
  }

  return (
    <div className="mx-auto w-full max-w-3xl rounded-xl border border-slate-800 bg-slate-900/50 p-6 shadow-xl shadow-black/20 backdrop-blur-md">
      <div className="mb-6 text-center">
        <h2 className="text-xl font-semibold text-slate-100">Pronto para minerar?</h2>
        <p className="mt-1 text-sm text-slate-400">Inicie uma nova consulta ou retome uma execução anterior.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <section className="flex flex-col justify-between gap-5 rounded-lg border border-slate-800 bg-slate-950/50 p-5">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-orange-500/30 bg-orange-500/10">
              <PlayCircle className="h-5 w-5 text-orange-400" />
            </span>
            <div>
              <h3 className="font-semibold text-slate-100">Realizar nova busca</h3>
              <p className="mt-1 text-sm text-slate-400">
                Abre o formulário de filtros para iniciar uma nova consulta no GitHub.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onNewSearch}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-orange-500 px-4 py-2 text-sm font-semibold text-slate-900 transition-colors hover:bg-orange-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-300 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            <PlayCircle className="h-4 w-4" />
            Nova busca
          </button>
        </section>

        <section className="flex flex-col justify-between gap-5 rounded-lg border border-slate-800 bg-slate-950/50 p-5">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-cyan-500/30 bg-cyan-500/10">
              <History className="h-5 w-5 text-cyan-400" />
            </span>
            <div>
              <h3 className="font-semibold text-slate-100">Buscar consulta antiga</h3>
              <p className="mt-1 text-sm text-slate-400">
                Informe o Run ID para carregar repositórios e estatísticas persistidos.
              </p>
            </div>
          </div>
          <form onSubmit={handleSubmit} className="flex gap-2">
            <label htmlFor="old-run-id" className="sr-only">
              Run ID da consulta antiga
            </label>
            <input
              id="old-run-id"
              type="number"
              min={1}
              value={oldRunId}
              onChange={(event) => onOldRunIdChange(event.target.value)}
              placeholder="Ex: 12"
              className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500"
            />
            <button
              type="submit"
              disabled={!canLoadRun}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-300 transition-colors hover:bg-cyan-500/20 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <History className="h-4 w-4" />
              Carregar
            </button>
          </form>
        </section>
      </div>
    </div>
  )
}
