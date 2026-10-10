# Arquitetura

Preenchido em 2026-10-08 a partir do código (não foi rodado nesta data).

## Visão geral
- O **front** (React) chama a **API** (FastAPI) para criar uma *run*. A API devolve `202` com o Run ID e executa a mineração em segundo plano. O front consulta o status a cada 5 s até a run chegar a `completed`, `failed` ou `cancelled`.
- A API busca candidatos no GitHub, filtra pelo conteúdo (pom.xml, regras de conteúdo), e, se pedido, clona e analisa cada repositório com Maven e o JDK certo. Resultados e estatísticas vão para o SQLite.

## Onde fica cada coisa
| Módulo | Pasta | Linguagem/stack | Banco | Como roda |
|---|---|---|---|---|
| API | `miner-backend/app/main.py`, `api/routes/` | Python 3.13, FastAPI, Uvicorn | SQLite | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` ou Docker (porta interna 10000) |
| Busca no GitHub | `app/services/miner.py` (~1.200 linhas), `filters.py` | `requests`, sessão com rate limit e cache de resposta | — | chamado pela run |
| Orquestração da run | `app/services/mining_runner.py` | threads | grava checkpoint | `execute_mining_run` (BackgroundTasks) |
| Análise (clone, compila, testa) | `app/services/analyzer.py` (~1.200 linhas) | subprocess: git, Maven, JDK | — | usa `JDK_MAP` (SDKMAN) |
| Persistência | `app/services/persistence.py`, `persistence_policy.py`, `core/database.py` | sqlite3 | SQLite | schema de `core/database.sql` aplicado ao subir |
| Estatísticas | `app/services/statistics.py` | Python puro | grava em `run_statistics` | `build_statistics(repos, scope)` |
| Front | `miner-front/src/` (`App.tsx`, `components/MiningDashboard.tsx`, `StatisticsPage.tsx`, `DocumentationPage.tsx`, `api/repositories.ts`, `models/types.ts`) | React 19, TypeScript, Vite 8, Tailwind 3 | — | `npm run dev` (porta 5173) |

## Endpoints (prefixo `/repositories`, mais `/health`)
- `POST /search` cria a run (exige token do GitHub no corpo ou em `GITHUB_TOKEN`), responde 202.
- `POST /runs/{id}/resume`, `POST /runs/{id}/cancel`, `GET /runs/{id}`, `GET /runs/{id}/repositories`, `GET /runs/{id}/statistics`.
- `POST /filter` filtra uma lista de repositórios já carregada (versão Java, nome, eliminado, tem testes, testes passaram).

## Fluxos principais
1. **Nova busca**: `POST /search` → cria `mining_runs` (queued) e salva `search_filters` → `execute_mining_run` pega a vaga do semáforo global (**uma run por vez no processo**) → status `running`.
2. **Mineração por páginas**: `fetch_mining_page` busca uma página por filtro → `mine_candidates` (threads, `max_workers`) lê `pom.xml`/arquivo casado, extrai versão Java, aplica regras de conteúdo e pega o `commit_sha` → candidatos gravados em `mining_run_candidates`.
3. **Análise (opcional, `analyze`)**: `analyze_mined_repositories` (`analyzer_workers`) clona (3 tentativas), resolve o JDK pela versão declarada (com `allow_jdk_upgrade` pode subir), compila e roda testes. Timeouts: clone 300 s, compile 300 s, testes 600 s, repositório inteiro 900 s. Resultado reaproveitado do `analysis_cache` quando repositório + commit + `run_test_suite` já foram analisados.
4. **Aceitar/eliminar**: respeita `require_buildable` e `require_tests_passed`; para ao atingir `max_repos` (os excedentes ficam `rejected` com `max_repos_reached`) ou quando a busca é improdutiva (muitas rejeições seguidas, `MIN_UNPRODUCTIVE_REJECTIONS = 100`). A taxa de aceitação é suavizada para decidir o tamanho do lote.
5. **Fim**: `building_statistics` → `persisting` → `completed`. Etapas da run (`progress_stage`): `mining`, `mined`, `analyzing`, `building_statistics`, `persisting`.
6. **Retomar**: lê a run salva, refaz o payload com os filtros salvos e continua do `page_cursor`/candidatos já processados.

7. **Busca simples** (só na `main`; `should_run_simple_github_search`): sem analyzer e sem "salvar eliminados", a run só pagina a busca do GitHub até `max_repos`, sem checar `pom.xml`, versão Java, build nem testes. Com "salvar eliminados" ligado cai no fluxo incremental sem analyzer.
8. **Procura do `pom.xml`** (`candidate_pom_lookup_paths`, só na `main`): para a Code Search, tenta o `pom.xml` na pasta do arquivo encontrado e sobe até 6 níveis até a raiz, guardando `matched_pom_path`. O analyzer, porém, só aceita `pom.xml` na raiz.
9. **Erro 401 do GitHub**: `safe_get` levanta `GitHubAuthenticationError` pedindo um token válido.

## Ambiente de execução (observado em 2026-10-08)
- Backend: dentro do **WSL** (Ubuntu), `.venv` Linux (Python 3.14.4, o README diz 3.13), iniciado pela ação `backend-dev` da Medula (`wsl.exe ... uvicorn app.main:app --host 127.0.0.1 --port 8000`). Banco em `~/.miner-backend/...` dentro do WSL. Log em `medula/logs/backend-dev.log`.
- Front: Windows, `npm.cmd run dev`, ação `front-dev` (porta 5173; a Medula acusa a porta como fechada mas o Vite está de pé).
- Maven 3.9.12 e git no WSL; JDKs 8, 17, 21 e 25 do apt em `/usr/lib/jvm`; os JDKs do SDKMAN que o analyzer usa estão vazios (alerta 20). Plano: Docker (`miner-backend/Dockerfile`).
- Docker Desktop instalado (`docker.exe` do Windows); `docker` não existe dentro do WSL.

## Integrações
- Ver `LoboTemporal/referencias.md` (GitHub REST API, Maven, SDKMAN/JDKs, Docker).
