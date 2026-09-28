import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
    AlertTriangle,
    BarChart3,
    BookOpen,
    CheckCircle2,
    Code2,
    Database,
    Filter,
    History,
    Info,
    Lightbulb,
    PlayCircle,
    Rocket,
    Search,
    SlidersHorizontal,
    Table2,
    Timer,
    XCircle,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/*                                   Tipos                                    */
/* -------------------------------------------------------------------------- */

type AppliesTo = "code" | "repositories" | "both" | "platform";

interface FieldDoc {
    label: string;
    group: "Campos principais" | "Filtros avançados" | "Tipo e limites";
    qualifier?: string;
    appliesTo: AppliesTo;
    defaultValue?: string;
    description: ReactNode;
    examples?: { value: string; meaning: string }[];
    tip?: ReactNode;
}

interface OptionDoc {
    label: string;
    description: ReactNode;
    tip?: ReactNode;
}

/* -------------------------------------------------------------------------- */
/*                         Seções (índice lateral)                            */
/* -------------------------------------------------------------------------- */

const SECTIONS = [
    { id: "visao-geral", label: "Visão geral", icon: BookOpen },
    { id: "primeira-busca", label: "Primeira busca", icon: Rocket },
    { id: "inicio", label: "Tela Início", icon: History },
    { id: "como-a-busca-funciona", label: "Como a busca funciona", icon: Search },
    { id: "sintaxe", label: "Sintaxe de valores", icon: Code2 },
    { id: "campos", label: "Campos de pesquisa", icon: SlidersHorizontal },
    { id: "opcoes", label: "Opções de execução", icon: PlayCircle },
    { id: "execucao", label: "Acompanhando a execução", icon: Timer },
    { id: "resultados", label: "Tabela de resultados", icon: Table2 },
    { id: "eliminacao", label: "Estágios de eliminação", icon: XCircle },
    { id: "estatisticas", label: "Estatísticas", icon: BarChart3 },
    { id: "limites", label: "Limites e boas práticas", icon: AlertTriangle },
    { id: "faq", label: "Perguntas frequentes", icon: Lightbulb },
] as const;

/* -------------------------------------------------------------------------- */
/*                            Campos de pesquisa                              */
/* -------------------------------------------------------------------------- */

