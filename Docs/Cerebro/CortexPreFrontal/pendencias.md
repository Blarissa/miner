# Pendências e próximos passos

Atualizado em: 2026-10-10. Marcar `[x]` quando resolver (riscar com `~~ ~~` e dizer como) e anotar no diário do dia.
A Medula lê este arquivo no bom-dia: conta os `- [ ]` e fala o primeiro da seção "Urgente".

## Urgente (bloqueia a entrega)
- Nada urgente. ~~Consertar o ambiente de JDKs~~ — resolvido em 2026-10-10 rodando o backend no Docker (ver diário). Para usar: Medula `docker-up` (backend em 8000) e `docker-down`.

## Próximos passos
- ~~[ ] 2026-10-08 — Refazer os testes no Docker~~ — feito em 2026-10-10 (run 1 B: 2 aceitos; run 2 A: 2 resultados).
- [ ] 2026-10-08 — Larissa: revogar o token do GitHub colado no chat e criar outro (sem escopos especiais).
- [ ] 2026-10-08 — Rodar os testes unitários (`python -m unittest` em `miner-backend`) e anotar o resultado. Não foram executados.
- [ ] 2026-10-08 — Responder as "Perguntas em aberto" abaixo para completar Entregas e Pessoas em `visao-geral.md`.
- [ ] 2026-10-08 — Commit de `Docs/` e do `.gitignore` (só quando a Larissa pedir; agora na `main`).
- ~~[ ] 2026-10-08 — Voltar para a `main`~~ — feito em 2026-10-08 (`main` em `0c400e3`, ver diário).

## Melhorias sugeridas
- [ ] 2026-10-10 — Investigar por que `eliminated_repositories` (28) > `analyzed_repositories` (18) na run 1.
- [ ] 2026-10-10 — Navegador do app bloqueia front→backend; testar o front contra o Docker por outra via (proxy do Vite). (não pedidas ainda)
- [ ] 2026-10-08 — Falha de ambiente (JAVA_HOME ausente, Maven ausente, "Comando não encontrado") não pode eliminar o repositório nem ir para o `analysis_cache`: hoje vira `error_stage = tests`. A Larissa escolheu **não mexer agora**.
- [ ] 2026-10-08 — Limpar do `analysis_cache` as entradas com o erro de JAVA_HOME (apagar linhas do banco é permanente; pedir o "pode"). Sem limpeza, expiram em até 30 dias.
- [ ] 2026-10-08 — Formulário do front: restaurar `file_path`/`filename` = `pom.xml` e `extension` = `xml` (o commit `bc4db50` os esvaziou); comentar as linhas atuais, sem apagar.
- [ ] 2026-10-08 — "Busca simples" (caixas desmarcadas) só lista resultados do GitHub sem checar Maven; antes ainda checava `pom.xml`/versão Java. Decidir: voltar a checar ou deixar claro na tela.
- [ ] 2026-10-08 — Analyzer só aceita `pom.xml` e `src/test/java` na raiz: projetos multi-módulo (ex.: apache/seatunnel) caem em `structure`/`no_tests`, apesar do `candidate_pom_lookup_paths` do miner.
- [ ] 2026-10-08 — `Dockerfile` não instala o JDK 25 que o `JDK_MAP` do analyzer espera; versões do SDKMAN podem ter saído do catálogo. Conferir no build.
- [ ] 2026-10-08 — **Retomar run depende de `GITHUB_TOKEN` no `.env`** (`resume` usa só `settings.github_token`), mas o token passou a vir do formulário; provável 400. Não testado.
- [ ] 2026-10-08 — Caminhos pessoais fixos: `config.py` (padrão do `database_url`), `Dockerfile` e `analyzer.py` (`/home/laris/.sdkman`).
- [ ] 2026-10-08 — Arquivos `__pycache__/*.pyc` estão **versionados no git** apesar do `.gitignore`; rodar o backend os modifica (aparecem 3 `.pyc` de 3.14 no `git status`). Tirar do índice com `git rm --cached` (comando que grava: pedir o "pode"); não commitar junto com o resto sem olhar.
- [ ] 2026-10-08 — `.github/` vazio (sem CI); falta `.env.example`.
- [ ] 2026-10-08 — `analyzer.py` ainda tem modo de linha de comando (`main()`, `INPUT_JSON`) e cria `repos/` e `logs/` ao importar; confirmar se o modo CLI é usado.
- [ ] 2026-10-08 — `miner-front/pasta de arquivos TXT/` vazia; confirmar se pode sair.
- [ ] 2026-10-08 — Cache de análise com mais de 30 dias é apagado ao subir o schema; confirmar se é desejado para pesquisa reprodutível.
- [ ] 2026-10-08 — Se for testar pelo front no navegador do app, resolver o bloqueio entre 5173 e 8000 (por exemplo proxy do Vite); hoje só funcionou chamando o backend pela página `/docs`.

## Perguntas em aberto
- Para que serve o resultado (artigo, TCC, ferramenta)? Qual é o prazo? Quem consome os dados além da Larissa?
- Gradle e outros provedores estão fora do escopo de propósito ou só não foram feitos?
- O que apagou o conteúdo das pastas de JDK do SDKMAN em 25/09 às 11:45? (limpeza de disco, `sdk uninstall`, script?)
