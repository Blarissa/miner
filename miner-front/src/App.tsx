import { useState } from 'react'
import type { ReactNode } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom'
import { BookOpen, Code2, History } from 'lucide-react'
import MiningDashboard from './components/MiningDashboard'
import StatisticsPage from './components/StatisticsPage'
import DocumentationPage from './components/DocumentationPage'
import HomePage from './components/home/HomePage'
import type { RepositoryStatistics } from './models/types'

function parseValidRunId(value: string): number | null {
  const parsedRunId = Number(value)
  if (!Number.isInteger(parsedRunId) || parsedRunId <= 0) {
    return null
  }
  return parsedRunId
}

function TopNavLink({
  to,
  end,
  extraActivePrefixes,
  icon,
  label,
}: {
  to: string
  end?: boolean
  /** Extra path prefixes that should also render this link as active (e.g. /runs/:id for "Mineração"). */
  extraActivePrefixes?: string[]
  icon: ReactNode
  label: string
}) {
  const location = useLocation()
  const extraActive = Boolean(
    extraActivePrefixes?.some((prefix) => location.pathname.startsWith(prefix)),
  )

  return (
    <NavLink
      to={to}
      end={end}
      aria-label={label}
      className={({ isActive }) =>
        `inline-flex shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${isActive || extraActive
          ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
          : 'text-slate-400 border-transparent hover:bg-slate-800 hover:text-slate-100'
        }`
      }
    >
      <span className="shrink-0">{icon}</span>
      <span>{label}</span>
    </NavLink>
  )
}

/** Wraps MiningDashboard for the /runs/:runId deep-link route: parses the run id from the URL. */
function RunDashboardRoute({
  onStatisticsChange,
  onEliminatedRepositoryStatsVisibilityChange,
  onOpenStatistics,
}: {
  onStatisticsChange: (statistics: RepositoryStatistics | null) => void
  onEliminatedRepositoryStatsVisibilityChange: (visible: boolean) => void
  onOpenStatistics: () => void
}) {
  const { runId } = useParams<{ runId: string }>()
  const parsedRunId = runId ? parseValidRunId(runId) : null

  return (
    <MiningDashboard
      key={parsedRunId ?? 'invalid'}
      initialRunId={parsedRunId}
      loadRequestKey={parsedRunId ?? 0}
      onStatisticsChange={onStatisticsChange}
      onEliminatedRepositoryStatsVisibilityChange={onEliminatedRepositoryStatsVisibilityChange}
      onOpenStatistics={onOpenStatistics}
    />
  )
}

function AppShell() {
  const navigate = useNavigate()
  const [statistics, setStatistics] = useState<RepositoryStatistics | null>(null)
  const [showEliminatedRepositoryStats, setShowEliminatedRepositoryStats] = useState(false)
  const [oldRunId, setOldRunId] = useState('')

  const openNewSearch = () => {
    setStatistics(null)
    setShowEliminatedRepositoryStats(false)
    navigate('/dashboard')
  }

  const loadOldRun = () => {
    const parsedRunId = parseValidRunId(oldRunId)
    if (parsedRunId === null) {
      return
    }
    navigate(`/runs/${parsedRunId}`)
  }

  const openStatistics = () => navigate('/statistics')

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-2 sm:px-6">
          <Link
            to="/"
            className="flex items-center gap-3 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-cyan-500/10 border border-cyan-500/30">
              <Code2 className="h-5 w-5 text-cyan-300" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-100">Minerador Java</p>
              <p className="hidden text-xs text-slate-400 sm:block">GitHub Repository Miner</p>
            </div>
          </Link>

          <nav aria-label="Navegação principal" className="-mx-1 flex min-w-0 items-center gap-1 overflow-x-auto px-1 py-1">
            <TopNavLink to="/" end icon={<History className="h-4 w-4" />} label="Início" />
            <TopNavLink
              to="/dashboard"
              extraActivePrefixes={['/runs/']}
              icon={<Code2 className="h-4 w-4" />}
              label="Mineração"
            />
            {/* <TopNavLink to="/statistics" icon={<BarChart3 className="h-4 w-4" />} label="Estatísticas" /> */}
            <TopNavLink to="/docs" icon={<BookOpen className="h-4 w-4" />} label="Documentação" />
          </nav>
        </div>
      </header>

      <main className="min-w-0">
        <Routes>
          <Route
            path="/"
            element={
              <HomePage
                oldRunId={oldRunId}
                onOldRunIdChange={setOldRunId}
                onLoadRun={loadOldRun}
                onNewSearch={openNewSearch}
              />
            }
          />
          <Route
            path="/dashboard"
            element={
              <MiningDashboard
                initialRunId={null}
                onStatisticsChange={setStatistics}
                onEliminatedRepositoryStatsVisibilityChange={setShowEliminatedRepositoryStats}
                onOpenStatistics={openStatistics}
              />
            }
          />
          <Route
            path="/runs/:runId"
            element={
              <RunDashboardRoute
                onStatisticsChange={setStatistics}
                onEliminatedRepositoryStatsVisibilityChange={setShowEliminatedRepositoryStats}
                onOpenStatistics={openStatistics}
              />
            }
          />
          <Route
            path="/statistics"
            element={
              <StatisticsPage
                statistics={statistics}
                showEliminatedRepositoryStats={showEliminatedRepositoryStats}
              />
            }
          />
          <Route path="/docs" element={<DocumentationPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  )
}

export default App