const FIELDS: FieldDoc[] = [
    // ------------------------------------------------------------ principais
    {
        label: "Queries de Busca no GitHub",
        group: "Campos principais",
        appliesTo: "both",
        defaultValue: "mockito",
        description: (
            <>
                Texto livre que será pesquisado no GitHub. É o único campo obrigatório. Aceita a
                sintaxe completa de busca do GitHub, então você pode escrever qualificadores
                diretamente aqui (ex.: <Code>filename:pom.xml</Code>, <Code>in:readme</Code>),
                usar aspas para frases exatas (<Code>"spring boot"</Code>) e o operador{" "}
                <Code>NOT</Code> para excluir termos. Use <strong>Adicionar query</strong> para
                criar várias buscas: cada query vira uma busca independente no GitHub
                (<Code>custom-search-1</Code>, <Code>custom-search-2</Code>…), todas com os mesmos
                filtros do formulário, e os resultados são combinados em uma única execução sem
                repetir repositórios.
            </>
        ),
        examples: [
            { value: "mockito", meaning: "arquivos/repositórios que contenham a palavra mockito" },
            { value: "junit-jupiter", meaning: "projetos que declaram JUnit 5" },
            { value: "\"spring-boot-starter-test\"", meaning: "frase exata" },
            { value: "mockito NOT powermock", meaning: "contém mockito mas não powermock" },
        ],
        tip: (
            <>
                Pelo GitHub, a parte de texto da busca pode ter no máximo 256 caracteres e no
                máximo cinco operadores <Code>AND</Code>/<Code>OR</Code>/<Code>NOT</Code>. Na busca
                de código é obrigatório ter pelo menos um termo de texto — não dá para buscar só
                com qualificadores.
            </>
        ),
    },
    {
        label: "GitHub Token",
        group: "Campos principais",
        appliesTo: "platform",
        description: (
            <>
                Token de acesso pessoal do GitHub (<Code>ghp_…</Code> ou{" "}
                <Code>github_pat_…</Code>) usado para autenticar as chamadas à API. Se ficar vazio,
                o backend usa o token padrão configurado no servidor. O token é enviado apenas na requisição da
                busca e não aparece nos resultados.
            </>
        ),
        tip: (
            <>
                A busca de código do GitHub <strong>exige autenticação</strong>. Para repositórios
                públicos basta um token sem permissões extras (GitHub → Settings → Developer
                settings → Personal access tokens). Sem token, o limite da API de busca cai para 10
                requisições por minuto.
            </>
        ),
    },
    {
        label: "Versão Java",
        group: "Campos principais",
        appliesTo: "platform",
        defaultValue: "Qualquer",
        description: (
            <>
                <strong>Não é um qualificador do GitHub.</strong> Depois que o GitHub devolve os
                candidatos, a plataforma baixa o <Code>pom.xml</Code> de cada um e procura a versão
                Java nas tags <Code>{"<java.version>"}</Code>,{" "}
                <Code>{"<maven.compiler.release>"}</Code>,{" "}
                <Code>{"<maven.compiler.source>"}</Code> e{" "}
                <Code>{"<maven.compiler.target>"}</Code>. Ao escolher uma versão, somente projetos
                que declaram exatamente essa versão seguem no pipeline (para Java 8, tanto{" "}
                <Code>8</Code> quanto <Code>1.8</Code> são aceitos); os demais são eliminados no
                estágio <Code>java_version_filter</Code>. Com <strong>Qualquer</strong>, a versão é
                apenas extraída, sem filtrar.
            </>
        ),
        examples: [
            { value: "Java 8", meaning: "aceita 8, 1.8, 8.0…" },
            { value: "Java 17", meaning: "aceita 17, 17.0…" },
        ],
    },
    {
        label: "Stars",
        group: "Campos principais",
        qualifier: "stars:",
        appliesTo: "repositories",
        description:
            "Filtra pela quantidade de estrelas do repositório. Aceita número exato ou intervalos (veja “Sintaxe de valores”).",
        examples: [
            { value: ">=100", meaning: "100 estrelas ou mais" },
            { value: "10..50", meaning: "entre 10 e 50 estrelas" },
            { value: "<1000", meaning: "menos de 1000 estrelas" },
        ],
    },
    {
        label: "Forks",
        group: "Campos principais",
        qualifier: "forks:",
        appliesTo: "repositories",
        description: "Filtra pela quantidade de forks que o repositório possui.",
        examples: [
            { value: "10..50", meaning: "entre 10 e 50 forks" },
            { value: ">=5", meaning: "5 forks ou mais" },
        ],
    },
    {
        label: "Tamanho",
        group: "Campos principais",
        qualifier: "size:",
        appliesTo: "repositories",
        description: (
            <>
                Filtra pelo tamanho do repositório <strong>em kilobytes</strong>. Útil para evitar
                projetos gigantes que demoram para clonar e compilar.
            </>
        ),
        examples: [
            { value: "<30000", meaning: "menos de ~30 MB" },
            { value: "1000..50000", meaning: "entre ~1 MB e ~50 MB" },
        ],
    },
    {
        label: "Criado desde",
        group: "Campos principais",
        qualifier: "created:",
        appliesTo: "repositories",
        description: (
            <>
                Seletor de data. A plataforma envia <Code>created:&gt;=AAAA-MM-DD</Code>, ou seja,
                só entram repositórios criados na data escolhida ou depois dela.
            </>
        ),
        examples: [{ value: "01/01/2020", meaning: "vira created:>=2020-01-01" }],
    },
    // ------------------------------------------------------------ avançados
    {
        label: "Último push desde",
        group: "Filtros avançados",
        qualifier: "pushed:",
        appliesTo: "repositories",
        description: (
            <>
                Seletor de data. Envia <Code>pushed:&gt;=AAAA-MM-DD</Code>: somente repositórios que
                receberam algum push a partir dessa data. Bom para descartar projetos abandonados.
            </>
        ),
        examples: [{ value: "01/01/2024", meaning: "ativos desde 2024" }],
    },
    {
        label: "Tópico",
        group: "Filtros avançados",
        qualifier: "topic:",
        appliesTo: "repositories",
        description:
            "Repositórios marcados com um tópico específico (as tags que aparecem na página do repositório).",
        examples: [{ value: "spring", meaning: "repositórios com o tópico spring" }],
        tip: (
            <>
                O campo aceita um tópico. Para exigir vários, escreva-os na query:{" "}
                <Code>topic:spring topic:testing</Code>.
            </>
        ),
    },
    {
        label: "Licença",
        group: "Filtros avançados",
        qualifier: "license:",
        appliesTo: "repositories",
        description: "Filtra pela licença do repositório usando a palavra-chave da licença.",
        examples: [
            { value: "mit", meaning: "MIT" },
            { value: "apache-2.0", meaning: "Apache 2.0" },
            { value: "gpl-3.0", meaning: "GNU GPL v3" },
            { value: "bsd-3-clause", meaning: "BSD 3-Clause" },
        ],
    },
    {
        label: "Visibilidade",
        group: "Filtros avançados",
        qualifier: "is:",
        appliesTo: "repositories",
        defaultValue: "Público",
        description: (
            <>
                <Code>is:public</Code>, <Code>is:private</Code> ou <Code>is:internal</Code>.
                Repositórios privados e internos só aparecem se o token tiver acesso a eles.
            </>
        ),
    },
    {
        label: "Usuário",
        group: "Filtros avançados",
        qualifier: "user:",
        appliesTo: "both",
        description: "Restringe a busca aos repositórios de uma conta pessoal.",
        examples: [{ value: "octocat", meaning: "só repositórios de octocat" }],
    },
    {
        label: "Organização",
        group: "Filtros avançados",
        qualifier: "org:",
        appliesTo: "both",
        description: "Restringe a busca aos repositórios de uma organização.",
        examples: [
            { value: "apache", meaning: "só repositórios da Apache" },
            { value: "spring-projects", meaning: "só repositórios do Spring" },
        ],
    },
    {
        label: "Repositório",
        group: "Filtros avançados",
        qualifier: "repo:",
        appliesTo: "both",
        description: (
            <>
                Busca em um repositório específico, no formato <Code>dono/nome</Code>. Útil para
                testar a plataforma com um projeto conhecido.
            </>
        ),
        examples: [{ value: "junit-team/junit5", meaning: "apenas esse repositório" }],
    },
    {
        label: "Seguidores",
        group: "Filtros avançados",
        qualifier: "followers:",
        appliesTo: "repositories",
        description: "Filtra pela quantidade de usuários que seguem o repositório.",
        examples: [{ value: ">=100", meaning: "100 seguidores ou mais" }],
    },
    {
        label: "Quantidade de tópicos",
        group: "Filtros avançados",
        qualifier: "topics:",
        appliesTo: "repositories",
        description: "Filtra pelo número de tópicos marcados no repositório (não pelo nome do tópico).",
        examples: [{ value: ">=3", meaning: "pelo menos 3 tópicos" }],
    },
    {
        label: "Fork",
        group: "Filtros avançados",
        qualifier: "fork:",
        appliesTo: "repositories",
        defaultValue: "Não",
        description: (
            <>
                Por padrão o GitHub não inclui forks nos resultados.{" "}
                <strong>Sim</strong> (<Code>fork:true</Code>) inclui forks junto com os
                originais; <strong>Somente forks</strong> (<Code>fork:only</Code>) traz só forks;{" "}
                <strong>Não</strong> mantém apenas os originais.
            </>
        ),
    },
    {
        label: "Arquivado",
        group: "Filtros avançados",
        qualifier: "archived:",
        appliesTo: "repositories",
        defaultValue: "Não",
        description:
            "Repositórios arquivados são somente leitura e normalmente não recebem mais manutenção. “Não” os exclui; “Sim” traz apenas arquivados.",
    },
    {
        label: "Mirror",
        group: "Filtros avançados",
        qualifier: "mirror:",
        appliesTo: "repositories",
        description: "Filtra repositórios que são espelhos (cópias sincronizadas de outro servidor).",
    },
    {
        label: "Template",
        group: "Filtros avançados",
        qualifier: "template:",
        appliesTo: "repositories",
        description: "Filtra repositórios marcados como template (modelo para criar novos projetos).",
    },
    {
        label: "Good first issues",
        group: "Filtros avançados",
        qualifier: "good-first-issues:",
        appliesTo: "repositories",
        description: "Quantidade de issues abertas com o rótulo “good first issue”.",
        examples: [{ value: ">=2", meaning: "2 ou mais issues desse tipo" }],
    },
    {
        label: "Help wanted issues",
        group: "Filtros avançados",
        qualifier: "help-wanted-issues:",
        appliesTo: "repositories",
        description: "Quantidade de issues abertas com o rótulo “help wanted”.",
        examples: [{ value: ">=2", meaning: "2 ou mais issues desse tipo" }],
    },
    {
        label: "Arquivo",
        group: "Filtros avançados",
        qualifier: "filename:",
        appliesTo: "code",
        defaultValue: "pom.xml",
        description:
            "Procura apenas em arquivos com esse nome. Para projetos Maven, mantenha pom.xml: é nele que a plataforma encontra dependências e a versão Java.",
        examples: [{ value: "pom.xml", meaning: "somente arquivos pom.xml" }],
    },
    {
        label: "Extensão",
        group: "Filtros avançados",
        qualifier: "extension:",
        appliesTo: "code",
        defaultValue: "xml",
        description: "Procura apenas em arquivos com essa extensão (sem o ponto).",
        examples: [{ value: "xml", meaning: "arquivos .xml" }],
    },
    {
        label: "Caminho",
        group: "Filtros avançados",
        qualifier: "path:",
        appliesTo: "code",
        description: "Procura apenas em arquivos que estão dentro de um diretório específico.",
        examples: [{ value: "src/main", meaning: "arquivos dentro de src/main" }],
    },
    {
        label: "Ordenar por",
        group: "Filtros avançados",
        appliesTo: "both",
        description: (
            <>
                Critério de ordenação dos resultados do GitHub. Vazio = “melhor correspondência”
                (padrão). Na busca de repositórios: <Code>stars</Code>, <Code>forks</Code>,{" "}
                <Code>help-wanted-issues</Code> ou <Code>updated</Code>. Na busca de código o GitHub
                só aceita <Code>indexed</Code> (e ele está obsoleto), então o ideal é deixar vazio.
            </>
        ),
        examples: [{ value: "stars", meaning: "mais estrelados primeiro (com direção Desc)" }],
    },
    {
        label: "Direção",
        group: "Filtros avançados",
        appliesTo: "both",
        defaultValue: "Padrão",
        description:
            "Asc (crescente) ou Desc (decrescente). Só tem efeito quando “Ordenar por” está preenchido; o padrão do GitHub é Desc.",
    },
    {
        label: "Itens por página",
        group: "Filtros avançados",
        appliesTo: "both",
        defaultValue: "100",
        description:
            "Quantos resultados o GitHub devolve por página (1 a 100). Valores maiores significam menos chamadas à API; a plataforma avança página por página até atingir o limite de repositórios.",
    },
    {
        label: "Buscar em",
        group: "Filtros avançados",
        qualifier: "in:",
        appliesTo: "repositories",
        description: (
            <>
                Define em quais partes do repositório o texto da query é procurado:{" "}
                <Code>name</Code>, <Code>description</Code>, <Code>readme</Code> e/ou{" "}
                <Code>topics</Code>. Sem nenhuma marcada, o GitHub procura em nome, descrição e
                tópicos.
            </>
        ),
        examples: [{ value: "readme", meaning: "vira in:readme" }],
    },
    // ------------------------------------------------------------ tipo e limites
    {
        label: "Tipo de Busca",
        group: "Tipo e limites",
        appliesTo: "platform",
        defaultValue: "Code Search",
        description: (
            <>
                <strong>Code Search</strong> procura o texto <em>dentro dos arquivos</em> (por
                padrão, dentro do <Code>pom.xml</Code>) — ideal para encontrar projetos que usam
                uma biblioteca específica. <strong>Repository Search</strong> procura nos{" "}
                <em>metadados</em> do repositório (nome, descrição, README, tópicos) e é a única
                que aceita filtros como estrelas, forks, datas e licença. Veja a tabela de
                compatibilidade abaixo.
            </>
        ),
    },
    {
        label: "Limite de Repositórios",
        group: "Tipo e limites",
        appliesTo: "platform",
        defaultValue: "20",
        description: (
            <>
                Quantos repositórios <strong>aceitos</strong> você quer ao final. A plataforma
                continua buscando novas páginas e analisando candidatos até chegar a esse número ou
                até o GitHub não ter mais resultados. Repositórios que passam de sua cota são
                marcados como <Code>max_repos_reached</Code>.
            </>
        ),
    },
    {
        label: "Estatísticas (escopo)",
        group: "Tipo e limites",
        appliesTo: "platform",
        defaultValue: "Aceitos",
        description: (
            <>
                Sobre qual conjunto as estatísticas serão calculadas: <strong>Aceitos</strong>{" "}
                (apenas os que passaram em todos os critérios), <strong>Todos filtrados</strong>{" "}
                (aceitos + eliminados) ou <strong>Eliminados</strong>. Para os escopos que incluem
                eliminados, marque também “Salvar repositórios eliminados”.
            </>
        ),
    },
];

