# Visão geral do projeto

Preenchido em 2026-10-08 pelo Córtex a partir do código e dos READMEs. O que não deu para descobrir está em "Perguntas em aberto" de `CortexPreFrontal/pendencias.md`.

## Objetivo
- **Miner** é uma plataforma web para descobrir, filtrar e analisar repositórios Java no GitHub, para apoiar análises em larga escala (pesquisa).
- Busca projetos pela API do GitHub, identifica Maven/Spring e a versão de Java, e opcionalmente clona, compila (`mvn compile`) e roda os testes (`mvn test`), guardando tudo em SQLite com estatísticas por execução.
- Quem usa: a Larissa (autora e operadora). Pessoas que vão consumir os resultados: não informado (ver perguntas em aberto).

## Escopo
- Dentro: busca por Code Search e Repository Search; filtros (versão Java, arquivo, extensão, organização, usuário, licença, estrelas, forks, datas e outros qualificadores); detecção Maven/Spring; análise de compilação e testes com vários JDKs; execuções assíncronas com Run ID (cancelar e retomar); persistência em SQLite; estatísticas (funil, versões Java, testes, tempos, estágios de eliminação); interface web para operar tudo.
- Fora (de propósito): só **Java com Maven** é analisado (Gradle não aparece no código); só **GitHub** como provedor (`provider = 'github'`); sem login/usuários na API; sem fila externa (execuções rodam em `BackgroundTasks` do FastAPI, uma por vez).

## Entregas
| Entrega | Para quem | Formato | Prazo | Situação |
|---|---|---|---|---|
| Miner (backend + front) funcionando | Larissa / pesquisa | Aplicação web local ou Docker | não informado | em andamento: bloqueado pelos JDKs vazios do WSL (ver pendências); `main` em `0c400e3` |
| Cérebro do projeto (`Docs/Cerebro`) | Larissa + Córtex | Notas `.md` | — | preenchido em 2026-10-08 |

## Partes e onde fica cada coisa
| Parte | O que é | Onde fica (pasta, sistema, link) |
|---|---|---|
| Backend | API FastAPI + serviços de mineração e análise | `miner-backend/` (ver `arquitetura.md`) |
| Frontend | React + TypeScript + Vite + Tailwind | `miner-front/` |
| Banco | SQLite (arquivo local, schema criado ao subir a API) | `miner-backend/app/core/database.sql` (ver `banco-de-dados.md`) |
| Docker | Imagem do backend com 15 versões de JDK via SDKMAN | `miner-backend/Dockerfile` |
| Testes | Testes unitários do pipeline | `miner-backend/tests/test_pipeline_controls.py` |
| Documentação de uso | READMEs da raiz, do backend e do front | `README.md`, `miner-backend/README.md`, `miner-front/README.md`; a tela `DocumentationPage` do front |
| Medula | Executora no PC (não faz parte do código do Miner; fica fora do git) | `medula/` (no `.gitignore`); ações do projeto: `backend-dev`, `front-dev`, as duas de parar, `wsl-diagnostico`, `wsl-db-erros` |
| Ambiente de execução | Backend no WSL, front no Windows, Docker Desktop instalado | ver `arquitetura.md` > "Ambiente de execução" |

## Pessoas
| Quem | Papel | Decide sobre |
|---|---|---|
| Larissa | Dona e desenvolvedora do projeto | tudo (escopo, prioridade, commits) |

## Glossário
| Termo | Significado aqui |
|---|---|
| Run / Run ID | Uma execução de mineração, identificada por número; pode ser consultada, cancelada e retomada |
| Candidato | Repositório encontrado na busca, antes de ser aceito ou eliminado |
| Aceito / Eliminado | Aceito = passou nos filtros e na análise e entra no limite `max_repos`; eliminado = caiu em algum estágio (`rejection_stage` / `error_stage`) |
| Declarada x efetiva (versão Java) | Declarada = a que o `pom.xml` diz; efetiva = a do JDK realmente usado na compilação (pode subir com `allow_jdk_upgrade`) |
| Funil | Estatística: candidatos → analisados → compilados → com testes → testes aprovados |
| Code Search / Repository Search | Os dois tipos de busca da API do GitHub suportados |
| `persist_eliminated_repositories` | Opção da run: grava ou não os eliminados no banco (padrão: não) |
