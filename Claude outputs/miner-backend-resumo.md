# Como o miner-backend funciona (e o que mudou em relação ao código anterior)

> Texto de apoio para gerar slides. Cada seção abaixo corresponde, em geral, a um ou mais slides. Compare com `github_java_miner.py` (minerador antigo) e `analyzer.py` (analisador antigo), da pasta `repos-tcc`.

## 1. O que o miner-backend é

O miner-backend é uma API em **Python + FastAPI** que substitui os dois scripts de linha de comando do projeto anterior por um **serviço único, assíncrono e persistente**. Ele expõe endpoints REST para minerar repositórios Java no GitHub, analisá-los (clonar, compilar, rodar testes) e consultar estatísticas — tudo isso guardado em um banco **SQLite** que serve de fonte única de verdade.

Na versão anterior existiam dois programas independentes, executados manualmente no terminal:
- `github_java_miner.py`: buscava repositórios no GitHub e salvava um `repositories.json`.
- `analyzer.py`: lia esse `repositories.json`, clonava cada repositório, compilava e rodava os testes, salvando um `output.json`.

Era preciso rodar um, esperar terminar, depois rodar o outro manualmente, e por fim rodar um terceiro script (`generate_charts.py`) para gerar gráficos a partir do `output.json`. Não havia banco de dados, API, nem interface — só arquivos JSON/CSV e logs em texto.

## 2. Estrutura do código

- `app/main.py` — cria a aplicação FastAPI, configura CORS e registra as rotas.
- `app/core/config.py` — configurações via variáveis de ambiente (token do GitHub, URL do banco, etc.), usando `pydantic-settings`.
- `app/core/database.py` + `database.sql` — schema do banco SQLite com **8 tabelas** (`mining_runs`, `search_filters`, `repositories`, `run_repositories`, `mining_run_candidates`, `analysis_results`, `analysis_cache`, `run_statistics`) e um mecanismo de **migração automática de colunas** (`ALTER TABLE` aplicado sozinho quando uma coluna nova é adicionada ao código), sem precisar de migrations manuais.
- `app/api/routes/repositories.py` e `health.py` — endpoints da API.
- `app/schemas/` — modelos de request/response e estruturas internas (`RepoCandidate`, `MinedRepo`).
- `app/services/filters.py` — construtor genérico de queries de busca do GitHub.
- `app/services/miner.py` — busca de candidatos no GitHub (Code Search / Repository Search), sessão HTTP com retry e controle de rate limit.
- `app/services/analyzer.py` — pipeline de clone → resolução de JDK → compilação → testes → detecção de ferramentas de teste.
- `app/services/mining_runner.py` — o orquestrador: pagina, decide tamanho de lote, usa cache, salva checkpoints, atualiza progresso.
- `app/services/persistence.py` — toda a leitura/escrita no banco.
- `app/services/persistence_policy.py` — decide se um repositório eliminado deve ou não ser salvo.
- `app/services/statistics.py` — motor de agregação de estatísticas.

## 3. Como um "run" (execução de mineração) funciona, passo a passo

