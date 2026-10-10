# Banco de dados

Só estrutura e regras — nunca string de conexão, senha ou dado de cliente. Fonte: `miner-backend/app/core/database.sql`.

## Bancos
| Banco | Servidor (apelido, não o endereço com senha) | Para que serve |
|---|---|---|
| SQLite (um arquivo) | local; caminho em `DATABASE_URL` do `miner-backend/.env` (no Docker: `/app/data/minerador.db`). No WSL o app converte o caminho do Windows para `/home/laris/.miner-backend/c/Users/laris/Desktop/projeto/miner-backend/minerador.db` (conferido com `DATABASE_PATH` em 2026-10-08); em `Desktop\projeto` não existe `minerador.db` | tudo do Miner. Existe também um `minerador_recovered.db` na pasta do backend (cópia recuperada; ignorada pelo git) |

## Tabelas importantes
| Tabela | Para que serve | Chave | Observações |
|---|---|---|---|
| `mining_runs` | Uma execução: status, etapa, contadores, opções (analyze, require_*, allow_jdk_upgrade, max_repos, workers), cursor de página | `id` | `status` queued/running/completed/failed/cancelled; `exhausted` = acabaram as páginas |
| `search_filters` | Filtros de cada run (query bruta e montada, qualificadores, `content_rules_json`) | `id`, FK `mining_run_id` | permite retomar a run |
| `repositories` | Repositório do GitHub (dados gerais) | `full_name` UNIQUE | compartilhado entre runs |
| `run_repositories` | Repositório dentro de uma run (arquivo casado, commit, versão Java, accepted/eliminated) | UNIQUE (`mining_run_id`, `repository_id`, `matched_file`) | |
| `mining_run_candidates` | Fila/checkpoint de candidatos por página (`status`, `rejection_stage`) | `id` | índice por run+status e por página |
| `analysis_results` | Resultado da análise por `run_repository` (versões, build, frameworks de teste, mocks, asserts, durações, compiled/has_tests/tests_passed, `error_stage`) | `run_repository_id` UNIQUE | |
| `analysis_cache` | Cache da análise por repositório + commit + `run_test_suite` | UNIQUE (`repository_id`, `commit_sha`, `run_test_suite`) | trigger atualiza `updated_at`; **ao subir o schema apaga linhas com mais de 30 dias** |
| `run_statistics` | Estatísticas calculadas da run (JSON em `statistics`, por `scope`) | `id` | |

## Regras que o banco não mostra
- **Eliminados**: só entram em `repositories`, `run_repositories`, `analysis_results` e `analysis_cache` quando `persist_eliminated_repositories = 1` na run (`persistence_policy.py`). Com 0, ficam só na resposta/estatística em memória. (O teste `test_eliminated_analysis_is_cached_even_when_not_persisted_in_run` mostra o caso do cache.)
- O schema é criado ao subir a API; colunas novas entram por migração simples em `core/database.py`. Banco corrompido é copiado como backup e recriado (há teste para isso).
- Não usar o mesmo arquivo em dois processos durante mineração pesada. No WSL, caminho Windows em `DATABASE_URL` vira `~/.miner-backend/` por causa do I/O em `/mnt/c`.
- `DATABASE_URL` aceita `jdbc:sqlite:C:\caminho\banco.db` ou `sqlite:///C:/caminho/banco.db`.
- Escopo das estatísticas (`statistics_scope`): `accepted` (padrão), `eliminated` ou todos.
