# Como o miner-front funciona (e o que ele traz de novo em relação ao código anterior)

> Texto de apoio para gerar slides. O ponto central deste texto é que, na versão anterior do projeto (`repos-tcc`), **não existia nenhuma interface** — tudo era feito por scripts de terminal e um script separado de geração de gráficos. O miner-front é, portanto, uma capacidade inteiramente nova.

## 1. O que o miner-front é

É uma aplicação web (**SPA**) construída com **React 19 + TypeScript + Vite + Tailwind CSS**, que consome a API do miner-backend e transforma todo o fluxo de mineração/análise em um **painel interativo em tempo real**, acessível pelo navegador — sem precisar editar código, variáveis de ambiente ou rodar comandos no terminal.

Na versão anterior:
- Não havia interface nenhuma.
- Para minerar, era preciso editar constantes no topo do `github_java_miner.py` (queries, filtros de estrelas/data) e rodá-lo via linha de comando com variáveis de ambiente.
- Para analisar, era preciso rodar `analyzer.py` manualmente depois, apontando para o `repositories.json` gerado.
- O único "retorno visual" vinha dos logs impressos no terminal (`tqdm`, linhas de log) e, ao final, de métricas de texto (`print_metrics`).
- Gráficos só existiam se alguém rodasse depois, manualmente, o script `generate_charts.py`, lendo o `output.json` já finalizado — um processo totalmente offline e desconectado da execução.

## 2. Estrutura da aplicação

- **`App.tsx`** — casca da aplicação: barra lateral com 3 seções (Início, Mineração, Estatísticas) e roteamento simples entre 3 telas.
  - **Início**: permite iniciar uma busca nova **ou** carregar uma execução (`run`) antiga só informando o número do `run_id` — mostrando que a plataforma agora tem "memória" entre sessões, algo que os scripts avulsos nunca tiveam.
  - **Mineração** (`MiningDashboard.tsx`) — o "cockpit" operacional.
  - **Estatísticas** (`StatisticsPage.tsx`) — o painel analítico.
- **`src/api/repositories.ts`** — cliente HTTP tipado para a API do backend. Encapsula o padrão "iniciar run → consultar (`poll`) a cada poucos segundos → repassar progresso" em uma única função assíncrona com um *callback* de progresso, de forma que qualquer componente da tela recebe atualizações ao vivo enquanto o backend processa em segundo plano.
- **`src/models/types.ts`** — tipos TypeScript espelhando exatamente os esquemas do backend (`AnalyzedRepo`, `RepositoryStatistics`, `MiningRunStatus`, `SearchFormData`, etc.), mantendo front e back sincronizados e pegando incompatibilidades em tempo de compilação (`tsc -b`), não em produção.

## 3. `MiningDashboard.tsx` — o painel operacional

