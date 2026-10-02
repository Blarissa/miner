import { ArrowDown } from 'lucide-react'
import ProcessSteps from './ProcessSteps'

export default function HeroSection({ onStart }: { onStart: () => void }) {
  return (
    <section
      aria-labelledby="hero-title"
      className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-7xl flex-col items-center justify-center px-4 py-12 sm:px-6 lg:py-16"
    >
      <div className="flex w-full flex-col items-center justify-center gap-8 text-center">
        <span className="w-max rounded-full bg-cyan-950/50 px-3 py-1 font-mono text-xs uppercase tracking-wider text-cyan-400">
          Mineração de repositórios Java
        </span>

        <h1
          id="hero-title"
          className="bg-gradient-to-r from-cyan-400 via-blue-500 to-orange-500 bg-clip-text pb-1 text-4xl font-bold leading-tight tracking-tight text-transparent lg:text-5xl"
        >
          Descubra, compile e analise repositórios Java em escala
        </h1>

        <p className="max-w-2xl text-base leading-relaxed text-slate-400">
          O Minerador se conecta à API do GitHub para encontrar projetos Java, valida estruturas Maven/Spring,
          verifica se compilam e se os testes passam, e consolida estatísticas sobre frameworks de teste,
          versões de Java e tempos de build. Tudo pelo navegador, sem rodar scripts.
        </p>

        <ProcessSteps />

        <button
          type="button"
          onClick={onStart}
          className="group mt-2 inline-flex items-center gap-2 rounded-lg bg-orange-500 px-6 py-3 text-sm font-semibold text-slate-900 transition-colors hover:bg-orange-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-300 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
        >
          Começar mineração
          <ArrowDown className="h-4 w-4 transition-transform group-hover:translate-y-0.5" />
        </button>
      </div>
    </section>
  )
}