const OPTIONS: OptionDoc[] = [
    {
        label: "Apenas repositórios buildáveis",
        description: (
            <>
                Liga o <strong>analyzer</strong>: cada candidato é clonado e compilado com Maven
                (usa o <Code>mvnw</Code> do projeto quando existe). Só ficam os que compilam. Nesse
                modo os testes não são executados.
            </>
        ),
    },
    {
        label: "Apenas com testes aprovados",
        description: (
            <>
                Modo mais completo: compila, detecta se o projeto tem testes e executa a suíte.
                Só ficam os que compilam, <strong>têm testes</strong> e cujos testes{" "}
                <strong>passam</strong>. Marcar esta opção marca automaticamente “buildáveis”.
            </>
        ),
        tip: "É o modo mais lento: cada repositório pode levar vários minutos.",
    },
    {
        label: "Salvar repositórios eliminados",
        description:
            "Por padrão só os aceitos são gravados no banco e mostrados na tabela. Marcando esta opção, os eliminados também são salvos (com o estágio e o log do erro), aparecem na tabela e podem entrar nas estatísticas.",
    },
    {
        label: "Permitir upgrade automático do JDK",
        description: (
            <>
                Só fica habilitada quando o analyzer vai rodar. Desmarcada (padrão), a compilação
                usa exatamente o JDK da versão declarada; se o Maven ou o <Code>pom.xml</Code>{" "}
                exigir uma versão maior, o repositório é eliminado (<Code>jdk_resolution</Code>).
                Marcada, o backend escolhe o menor JDK disponível que atenda à exigência. A tabela
                mostra o JDK efetivo e o selo <Badge tone="amber">Upgraded</Badge>.
            </>
        ),
    },
    {
        label: "Retornar estatísticas",
        description:
            "Calcula o pacote de estatísticas ao final da execução e habilita o botão “Ver estatísticas”. Desmarque se quiser apenas a lista de repositórios.",
    },
];

const ELIMINATION_STAGES: { stage: string; meaning: string }[] = [
    { stage: "java_version_filter", meaning: "O pom.xml não declara a versão Java escolhida no formulário." },
    { stage: "jdk_resolution", meaning: "Não há JDK compatível instalado, ou o projeto exige um JDK maior e o upgrade automático está desligado." },
    { stage: "clone", meaning: "Falha ao clonar o repositório (removido, privado, rede, tempo limite de 5 min)." },
    { stage: "structure", meaning: "Não existe pom.xml na raiz do projeto (não é um projeto Maven na raiz)." },
    { stage: "compile", meaning: "O build Maven falhou ou passou do tempo limite de 5 min." },
    { stage: "no_tests", meaning: "O projeto compila, mas nenhum teste foi detectado." },
    { stage: "tests", meaning: "Os testes rodaram e pelo menos um falhou, ou passaram do tempo limite de 10 min." },
    { stage: "tests_infra", meaning: "Os testes falharam por dependência de infraestrutura externa (banco, Docker, Selenium/navegador, etc.)." },
    { stage: "unexpected", meaning: "Erro inesperado durante a análise. Veja o log no modal de detalhes." },
    { stage: "max_repos_reached", meaning: "O repositório seria aceito, mas o limite de repositórios já tinha sido atingido." },
];

const RUN_STATUSES: { value: string; meaning: string }[] = [
    { value: "queued", meaning: "A execução foi criada e está aguardando para começar." },
    { value: "running", meaning: "Em andamento. Veja a etapa atual ao lado do status." },
    { value: "completed", meaning: "Concluída com sucesso." },
    { value: "failed", meaning: "Interrompida por erro (ex.: limite da API do GitHub, token inválido)." },
    { value: "cancelled", meaning: "Cancelada pelo usuário." },
];

const PROGRESS_STAGES: { value: string; meaning: string }[] = [
    { value: "mining", meaning: "Buscando uma página de resultados no GitHub." },
    { value: "mined", meaning: "Página recebida; candidatos sendo filtrados pelo conteúdo do pom.xml." },
    { value: "analyzing", meaning: "Clonando, compilando e/ou testando os candidatos do lote." },
    { value: "building_statistics", meaning: "Calculando as estatísticas." },
    { value: "persisting", meaning: "Gravando os resultados no banco." },
];