1. **`POST /repositories/search`** recebe os filtros e as opções da busca (linguagem, estrelas, versão Java alvo, quantidade máxima de repositórios, número de workers, se exige que o projeto compile, se exige que os testes passem, se permite upgrade automático de JDK, se deve persistir repositórios eliminados, se deve calcular estatísticas, escopo das estatísticas, etc.). Cria uma linha em `mining_runs` com status `queued` e **retorna imediatamente** (HTTP 202) com um `run_id` — o processamento roda em segundo plano (`BackgroundTasks` do FastAPI), então a API nunca fica bloqueada esperando o trabalho pesado terminar.
2. Um **semáforo global** garante que só um run pesado processe por vez, evitando estourar os limites de taxa da API do GitHub quando várias buscas são disparadas.
3. O runner busca páginas de candidatos no GitHub (via `miner.py`), aplicando uma **rejeição precoce e barata** (ex.: versão de Java inválida ou regra de conteúdo que não bate) antes de gastar tempo clonando/compilando qualquer coisa.
4. Os candidatos sobreviventes são agrupados em **lotes de tamanho adaptativo** (`calculate_analyzer_batch_size`), calculado a partir de quantos repositórios ainda faltam e de quantos workers de análise existem.
5. Para cada candidato, o sistema primeiro verifica um **cache de análise** (`analysis_cache`, chaveado por commit + opções de teste/upgrade de JDK). Se aquele exato commit já foi analisado com as mesmas opções, o resultado é reaproveitado — **sem clonar, compilar ou testar de novo**. Isso é uma capacidade nova: no código antigo, toda execução recomeçava do zero, clonando e compilando tudo de novo mesmo que nada tivesse mudado.
6. Só os candidatos realmente novos passam pelo `analyzer.py`: clone raso com retry/backoff, resolução do JDK correto, tentativa de compilação, e testes (opcional — pode ser pulado quando só interessa saber se compila).
7. Cada resultado (aceito **ou** eliminado) é persistido, com o **estágio e a mensagem do erro** registrados (`error_stage`/`error_message`), tornando as eliminações auditáveis — não são simplesmente descartadas como no script antigo.
8. O progresso é salvo continuamente (página atual, tamanho de página, taxa de aceitação estimada, índice do último item processado, flag de "esgotado"), permitindo **retomar exatamente de onde parou** via `POST /repositories/runs/{id}/resume`, caso o processo seja cancelado ou interrompido.
9. Um estimador de **taxa de aceitação** (média móvel exponencial) prevê quantos candidatos brutos ainda são necessários para atingir a meta, e um mecanismo de **corte de busca improdutiva** encerra automaticamente um run que já acumulou centenas de rejeições e zero aceitos — evitando desperdiçar cota da API do GitHub à toa. O script antigo não tinha nenhuma proteção equivalente.
10. `GET /repositories/runs/{id}`, `.../repositories` e `.../statistics` permitem consultar status, listar os repositórios já analisados com todos os metadados, e obter (ou reaproveitar, se já calculado) o pacote de estatísticas do run.
11. `POST /repositories/filter` permite filtrar uma lista de repositórios já buscada (por versão Java, nome, eliminado/tem-testes/testes-passaram) sem precisar consultar o GitHub de novo.

## 4. O que o analisador (dentro do backend) melhora em relação ao `analyzer.py` antigo

- **Resolução de JDK configurável**: no script antigo, os caminhos dos JDKs eram **caminhos absolutos fixos no código** (ex.: `/home/laris/.sdkman/candidates/java/17.0.10-tem`), só funcionando naquela máquina específica. No backend atual, o diretório base do SDKMAN e o `JAVA_HOME` vêm de **variáveis de ambiente**, tornando o pipeline portátil.
- **Upgrade de JDK agora é opcional (`allow_jdk_upgrade`)**: antes, o script sempre fazia upgrade automático de JDK quando necessário, sem opção de desligar. Agora isso é um parâmetro configurável por busca.
- **Prazo total por repositório (`TIMEOUT_REPOSITORY`)**: além dos timeouts por etapa (clone, compilação, teste) que já existiam, foi adicionado um **prazo global por repositório** (900s), evitando que um único repositório problemático consuma tempo indefinido somando várias tentativas.
- Mantém e reaproveita todo o diagnóstico inteligente de falhas de compilação já existente no script antigo (versão insuficiente do bytecode, conflito de `-source`/`-target`, submódulos ausentes, falhas de infraestrutura de teste como Selenium/Appium sem driver) — ou seja, essa parte foi preservada, não jogada fora.

## 5. As novas estatísticas de ferramentas de teste (o diferencial deste ciclo de trabalho)

O script antigo só registrava **um único campo** `test_framework`, e mesmo assim de forma limitada: era detectado *durante a mineração* (checando só `Mockito`/`TestNG` no `pom.xml`, via regex fixas), não durante a análise real do projeto.

