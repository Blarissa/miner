import { useCallback, useRef } from 'react'
import ActionPanel from './ActionPanel'
import HeroSection from './HeroSection'

interface HomePageProps {
  oldRunId: string
  onOldRunIdChange: (value: string) => void
  onLoadRun: () => void
  onNewSearch: () => void
}

/** Landing page: primeiro explica (hero), depois oferece a ação (scroll suave). */
export default function HomePage(props: HomePageProps) {
  const actionRef = useRef<HTMLElement>(null)

  const scrollToAction = useCallback(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    actionRef.current?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' })
  }, [])

  return (
    <div className="relative min-h-screen overflow-hidden bg-slate-950 font-sans text-slate-100">
      {/* brilhos decorativos */}
      <div aria-hidden="true" className="pointer-events-none absolute -left-40 top-0 h-96 w-96 rounded-full bg-cyan-500/10 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-40 top-1/3 h-96 w-96 rounded-full bg-orange-500/10 blur-3xl" />

      <div className="relative">
        <HeroSection onStart={scrollToAction} />

        <section
          id="acao"
          ref={actionRef}
          aria-label="Iniciar mineração"
          className="scroll-mt-20 px-4 pb-24 pt-8 sm:px-6"
        >
          <ActionPanel {...props} />
        </section>
      </div>
    </div>
  )
}