**Formulário de busca extenso e configurável**, cobrindo praticamente todos os qualificadores de busca do GitHub que o backend suporta:
- múltiplas queries de texto livre (pode adicionar/remover dinamicamente);
- tipo de busca — *Code Search* (procura dentro de `pom.xml`) ou *Repository Search* (nome/descrição/README/tópicos);
- token do GitHub, versão de Java alvo, faixas de estrelas/forks/tamanho, linguagem, tópico, licença, visibilidade, usuário/organização/repositório, seguidores, flags de fork/arquivado/mirror/template, quantidade de *good first issues*/*help wanted*, `filename`/`extension`/`path` (para busca de código), ordenação e itens por página;
- cinco interruptores operacionais: **somente repositórios buildáveis**, **somente com testes aprovados**, **salvar repositórios eliminados**, **permitir upgrade automático de JDK**, **calcular estatísticas** — e um seletor de **escopo das estatísticas** (aceitos / todos / eliminados).

**Monitoramento ao vivo** enquanto a busca roda: barra de progresso (candidatos processados/total), rótulo de status (`queued`/`running`/`completed`/`failed`/`cancelled`) e a **tabela de resultados preenchendo em tempo real**, lote por lote — não é preciso esperar o run inteiro terminar para começar a ver repositórios, ao contrário do script antigo, em que só se via progresso como texto no terminal e as métricas finais só no fim de tudo.

**Controles de ciclo de vida do run**: botão para **cancelar** uma busca em andamento e botão para **retomar** uma busca pausada/interrompida/com páginas esgotadas exatamente do ponto em que parou (chama o endpoint de retomada do backend) — uma capacidade que simplesmente não existia antes.

**Tabela de resultados por repositório**, mostrando: nome, versão Java declarada x efetiva (com um selo "Upgraded" quando o backend precisou subir o JDK para conseguir compilar), status de compilação, status de testes, status final (Aprovado / Eliminado + em qual estágio), origem (filtro/arquivo/commit que casou) e ações (abrir no GitHub e ver detalhes).

**Novidade deste ciclo — modal de "Detalhes" por repositório**, mostrando:
- tempo de compilação e tempo de testagem, formatados de forma legível (ex.: `1m 05s`);
- "chips" com todos os *frameworks* de teste, bibliotecas de mock, bibliotecas de asserção e ferramentas de teste de integração detectadas naquele repositório específico;
- o log de erro capturado, quando o repositório foi eliminado.

Além do modal, pequenas indicações de tempo (badges) aparecem agora **diretamente nas colunas de Compilação e Testes** da tabela, então esse nível de detalhe técnico — que antes ficava enterrado dentro de um arquivo JSON — passa a ser visível e explorável direto na interface, sem precisar abrir nenhum arquivo.

**Filtros rápidos do lado do cliente** sobre os resultados já carregados (busca por nome, filtro por versão Java, "somente buildáveis"/"somente testes aprovados"), permitindo explorar sem gerar novas chamadas à API.

## 4. `StatisticsPage.tsx` — o painel analítico (substitui o `generate_charts.py`)

Renderiza o pacote de estatísticas rico que o backend calcula:
- **Cartões-resumo**: total no escopo, taxa de sucesso de testes, taxa de eliminação, taxa de "tem testes".
- **Funil de análise**: buscados → analisados → compilaram → têm testes → testes passaram → aceitos.
- **Java declarado x efetivo**: distribuições separadas e a comparação entre as duas (quantos projetos precisaram de upgrade de JDK).
- **Quatro painéis de ferramentas de teste**: Frameworks de teste, Bibliotecas de mock, Bibliotecas de asserção e Ferramentas de teste de integração — cada um com contagem e percentual por valor detectado.
- **Painel "Tempo por etapa"**: tempo médio (e min/máx/total) de **compilação** e de **testagem**, agregados sobre todo o run.
- **Relação com testes, estágios de eliminação, aceitos x eliminados**, e taxas de compilação por *build tool* e por *framework* de teste.
- Tudo isso é calculado **sob demanda**, ao vivo, a partir do backend (ou recarregado instantaneamente do cache, se já tiver sido calculado antes), e pode alternar entre os escopos **aceitos / todos filtrados / eliminados** — algo que o script estático de gráficos nunca ofereceu (ele gerava um conjunto fixo de imagens por execução manual).

## 5. Resumo das melhorias em relação ao projeto anterior (para o slide de "comparação")

1. A própria existência de uma interface é a maior mudança: substitui "editar constantes no `.py` → rodar no terminal → esperar → rodar outro script de gráficos → olhar PNGs" por uma aplicação web persistente e interativa.
2. **Formulário guiado e validado** para todos os filtros de busca do GitHub, em vez de constantes fixas no topo de um script.
3. **Progresso ao vivo e resultados incrementais** durante a execução, em vez de apenas logs de texto no terminal.
4. **Controles de pausar/cancelar/retomar** uma busca — inexistentes antes.
5. **Reabertura de execuções passadas** por `run_id`, graças à camada de persistência do backend — os resultados de uma mineração deixam de "morrer" junto com o script.
6. **Detalhamento por repositório** de frameworks de teste, bibliotecas de mock, de asserção, ferramentas de integração e tempos de compilação/testagem — visível diretamente na tabela e em um modal de detalhes, sem precisar abrir nenhum JSON.
7. **Painel de estatísticas interativo**, com escopo selecionável, no lugar do script offline de geração de gráficos.
8. Front-end e back-end **tipados e sincronizados** (TypeScript espelhando os esquemas Python), reduzindo erros de integração.
9. Interface acessível a qualquer pessoa (inclusive o orientador), sem precisar tocar em código ou terminal.

---

### Sugestão de divisão em slides
1. Título + "antes não existia interface nenhuma".
2. Estrutura da aplicação (Início / Mineração / Estatísticas).
3. Formulário de busca (print/mock do formulário, destacando a quantidade de filtros).
4. Monitoramento ao vivo + controles de cancelar/retomar.
5. Tabela de resultados + o novo modal de "Detalhes" (frameworks/mocks/asserções/integração + tempos).
6. Painel de Estatísticas (funil, versões de Java, tempo por etapa).
7. Quadro-resumo "antes x depois".
