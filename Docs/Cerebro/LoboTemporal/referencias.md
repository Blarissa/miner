# Referências

Onde está cada coisa que vem de fora: sistemas, APIs, documentos e pessoas. **Nunca o valor de senha ou token — só onde ele está guardado.**

## Sistemas e APIs
| Nome | Para que usamos | Documentação / link | Acesso (onde está a credencial) |
|---|---|---|---|
| GitHub REST API (versão `2026-03-10` no config) | Code Search, Repository Search, metadados, conteúdo de arquivos, commit do branch padrão | https://docs.github.com/rest | Token pessoal informado no formulário do front (campo `github_token`) ou `GITHUB_TOKEN` no `.env` do backend. **Code Search exige autenticação** |
| Maven | `mvn compile` / `mvn test` nos repositórios clonados (usa `mvnw` do projeto se houver) | https://maven.apache.org | instalado no PC/Docker, sem credencial |
| JDKs via SDKMAN | 6, 7, 8, 11, 14–23 (e 25 mapeado) escolhidos pela versão declarada | https://sdkman.io | sem credencial; caminho base em `JDK_BASE_DIR` / `SDKMAN_JAVA_DIR` |
| Docker | Empacota o backend com todos os JDKs | `miner-backend/Dockerfile` | sem credencial |
| SQLite | Banco local | https://sqlite.org | arquivo local, sem senha |

## Documentos e fontes
| Documento / fonte | O que tem | Onde está | Confiável até |
|---|---|---|---|
| `README.md` (raiz) | Visão, instalação Windows/Docker, fluxo de uso | raiz do projeto | commit `0c400e3` (`main`) |
| `miner-backend/README.md` | Variáveis, banco, execução local e Docker | `miner-backend/` | idem |
| `miner-front/README.md` | Funções da interface, `.env`, CORS | `miner-front/` | idem |
| Tela de documentação | Texto de ajuda dentro do front | `miner-front/src/components/DocumentationPage.tsx` | idem |

## Pessoas e contatos
| Quem | Papel no projeto | Assuntos com ela | Canal |
|---|---|---|---|
| Larissa | Dona do projeto | tudo | chat |

## Detalhes
### GitHub API
- Há limite de requisições: `miner.py` tem `TokenRateLimiter`, cache de resposta e backoff (`handle_rate_limit`, `sleep_with_backoff`). Rodar muitas buscas seguidas com o mesmo token pode travar a run por espera.
- Code Search devolve o arquivo casado (`matched_file`); a Repository Search não, então o código lê o `pom.xml` da raiz.
