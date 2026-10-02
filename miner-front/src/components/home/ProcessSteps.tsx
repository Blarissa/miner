import { BarChart3, ChevronRight, Filter, Hammer, Search } from 'lucide-react'
import type { ReactNode } from 'react'

interface Step {
  label: string
  hint: string
  icon: ReactNode
}

const STEPS: Step[] = [
  { label: 'Buscar', hint: 'API do GitHub', icon: <Search className="h-4 w-4" /> },
  { label: 'Filtrar', hint: 'Maven / Spring', icon: <Filter className="h-4 w-4" /> },
  { label: 'Compilar', hint: 'Build e testes', icon: <Hammer className="h-4 w-4" /> },
  { label: 'Analisar', hint: 'Estatísticas', icon: <BarChart3 className="h-4 w-4" /> },
]

/** Linha horizontal com os 4 passos do processo, ligados por conectores sutis. */
export default function ProcessSteps() {
  return (
    <ol aria-label="Etapas do processo de mineração" className="flex flex-wrap items-center gap-x-2 gap-y-4">
      {STEPS.map((step, index) => (
        <li key={step.label} className="flex items-center gap-2">
          <div className="flex items-center gap-3">
            <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300">
              {step.icon}
              <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-slate-950 font-mono text-[10px] text-slate-400 ring-1 ring-slate-700">
                {index + 1}
              </span>
            </span>
            <span className="leading-tight">
              <span className="block text-sm font-semibold text-slate-100">{step.label}</span>
              <span className="block text-xs text-slate-500">{step.hint}</span>
            </span>
          </div>

          {index < STEPS.length - 1 && (
            <span aria-hidden="true" className="ml-1 flex items-center text-slate-700">
              <span className="hidden h-px w-5 bg-gradient-to-r from-slate-700 to-slate-600 sm:block" />
              <ChevronRight className="h-4 w-4" />
            </span>
          )}
        </li>
      ))}
    </ol>
  )
}