/* -------------------------------------------------------------------------- */
/*                           Componentes auxiliares                           */
/* -------------------------------------------------------------------------- */

function Code({ children }: { children: ReactNode }) {
    return (
        <code className="break-words rounded border border-zinc-700 bg-zinc-900 px-1.5 py-0.5 font-mono text-[0.8em] text-indigo-200">
            {children}
        </code>
    );
}

function Badge({
    children,
    tone = "zinc",
}: {
    children: ReactNode;
    tone?: "zinc" | "indigo" | "emerald" | "amber" | "rose" | "sky";
}) {
    const tones = {
        zinc: "border-zinc-600 bg-zinc-800 text-zinc-300",
        indigo: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300",
        emerald: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
        amber: "border-amber-500/30 bg-amber-500/10 text-amber-300",
        rose: "border-rose-500/30 bg-rose-500/10 text-rose-300",
        sky: "border-sky-500/30 bg-sky-500/10 text-sky-300",
    } as const;
    return (
        <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-semibold ${tones[tone]}`}>
            {children}
        </span>
    );
}

const APPLIES_TO_BADGE: Record<AppliesTo, { label: string; tone: "indigo" | "emerald" | "sky" | "zinc" }> = {
    code: { label: "Code Search", tone: "sky" },
    repositories: { label: "Repository Search", tone: "emerald" },
    both: { label: "Ambas as buscas", tone: "indigo" },
    platform: { label: "Plataforma", tone: "zinc" },
};

function Section({
    id,
    title,
    icon,
    children,
}: {
    id: string;
    title: string;
    icon: ReactNode;
    children: ReactNode;
}) {
    return (
        <section id={id} data-doc-section className="scroll-mt-6 space-y-4">
            <h2 className="flex items-center gap-2 border-b border-zinc-800 pb-2 text-lg font-bold text-zinc-50">
                {icon}
                {title}
            </h2>
            <div className="space-y-4 text-sm leading-7 text-zinc-300">{children}</div>
        </section>
    );
}

function Callout({
    tone = "info",
    title,
    children,
}: {
    tone?: "info" | "warning" | "tip";
    title?: string;
    children: ReactNode;
}) {
    const styles = {
        info: { box: "border-indigo-500/25 bg-indigo-500/10", icon: <Info className="h-4 w-4 text-indigo-300" /> },
        warning: { box: "border-amber-500/25 bg-amber-500/10", icon: <AlertTriangle className="h-4 w-4 text-amber-300" /> },
        tip: { box: "border-emerald-500/25 bg-emerald-500/10", icon: <Lightbulb className="h-4 w-4 text-emerald-300" /> },
    }[tone];
    return (
        <div className={`flex gap-3 rounded-lg border px-4 py-3 text-sm ${styles.box}`}>
            <div className="mt-1 shrink-0">{styles.icon}</div>
            <div className="space-y-1 leading-6 text-zinc-200">
                {title && <p className="font-semibold text-zinc-100">{title}</p>}
                <div>{children}</div>
            </div>
        </div>
    );
}

function Card({ children }: { children: ReactNode }) {
    return (
        <div className="min-w-0 rounded-xl border border-zinc-700/60 bg-zinc-800/80 p-4 shadow-sm">{children}</div>
    );
}

function DefinitionTable({
    head,
    rows,
}: {
    head: [string, string];
    rows: { key: ReactNode; value: ReactNode }[];
}) {
    return (
        <div className="overflow-x-auto rounded-lg border border-zinc-700/60">
            <table className="w-full text-left text-sm">
                <thead className="bg-zinc-900/80 text-xs uppercase tracking-wider text-zinc-400">
                    <tr>
                        <th className="px-4 py-2.5 font-semibold">{head[0]}</th>
                        <th className="px-4 py-2.5 font-semibold">{head[1]}</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-zinc-700/40 bg-zinc-800/50">
                    {rows.map((row, index) => (
                        <tr key={index}>
                            <td className="whitespace-nowrap px-4 py-2.5 align-top">{row.key}</td>
                            <td className="px-4 py-2.5 text-zinc-300">{row.value}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

function FieldCard({ field }: { field: FieldDoc }) {
    const applies = APPLIES_TO_BADGE[field.appliesTo];
    return (
        <Card>
            <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-semibold text-zinc-100">{field.label}</h4>
                {field.qualifier && <Code>{field.qualifier}</Code>}
                <Badge tone={applies.tone}>{applies.label}</Badge>
                {field.defaultValue && <Badge>Padrão: {field.defaultValue}</Badge>}
            </div>
            <div className="mt-2 text-sm leading-6 text-zinc-300">{field.description}</div>
            {field.examples && field.examples.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                    {field.examples.map((example) => (
                        <span
                            key={example.value}
                            className="inline-flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs"
                        >
                            <span className="font-mono text-indigo-200">{example.value}</span>
                            <span className="text-zinc-500">→ {example.meaning}</span>
                        </span>
                    ))}
                </div>
            )}
            {field.tip && (
                <p className="mt-3 flex gap-2 text-xs leading-5 text-zinc-400">
                    <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                    <span>{field.tip}</span>
                </p>
            )}
        </Card>
    );
}

function Pre({ children }: { children: string }) {
    return (
        <pre className="overflow-x-auto rounded-lg border border-zinc-700 bg-zinc-950 px-4 py-3 font-mono text-xs leading-6 text-zinc-200">
            {children}
        </pre>
    );
}

/* -------------------------------------------------------------------------- */
/*                               Página principal                             */
/* -------------------------------------------------------------------------- */

const FIELD_GROUPS: FieldDoc["group"][] = ["Campos principais", "Filtros avançados", "Tipo e limites"];

export default function DocumentationPage() {
    const [activeSection, setActiveSection] = useState<string>(SECTIONS[0].id);
    const [fieldFilter, setFieldFilter] = useState("");
    const [appliesFilter, setAppliesFilter] = useState<"all" | "code" | "repositories">("all");

    useEffect(() => {
        const elements = Array.from(document.querySelectorAll<HTMLElement>("[data-doc-section]"));
        const observer = new IntersectionObserver(
            (entries) => {
                const visible = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
                if (visible[0]) setActiveSection(visible[0].target.id);
            },
            { rootMargin: "0px 0px -70% 0px" },
        );
        elements.forEach((element) => observer.observe(element));
        return () => observer.disconnect();
    }, []);

    const filteredFields = useMemo(() => {
        const term = fieldFilter.trim().toLowerCase();
        return FIELDS.filter((field) => {
            const matchesTerm =
                !term ||
                field.label.toLowerCase().includes(term) ||
                (field.qualifier ?? "").toLowerCase().includes(term);
            const matchesApplies =
                appliesFilter === "all" ||
                field.appliesTo === appliesFilter ||
                field.appliesTo === "both" ||
                field.appliesTo === "platform";
            return matchesTerm && matchesApplies;
        });
    }, [fieldFilter, appliesFilter]);

    const scrollTo = (id: string) => {
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    return (
        <div className="min-h-screen bg-zinc-900 p-6 font-sans text-zinc-200 sm:p-10">
            <div className="mx-auto flex max-w-7xl gap-10">
                {/* Índice */}
                <aside className="hidden w-56 shrink-0 xl:block">
                    <nav className="sticky top-10 space-y-1">
                        <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500">
                            Nesta página
                        </p>
                        {SECTIONS.map(({ id, label, icon: Icon }) => (
                            <button
                                key={id}
                                type="button"
                                onClick={() => scrollTo(id)}
                                className={`flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-xs font-medium transition ${
                                    activeSection === id
                                        ? "bg-indigo-500/15 text-indigo-200"
                                        : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
                                }`}
                            >
                                <Icon className="h-3.5 w-3.5" />
                                {label}
                            </button>
                        ))}
                    </nav>
                </aside>

                {/* Conteúdo */}
                <div className="min-w-0 flex-1 space-y-12">
                    <header className="space-y-2 border-b border-zinc-800 pb-6">
                        <h1 className="flex items-center gap-2.5 text-2xl font-bold tracking-tight text-zinc-50">
                            <BookOpen className="h-7 w-7 text-indigo-400" />
                            Documentação
                        </h1>
                        <p className="max-w-3xl text-sm leading-6 text-zinc-400">
                            Tudo o que você precisa para usar o Minerador Java: o que cada campo de
                            pesquisa faz, como acompanhar uma execução, como ler os resultados e as
                            estatísticas. Os campos de busca seguem a sintaxe oficial de busca do
                            GitHub.
                        </p>
                        {/* Índice compacto para telas menores */}
                        <div className="flex flex-wrap gap-2 pt-3 xl:hidden">
                            {SECTIONS.map(({ id, label }) => (
                                <button
                                    key={id}
                                    type="button"
                                    onClick={() => scrollTo(id)}
                                    className="rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs text-zinc-300 hover:bg-zinc-700"
                                >
                                    {label}
                                </button>
                            ))}
                        </div>
                    </header>

                    {/* ------------------------------------------------ Visão geral */}
                    <Section id="visao-geral" title="Visão geral" icon={<BookOpen className="h-5 w-5 text-indigo-400" />}>
                        <p>
                            O Minerador Java encontra repositórios Java (Maven) no GitHub, verifica se
                            eles compilam e se os testes passam, e gera estatísticas sobre o conjunto
                            encontrado — frameworks de teste, bibliotecas de mock, versões de Java,
                            tempos de build, motivos de eliminação e mais. Tudo pelo navegador, sem
                            editar código ou rodar scripts.
                        </p>
                        <p>Cada execução (<strong>run</strong>) passa pelas etapas abaixo:</p>
                        <ol className="grid gap-3 md:grid-cols-5">
                            {[
                                ["1. Busca", "Consulta a API de busca do GitHub com a query e os filtros do formulário."],
                                ["2. Filtro de conteúdo", "Lê o pom.xml de cada candidato e extrai/filtra a versão Java."],
                                ["3. Análise (opcional)", "Clona, escolhe o JDK, compila com Maven e executa os testes."],
                                ["4. Persistência", "Grava repositórios e resultados no banco com um Run ID."],
                                ["5. Estatísticas", "Calcula os indicadores exibidos na tela Estatísticas."],
                            ].map(([title, text]) => (
                                <li key={title} className="rounded-lg border border-zinc-700/60 bg-zinc-800/80 p-3">
                                    <p className="text-xs font-semibold text-indigo-300">{title}</p>
                                    <p className="mt-1 text-xs leading-5 text-zinc-400">{text}</p>
                                </li>
                            ))}
                        </ol>
                        <p>O menu lateral tem quatro telas:</p>
                        <DefinitionTable
                            head={["Tela", "Para que serve"]}
                            rows={[
                                { key: <strong>Início</strong>, value: "Começar uma nova busca ou reabrir uma execução antiga pelo Run ID." },
                                { key: <strong>Mineração</strong>, value: "Formulário de busca, acompanhamento ao vivo e tabela de resultados." },
                                { key: <strong>Estatísticas</strong>, value: "Painel analítico da execução carregada." },
                                { key: <strong>Documentação</strong>, value: "Esta página." },
                            ]}
                        />
                    </Section>

                    {/* ------------------------------------------------ Primeira busca */}
                    <Section id="primeira-busca" title="Primeira busca" icon={<Rocket className="h-5 w-5 text-indigo-400" />}>
                        <p className="font-semibold text-zinc-100">Sua primeira busca, em 4 passos:</p>
                        <ol className="list-decimal space-y-1 pl-5">
                            <li>No Início, clique em <strong>Nova busca</strong>.</li>
                            <li>Mantenha a query <Code>mockito</Code> e o tipo <strong>Code Search</strong>; informe seu token do GitHub.</li>
                            <li>Deixe o limite em 5 ou 10 repositórios para um teste rápido.</li>
                            <li>Clique em <strong>Iniciar Mineração</strong> e acompanhe a tabela sendo preenchida.</li>
                        </ol>
                    </Section>

                    {/* ------------------------------------------------ Início */}
                    <Section id="inicio" title="Tela Início" icon={<History className="h-5 w-5 text-indigo-400" />}>
                        <DefinitionTable
                            head={["Ação", "O que faz"]}
                            rows={[
                                {
                                    key: <strong>Nova busca</strong>,
                                    value: "Abre a tela Mineração com o formulário limpo e zera as estatísticas carregadas.",
                                },
                                {
                                    key: <strong>Buscar consulta antiga</strong>,
                                    value: (
                                        <>
                                            Digite o <strong>Run ID</strong> (número inteiro, ex.: 12) e clique em{" "}
                                            <strong>Carregar</strong>. A plataforma busca no banco o status, os
                                            repositórios e as estatísticas dessa execução e abre a tela Mineração
                                            com tudo carregado. Se ela tiver sido interrompida, é possível retomá-la.
                                        </>
                                    ),
                                },
                            ]}
                        />
                        <Callout tone="info">
                            O Run ID aparece na tela Mineração assim que uma busca começa (selo{" "}
                            <Badge>Run #12</Badge>). Anote-o para voltar aos resultados depois.
                        </Callout>
                    </Section>

                    {/* ------------------------------------------------ Como a busca funciona */}
                    <Section id="como-a-busca-funciona" title="Como a busca funciona" icon={<Search className="h-5 w-5 text-indigo-400" />}>
                        <p>
                            A plataforma usa a <strong>API REST de busca do GitHub</strong>. O texto da
                            query e os campos preenchidos no formulário são transformados em{" "}
                            <strong>qualificadores</strong> no formato <Code>nome:valor</Code> e
                            juntos formam uma única string de busca. Campos vazios são ignorados; valores
                            com espaço são colocados entre aspas automaticamente.
                        </p>
                        <p className="font-semibold text-zinc-100">Exemplo — Code Search (valores padrão):</p>
                        <Pre>{"Query: mockito   Arquivo: pom.xml   Extensão: xml\n\n→  mockito filename:pom.xml extension:xml"}</Pre>
                        <p className="font-semibold text-zinc-100">Exemplo — Repository Search:</p>
                        <Pre>
                            {"Query: spring   Buscar em: readme   Stars: >=100   Criado desde: 01/01/2020\nFork: Não   Arquivado: Não   Visibilidade: Público\n\n→  spring in:readme stars:>=100 created:>=2020-01-01 language:Java fork:false archived:false is:public"}
                        </Pre>
                        <Callout tone="info" title="Linguagem sempre Java">
                            Na busca de repositórios, <Code>language:Java</Code> é adicionado
                            automaticamente. Na busca de código o filtro é feito pelo arquivo (
                            <Code>pom.xml</Code>).
                        </Callout>

                        <h3 className="pt-2 text-base font-semibold text-zinc-100">Code Search × Repository Search</h3>
                        <p>
                            Cada tipo de busca do GitHub aceita um conjunto diferente de qualificadores.
                            A plataforma envia somente os que são válidos para o tipo escolhido —{" "}
                            <strong>os demais campos são ignorados</strong>, mesmo se preenchidos.
                        </p>
                        <DefinitionTable
                            head={["Tipo", "Campos que são aplicados"]}
                            rows={[
                                {
                                    key: <Badge tone="sky">Code Search</Badge>,
                                    value: (
                                        <>
                                            Query, Usuário, Organização, Repositório, Arquivo, Extensão, Caminho,
                                            Ordenar por, Direção, Itens por página. Procura dentro do conteúdo dos
                                            arquivos, somente na branch padrão e em arquivos menores que 384 KB.
                                        </>
                                    ),
                                },
                                {
                                    key: <Badge tone="emerald">Repository Search</Badge>,
                                    value: (
                                        <>
                                            Query, Buscar em, Stars, Forks, Tamanho, Criado desde, Último push,
                                            Tópico, Quantidade de tópicos, Licença, Visibilidade, Usuário,
                                            Organização, Repositório, Seguidores, Fork, Arquivado, Mirror, Template,
                                            Good first issues, Help wanted issues, Ordenar por, Direção, Itens por
                                            página.
                                        </>
                                    ),
                                },
                                {
                                    key: <Badge>Ambos</Badge>,
                                    value: "Versão Java, token, limite de repositórios e opções de execução são da plataforma e valem para os dois tipos.",
                                },
                            ]}
                        />
                        <Callout tone="tip" title="Qual escolher?">
                            Quer projetos que <em>usam</em> uma biblioteca (Mockito, JUnit 5,
                            Testcontainers)? Use <strong>Code Search</strong> buscando no{" "}
                            <Code>pom.xml</Code>. Quer filtrar por popularidade, data, licença ou
                            atividade? Use <strong>Repository Search</strong>. Dá para combinar: em
                            Code Search, filtre por dono com <Code>org:</Code>/<Code>user:</Code>.
                        </Callout>
                    </Section>

                    {/* ------------------------------------------------ Sintaxe */}
                    <Section id="sintaxe" title="Sintaxe de valores" icon={<Code2 className="h-5 w-5 text-indigo-400" />}>
                        <p>
                            Campos numéricos (Stars, Forks, Tamanho, Seguidores, Quantidade de tópicos,
                            Good first issues, Help wanted issues) aceitam a mesma sintaxe de intervalos
                            do GitHub:
                        </p>
                        <DefinitionTable
                            head={["Formato", "Significado"]}
                            rows={[
                                { key: <Code>n</Code>, value: "Exatamente n. Ex.: 50" },
                                { key: <Code>&gt;n</Code>, value: "Maior que n. Ex.: >100" },
                                { key: <Code>&gt;=n</Code>, value: "Maior ou igual a n. Ex.: >=100" },
                                { key: <Code>&lt;n</Code>, value: "Menor que n. Ex.: <1000" },
                                { key: <Code>&lt;=n</Code>, value: "Menor ou igual a n. Ex.: <=1000" },
                                { key: <Code>n..m</Code>, value: "Entre n e m, inclusive. Ex.: 10..50" },
                                { key: <Code>n..*</Code>, value: "n ou mais (equivale a >=n). Ex.: 10..*" },
                                { key: <Code>*..n</Code>, value: "n ou menos (equivale a <=n). Ex.: *..10" },
                            ]}
                        />
                        <p>
                            Datas usam o formato <Code>AAAA-MM-DD</Code>. Os seletores de data do formulário
                            já montam <Code>&gt;=data</Code>. Para um intervalo de datas (ex.: criados em 2022),
                            escreva direto na query: <Code>created:2022-01-01..2022-12-31</Code>.
                        </p>
                        <p>Operadores e recursos que podem ser usados na query:</p>
                        <DefinitionTable
                            head={["Recurso", "Exemplo"]}
                            rows={[
                                { key: "Frase exata", value: <Code>"spring boot starter"</Code> },
                                { key: "Excluir termo", value: <Code>mockito NOT powermock</Code> },
                                { key: "Excluir qualificador", value: <><Code>-org:spring-projects</Code> (tudo menos essa organização)</> },
                                { key: "Qualificador direto", value: <Code>junit-jupiter filename:pom.xml org:apache</Code> },
                            ]}
                        />
                    </Section>

                    {/* ------------------------------------------------ Campos */}
                    <Section id="campos" title="Campos de pesquisa" icon={<SlidersHorizontal className="h-5 w-5 text-indigo-400" />}>
                        <p>
                            Referência de todos os campos da tela Mineração. Os campos principais ficam
                            sempre visíveis; os demais aparecem ao clicar em{" "}
                            <strong>Filtros avançados</strong>. O selo colorido indica em qual tipo de busca
                            o campo é aplicado.
                        </p>
                        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-700/60 bg-zinc-800/60 p-3">
                            <div className="relative min-w-[14rem] flex-1">
                                <Filter className="absolute left-3 top-2.5 h-4 w-4 text-zinc-500" />
                                <input
                                    type="text"
                                    value={fieldFilter}
                                    onChange={(event) => setFieldFilter(event.target.value)}
                                    placeholder="Procurar campo (ex.: stars, licença)…"
                                    className="w-full rounded-lg border border-zinc-700 bg-zinc-900 py-2 pl-9 pr-3 text-sm text-zinc-100 placeholder-zinc-500 focus:border-indigo-500 focus:outline-none"
                                />
                            </div>
                            <div className="flex gap-1 rounded-lg border border-zinc-700 bg-zinc-900 p-1 text-xs">
                                {([
                                    ["all", "Todos"],
                                    ["code", "Code Search"],
                                    ["repositories", "Repository Search"],
                                ] as const).map(([value, label]) => (
                                    <button
                                        key={value}
                                        type="button"
                                        onClick={() => setAppliesFilter(value)}
                                        className={`rounded-md px-2.5 py-1 font-semibold transition ${
                                            appliesFilter === value
                                                ? "bg-indigo-600 text-white"
                                                : "text-zinc-400 hover:text-zinc-100"
                                        }`}
                                    >
                                        {label}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {FIELD_GROUPS.map((group) => {
                            const groupFields = filteredFields.filter((field) => field.group === group);
                            if (groupFields.length === 0) return null;
                            return (
                                <div key={group} className="space-y-3">
                                    <h3 className="pt-2 text-base font-semibold text-zinc-100">{group}</h3>
                                    <div className="grid gap-3 lg:grid-cols-2">
                                        {groupFields.map((field) => (
                                            <FieldCard key={field.label} field={field} />
                                        ))}
                                    </div>
                                </div>
                            );
                        })}
                        {filteredFields.length === 0 && (
                            <p className="text-center text-zinc-500">Nenhum campo encontrado.</p>
                        )}
                    </Section>

                    {/* ------------------------------------------------ Opções */}
                    <Section id="opcoes" title="Opções de execução" icon={<PlayCircle className="h-5 w-5 text-indigo-400" />}>
                        <p>
                            As caixas de seleção abaixo do formulário definem <strong>o quanto</strong> cada
                            candidato será analisado. Quanto mais completa a análise, mais lenta a execução.
                        </p>
                        <div className="grid gap-3 lg:grid-cols-2">
                            {OPTIONS.map((option) => (
                                <Card key={option.label}>
                                    <p className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
                                        <CheckCircle2 className="h-4 w-4 text-indigo-400" />
                                        {option.label}
                                    </p>
                                    <div className="mt-2 text-sm leading-6 text-zinc-300">{option.description}</div>
                                    {option.tip && <p className="mt-2 text-xs text-zinc-400">{option.tip}</p>}
                                </Card>
                            ))}
                        </div>
                        <h3 className="pt-2 text-base font-semibold text-zinc-100">Modos resultantes</h3>
                        <DefinitionTable
                            head={["Combinação", "O que acontece"]}
                            rows={[
                                { key: "Nenhuma marcada", value: "Somente busca + filtro de versão Java. Rápido; nada é clonado ou compilado (status “Minerado”)." },
                                { key: "Buildáveis", value: "Busca + clone + compilação. Testes não são detectados nem executados." },
                                { key: "Testes aprovados", value: "Busca + clone + compilação + detecção e execução dos testes." },
                            ]}
                        />
                        <Callout tone="info">
                            A linha <strong>Execução</strong> logo abaixo do botão mostra, antes de
                            começar, qual desses modos será usado e se o JDK será exato ou com upgrade.
                        </Callout>
                    </Section>

                    {/* ------------------------------------------------ Execução */}
                    <Section id="execucao" title="Acompanhando a execução" icon={<Timer className="h-5 w-5 text-indigo-400" />}>
                        <p>
                            Ao clicar em <strong>Iniciar Mineração</strong>, o backend cria uma execução em
                            segundo plano e a interface consulta o andamento a cada 5 segundos. A tabela é
                            preenchida lote a lote, então dá para ver resultados antes do fim.
                        </p>
                        <p className="font-semibold text-zinc-100">Status da execução</p>
                        <DefinitionTable
                            head={["Status", "Significado"]}
                            rows={RUN_STATUSES.map((item) => ({ key: <Code>{item.value}</Code>, value: item.meaning }))}
                        />
                        <p className="font-semibold text-zinc-100">Etapa atual (exibida após o status)</p>
                        <DefinitionTable
                            head={["Etapa", "Significado"]}
                            rows={PROGRESS_STAGES.map((item) => ({ key: <Code>{item.value}</Code>, value: item.meaning }))}
                        />
                        <p className="font-semibold text-zinc-100">Informações e botões da barra da execução</p>
                        <DefinitionTable
                            head={["Item", "Descrição"]}
                            rows={[
                                { key: <Badge>Run #N</Badge>, value: "Identificador da execução. Use-o na tela Início para reabrir." },
                                { key: "Barra de progresso", value: "Candidatos analisados / total de candidatos, com aceitos e eliminados." },
                                { key: "Total da resposta", value: "Quantidade de repositórios devolvidos pela execução." },
                                { key: "Testes analisados / ignorados", value: "Indica se essa execução rodou os testes." },
                                { key: "Página / índice", value: "Em qual página do GitHub e em qual item a busca parou." },
                                { key: "Lote", value: "Quantos candidatos são analisados por vez." },
                                { key: "Aceitação", value: "Percentual de candidatos aceitos até agora." },
                                { key: <strong>Cancelar</strong>, value: "Interrompe uma execução queued/running. O que já foi aceito fica salvo." },
                                {
                                    key: <strong>Retomar consulta</strong>,
                                    value: "Aparece quando a execução foi cancelada ou falhou antes de atingir o limite. Continua exatamente de onde parou, sem repetir candidatos.",
                                },
                                { key: <strong>Ver estatísticas</strong>, value: "Abre a tela Estatísticas (habilitado quando há estatísticas)." },
                            ]}
                        />
                        <Callout tone="warning" title="Quando não dá para retomar">
                            Se aparecer “todas as páginas disponíveis no GitHub para essa busca já foram
                            esgotadas”, o GitHub não tem mais resultados para essa query. Para encontrar
                            mais repositórios, crie uma nova busca com outra query ou filtros diferentes.
                        </Callout>
                    </Section>

                    {/* ------------------------------------------------ Resultados */}
                    <Section id="resultados" title="Tabela de resultados" icon={<Table2 className="h-5 w-5 text-indigo-400" />}>
                        <p>
                            Acima da tabela há quatro indicadores rápidos: <strong>Total Encontrado</strong>,{" "}
                            <strong>Taxa de Compilação</strong>, <strong>Testes com Sucesso</strong> e{" "}
                            <strong>Upgrades de JDK</strong> (quantos usaram um JDK diferente do declarado).
                        </p>
                        <DefinitionTable
                            head={["Coluna", "O que mostra"]}
                            rows={[
                                { key: "Repositório", value: "Nome no formato dono/nome." },
                                {
                                    key: "Versão Java",
                                    value: (
                                        <>
                                            JDK efetivamente usado. O selo <Badge tone="amber">Upgraded</Badge>{" "}
                                            indica que foi preciso um JDK maior que o declarado (passe o mouse para
                                            ver a versão declarada).
                                        </>
                                    ),
                                },
                                { key: "Compilação", value: "OK, Falhou ou Não analisado, com o tempo do build." },
                                { key: "Testes", value: "Passaram, Falharam, Sem testes ou Ignorado (quando a execução não rodou testes), com o tempo." },
                                {
                                    key: "Status Final",
                                    value: (
                                        <>
                                            <Badge tone="emerald">Aprovado</Badge>, o estágio de eliminação em
                                            vermelho, ou “Minerado” quando não houve análise.
                                        </>
                                    ),
                                },
                                { key: "Origem", value: "Qual query (custom-search-N) encontrou o repositório, o arquivo correspondente e o commit analisado." },
                                { key: "Ações", value: "Detalhes (abre o modal) e Link (abre o repositório no GitHub)." },
                            ]}
                        />
                        <h3 className="pt-2 text-base font-semibold text-zinc-100">Filtros da tabela</h3>
                        <p>
                            A barra acima da tabela filtra apenas o que já foi carregado, sem nova chamada ao
                            GitHub: por <strong>nome</strong>, por <strong>versão Java</strong> e pelas
                            caixas <strong>Buildáveis</strong> e <strong>Testes OK</strong>.
                        </p>
                        <Callout tone="warning">
                            As caixas <strong>Buildáveis</strong> e <strong>Testes OK</strong> da tabela são
                            as mesmas opções do formulário. Alterá-las também muda o que será usado na
                            próxima mineração.
                        </Callout>
                        <h3 className="pt-2 text-base font-semibold text-zinc-100">Modal de detalhes</h3>
                        <ul className="list-disc space-y-1 pl-5">
                            <li><strong>Tempo de compilação</strong> e <strong>tempo de testagem</strong>.</li>
                            <li><strong>Frameworks de teste</strong> detectados (JUnit 4, JUnit 5, JUnit Vintage, TestNG, Spock, Cucumber, Karate).</li>
                            <li><strong>Bibliotecas de mock</strong> (Mockito, EasyMock, JMock, PowerMock, WireMock, MockServer, MockWebServer).</li>
                            <li><strong>Bibliotecas de asserção</strong> (AssertJ, Hamcrest, Truth, Awaitility, JSONAssert, XMLUnit).</li>
                            <li><strong>Ferramentas de teste de integração</strong> (Spring Test, Spring Boot Test, Testcontainers, REST Assured, Arquillian).</li>
                            <li>O <strong>log de erro</strong>, quando o repositório foi eliminado.</li>
                        </ul>
                    </Section>

                    {/* ------------------------------------------------ Eliminação */}
                    <Section id="eliminacao" title="Estágios de eliminação" icon={<XCircle className="h-5 w-5 text-rose-400" />}>
                        <p>
                            Quando um candidato não cumpre algum critério, ele é <strong>eliminado</strong> e
                            recebe o estágio em que parou. Esses nomes aparecem na coluna Status Final e no
                            painel “Maiores estágios de erro”.
                        </p>
                        <DefinitionTable
                            head={["Estágio", "Motivo"]}
                            rows={ELIMINATION_STAGES.map((item) => ({
                                key: <Code>{item.stage}</Code>,
                                value: item.meaning,
                            }))}
                        />
                        <Callout tone="info">
                            Cada repositório tem no máximo 15 minutos no total para ser analisado. Para ver
                            os eliminados na tabela, marque “Salvar repositórios eliminados” antes de iniciar.
                        </Callout>
                    </Section>

                    {/* ------------------------------------------------ Estatísticas */}
                    <Section id="estatisticas" title="Estatísticas" icon={<BarChart3 className="h-5 w-5 text-indigo-400" />}>
                        <p>
                            A tela Estatísticas mostra os indicadores da execução carregada no escopo
                            escolhido (Aceitos, Todos filtrados ou Eliminados). Os painéis de eliminação só
                            aparecem quando a execução salvou os eliminados.
                        </p>
                        <DefinitionTable
                            head={["Painel", "O que mostra"]}
                            rows={[
                                { key: "Cartões-resumo", value: "Total no escopo, total analisado, taxa de testes com sucesso, taxa de eliminação e percentual com testes." },
                                { key: "Funil de análise", value: "Pesquisados → Analisados → Compilaram → Com testes → Testes OK → Aceitos." },
                                { key: "Java declarado", value: "Distribuição das versões Java declaradas no pom.xml." },
                                { key: "Java declarado x efetivo", value: "Quantos usaram a mesma versão e quantos precisaram de upgrade de JDK." },
                                { key: "Frameworks / Mocks / Asserções / Integração", value: "Contagem e percentual de cada ferramenta de teste detectada." },
                                { key: "Tempo por etapa", value: "Tempo médio, mínimo, máximo e total de compilação e de testagem." },
                                { key: "Relação com testes", value: "Repositórios com e sem testes." },
                                { key: "Maiores estágios de erro", value: "Em quais estágios os eliminados pararam." },
                                { key: "Aceitos x eliminados", value: "Proporção entre aceitos e eliminados." },
                                { key: "Compilaram e reprovaram nos testes por Java", value: "Por versão Java, quantos compilaram mas falharam nos testes." },
                                { key: "Taxa de compilação por build / por framework", value: "Sucesso de compilação agrupado por ferramenta de build e por framework de teste." },
                            ]}
                        />
                    </Section>

                    {/* ------------------------------------------------ Limites */}
                    <Section id="limites" title="Limites e boas práticas" icon={<AlertTriangle className="h-5 w-5 text-amber-400" />}>
                        <DefinitionTable
                            head={["Limite", "Detalhe"]}
                            rows={[
                                { key: "Resultados por busca", value: "O GitHub devolve no máximo 1.000 resultados por query. Para ir além, divida em várias queries (ex.: por faixa de estrelas ou de datas)." },
                                { key: "Taxa da API de busca", value: "Com token: 30 requisições/min na busca de repositórios e 10 requisições/min na busca de código. Sem token: 10/min e a busca de código não funciona." },
                                { key: "Busca de código", value: "Só indexa a branch padrão e arquivos menores que 384 KB." },
                                { key: "Tamanho da query", value: "Até 256 caracteres de texto e no máximo 5 operadores AND/OR/NOT." },
                                { key: "Tempos da análise", value: "Clone: 5 min · Compilação: 5 min · Testes: 10 min · Total por repositório: 15 min." },
                            ]}
                        />
                        <Callout tone="tip" title="Boas práticas">
                            <ul className="list-disc space-y-1 pl-5">
                                <li>Comece com um limite pequeno (5–10) para validar os filtros antes de rodar uma busca grande.</li>
                                <li>Use várias queries em vez de uma query enorme: cada uma tem sua própria cota de 1.000 resultados.</li>
                                <li>Na busca de repositórios, filtre por <Code>size</Code> e <Code>pushed</Code> para evitar projetos gigantes ou abandonados.</li>
                                <li>Ative “Salvar repositórios eliminados” quando quiser estudar <em>por que</em> os projetos falham.</li>
                                <li>Anote o Run ID; se algo interromper a execução, é só carregá-la e clicar em Retomar.</li>
                            </ul>
                        </Callout>
                    </Section>

                    {/* ------------------------------------------------ FAQ */}
                    <Section id="faq" title="Perguntas frequentes" icon={<Lightbulb className="h-5 w-5 text-emerald-400" />}>
                        {[
                            {
                                q: "Preenchi Stars/Forks, mas os resultados não respeitaram o filtro.",
                                a: "Esses filtros só existem na Repository Search. Com Code Search selecionado eles são ignorados. Troque o Tipo de Busca ou use org:/user:/repo: para restringir.",
                            },
                            {
                                q: "A execução terminou com poucos repositórios.",
                                a: "Muitos candidatos podem ter sido eliminados (versão Java, compilação, testes). Marque “Salvar repositórios eliminados” e consulte o painel “Maiores estágios de erro”. Se a busca foi esgotada, amplie a query.",
                            },
                            {
                                q: "Aparece “failed” logo no começo.",
                                a: "Normalmente é token ausente/inválido ou limite da API do GitHub atingido. Confira o token e aguarde um minuto antes de retomar.",
                            },
                            {
                                q: "Muitos repositórios eliminados em jdk_resolution.",
                                a: "O projeto exige um JDK maior do que o declarado. Marque “Permitir upgrade automático do JDK”.",
                            },
                            {
                                q: "Fechei o navegador no meio da mineração. Perdi tudo?",
                                a: "Não. A execução roda no backend e os resultados ficam no banco. Na tela Início, carregue o Run ID.",
                            },
                        ].map((item) => (
                            <Card key={item.q}>
                                <p className="flex items-start gap-2 font-semibold text-zinc-100">
                                    <Database className="mt-1 h-4 w-4 shrink-0 text-indigo-400" />
                                    {item.q}
                                </p>
                                <p className="mt-1 pl-6 text-zinc-400">{item.a}</p>
                            </Card>
                        ))}
                    </Section>
                </div>
            </div>
        </div>
    );
}
