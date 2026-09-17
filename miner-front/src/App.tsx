import { useState } from 'react'
import type { ReactNode } from 'react'
import { BarChart3, Code2, History, PlayCircle } from 'lucide-react'
import MiningDashboard from './components/MiningDashboard'
import StatisticsPage from './components/StatisticsPage'
import type { RepositoryStatistics } from './models/types'

type AppPage = 'home' | 'dashboard' | 'statistics'

function parseValidRunId(value: string): number | null {
  const parsedRunId = Number(value)
  if (!Number.isInteger(parsedRunId) || parsedRunId <= 0) {
    return null
  }
  return parsedRunId
}

function SidebarButton({
  active,
  icon,
  label,
  onClick,
}: {
  active: boolean
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full inline-flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition cursor-pointer ${active
        ? 'bg-indigo-500/15 text-indigo-200 border border-indigo-500/30'
        : 'text-zinc-400 border border-transparent hover:bg-zinc-800 hover:text-zinc-100'
        }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  )
}

function HomePage({
  oldRunId,
  onOldRunIdChange,
  onLoadRun,
  onNewSearch,
}: {
  oldRunId: string
  onOldRunIdChange: (value: string) => void
  onLoadRun: () => void
  onNewSearch: () => void
}) {
  const canLoadRun = Number(oldRunId) > 0

  return (
    <div className="min-h-screen bg-zinc-900 text-zinc-200 p-6 sm:p-10 font-sans">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-5xl flex-col justify-center gap-8">
        <header className="space-y-3">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-lg border border-indigo-500/30 bg-indigo-500/15">
            <Code2 className="h-6 w-6 text-indigo-300" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-zinc-50">
              Minerador Java
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-400">
              Inicie uma nova mineração ou carregue uma execução antiga já salva no banco.
            </p>
          </div>
        </header>

        <div className="grid gap-4 md:grid-cols-2">
          <section className="rounded-xl border border-zinc-700/60 bg-zinc-800/80 p-5 shadow-md">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-indigo-500/30 bg-indigo-500/15">
                <PlayCircle className="h-5 w-5 text-indigo-300" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold text-zinc-100">Realizar nova busca</h2>
                <p className="mt-1 text-sm text-zinc-400">
                  Abre o formulário de filtros para iniciar uma nova consulta no GitHub.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onNewSearch}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-500"
            >
              <PlayCircle className="h-4 w-4" />
              Nova busca
            </button>
          </section>

          <section className="rounded-xl border border-zinc-700/60 bg-zinc-800/80 p-5 shadow-md">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-zinc-600 bg-zinc-900">
                <History className="h-5 w-5 text-zinc-300" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold text-zinc-100">Buscar consulta antiga</h2>
                <p className="mt-1 text-sm text-zinc-400">
                  Informe o Run ID para carregar repositórios e estatísticas persistidos.
                </p>
              </div>
            </div>
            <div className="mt-5 flex gap-2">
              <input
                type="number"
                min={1}
                value={oldRunId}
                onChange={(event) => onOldRunIdChange(event.target.value)}
                placeholder="Ex: 12"
                className="min-w-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={onLoadRun}
                disabled={!canLoadRun}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-4 py-2 text-sm font-semibold text-zinc-100 transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <History className="h-4 w-4" />
                Carregar
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function App() {
  const [page, setPage] = useState<AppPage>('home')
  const [statistics, setStatistics] = useState<RepositoryStatistics | null>(null)
  const [showEliminatedRepositoryStats, setShowEliminatedRepositoryStats] = useState(false)
  const [oldRunId, setOldRunId] = useState('')
  const [runToLoad, setRunToLoad] = useState<number | null>(null)
  const [loadRequestKey, setLoadRequestKey] = useState(0)

  const openNewSearch = () => {
    setRunToLoad(null)
    setStatistics(null)
    setShowEliminatedRepositoryStats(false)
    setPage('dashboard')
  }

  const loadOldRun = () => {
    const parsedRunId = parseValidRunId(oldRunId)
    if (parsedRunId === null) {
      return
    }
    setRunToLoad(parsedRunId)
    setLoadRequestKey((value) => value + 1)
    setPage('dashboard')
  }

  const renderCurrentPage = () => {
    if (page === 'home') {
      return (
        <HomePage
          oldRunId={oldRunId}
          onOldRunIdChange={setOldRunId}
          onLoadRun={loadOldRun}
          onNewSearch={openNewSearch}
        />
      )
    }

    if (page === 'statistics') {
      return (
        <StatisticsPage
          statistics={statistics}
          showEliminatedRepositoryStats={showEliminatedRepositoryStats}
        />
      )
    }

    return (
      <MiningDashboard
        initialRunId={runToLoad}
        loadRequestKey={loadRequestKey}
        onStatisticsChange={setStatistics}
        onEliminatedRepositoryStatsVisibilityChange={setShowEliminatedRepositoryStats}
        onOpenStatistics={() => setPage('statistics')}
      />
    )
  }

  return (
    <div className="min-h-screen bg-zinc-900 text-zinc-200 lg:flex">
      <aside className="lg:sticky lg:top-0 lg:h-screen lg:w-72 border-b lg:border-b-0 lg:border-r border-zinc-800 bg-zinc-950/80 px-4 py-5">
        <div className="flex items-center gap-3 px-2 pb-5 border-b border-zinc-800">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-500/15 border border-indigo-500/30">
            <Code2 className="h-5 w-5 text-indigo-300" />
          </div>
          <div>
            <p className="text-sm font-bold text-zinc-100">Minerador Java</p>
            <p className="text-xs text-zinc-500">GitHub Repository Miner</p>
          </div>
        </div>

        <nav className="mt-5 space-y-2">
          <SidebarButton
            active={page === 'home'}
            icon={<History className="h-4 w-4" />}
            label="Início"
            onClick={() => setPage('home')}
          />
          <SidebarButton
            active={page === 'dashboard'}
            icon={<Code2 className="h-4 w-4" />}
            label="Mineração"
            onClick={() => setPage('dashboard')}
          />
          <SidebarButton
            active={page === 'statistics'}
            icon={<BarChart3 className="h-4 w-4" />}
            label="Estatísticas"
            onClick={() => setPage('statistics')}
          />
        </nav>
      </aside>

      <main className="min-w-0 flex-1">
        {renderCurrentPage()}
      </main>
    </div>
  )
}

export default App