O backend atual detecta, durante a análise de cada repositório, **quatro categorias independentes**, cada uma com seu próprio dicionário de padrões (`TEST_FRAMEWORK_PATTERNS`, `MOCK_LIBRARY_PATTERNS`, `ASSERTION_LIBRARY_PATTERNS`, `INTEGRATION_TEST_TOOL_PATTERNS`), permitindo que um mesmo projeto apareça, por exemplo, como `JUnit 5 + TestNG` (frameworks), `Mockito` (mock), `AssertJ` (asserção) e `Testcontainers` (integração) ao mesmo tempo:

- **`test_frameworks`** — JUnit 4/5, TestNG, Spock, etc.
- **`mock_libraries`** — Mockito, EasyMock, PowerMock, etc.
- **`assertion_libraries`** — AssertJ, Hamcrest, Truth, etc.
- **`integration_test_tools`** — Testcontainers, WireMock, RestAssured, etc.

Além disso, o backend agora **mede o tempo real de cada etapa**:

- **`compile_duration_seconds`** — tempo do início ao fim da etapa de compilação.
- **`test_duration_seconds`** — tempo do início ao fim da etapa de testes.

Tudo isso é persistido por repositório (tabelas `analysis_results`/`analysis_cache`) e **agregado automaticamente** pelo `statistics.py`, que calcula, para o escopo escolhido (aceitos / todos / eliminados):

- Distribuição (contagem e %) de cada uma das quatro categorias de ferramentas de teste.
- Estatísticas de duração — `count`, `total_seconds`, `average_seconds`, `min_seconds`, `max_seconds` — separadamente para a etapa de **compilação** e para a etapa de **testagem**.
- Funil de análise (buscados → analisados → compilaram → têm testes → testes passaram → aceitos), versões de Java declaradas x efetivas (mostrando quantos projetos precisaram de upgrade de JDK), taxa de sucesso de compilação por build tool e por framework de teste, e ranking dos estágios que mais eliminam repositórios.

Essas métricas eram exatamente o que faltava para permitir uma análise quantitativa (tempos de build/teste e ecossistema de ferramentas de teste usadas) que o pipeline anterior não conseguia produzir de forma alguma.

## 6. Resumo das melhorias em relação ao código anterior (para o slide de "comparação")

1. Une dois scripts desconexos (minerador + analisador, rodados manualmente) em **um único serviço com API REST**.
2. Troca arquivos soltos (`CSV`/`JSON`/`checkpoint.json`) por um **banco relacional SQLite** com 8 tabelas e migração automática de schema.
3. Processamento **assíncrono e não bloqueante** (fila de background tasks) em vez de scripts síncronos rodados na mão.
4. **Retomada granular** (por candidato/página, com estimativa de taxa de aceitação) em vez de apenas reaproveitar o que já tinha sido processado.
5. **Cache de análise** por commit — evita reclonar/recompilar/retestar repositórios já vistos.
6. **Configuração portátil de JDKs** via variáveis de ambiente, em vez de caminhos fixos de uma máquina.
7. Upgrade automático de JDK agora é **opcional e configurável**, não implícito.
8. **Quatro categorias de ferramentas de teste** detectadas separadamente, em vez de um único campo genérico.
9. **Medição de tempo** de compilação e de testagem por repositório — inexistente antes.
10. Estatísticas ricas calculadas **sob demanda via API** (e cacheadas no banco), substituindo o script offline `generate_charts.py`.
11. Proteções operacionais novas: semáforo global de concorrência, corte automático de busca improdutiva, timeout total por repositório.
12. Toda eliminação é registrada com estágio e mensagem de erro, tornando o processo **auditável**.

---

### Sugestão de divisão em slides
1. Título + objetivo do backend.
2. Problema do código anterior (dois scripts manuais, sem API, sem banco).
3. Arquitetura do backend (diagrama de pastas/serviços).
4. Fluxo de um run (passo a passo, pode virar um diagrama de etapas).
5. Cache de análise e retomada de execução (a melhoria de performance/robustez).
6. As 4 categorias de ferramentas de teste + tempos de compilação/testagem (o destaque central).
7. Estatísticas geradas pela API.
8. Quadro-resumo "antes x depois".
