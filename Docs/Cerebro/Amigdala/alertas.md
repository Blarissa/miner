# Alertas — ler antes de mexer

Armadilhas que já custaram tempo. Uma por item, com o porquê. Os do projeto entram no fim, numerados a partir do próximo número livre.

## Gerais (valem para qualquer projeto)

1. **Segredos** (senha, token, chave, string de conexão, dado pessoal de cliente): nunca copiar para docs, logs, chat ou Cérebro. Aqui só se anota **onde** o segredo está, nunca o valor.
2. **Credencial que o usuário manda no chat**: usar só na chamada; não gravar em arquivo (nem fila/resultado da Medula), não repetir.
3. **O usuário também edita os arquivos.** Antes de editar, trazer a versão atual; depois de gravar, conferir no disco. Programa aberto (editor, IDE, Word, Excel) pode salvar por cima — pedir para recarregar ou fechar sem salvar.
4. **Cópia recém-trazida do PC pode vir atrasada 1–3 s.** Esperar antes de comparar.
5. **Gravar de novo o mesmo arquivo de saída pode mandar a versão anterior.** Cada versão com nome novo (`_v2`, `_v3`) e conferir tamanho/conteúdo depois.
6. **Ação que atinge o mundo real** (mensagem, e-mail, publicação, pagamento, gravação em sistema de produção, envio a cliente): é MOVIMENTO — perguntar antes, testar com destino da equipe, nunca com contato inventado.
7. **Material para cliente/público** não cita regra interna, nome de tabela, custo, nem "como fazemos por dentro"; site estático não guarda segredo.
8. **Mudança com duas pontas** (quem grava × quem lê; a mesma lista em dois lugares; documento e planilha que se citam): mudar as duas juntas e deixar iguais.
9. **Feito ≠ funciona.** Depois de produzir, conferir o resultado real (abrir o arquivo, rodar, ver o print) — ou dizer claramente que não foi conferido.
10. **Fonte de outro cliente/contexto** (acesso, planilha, token de outra operação) não serve para decidir regra deste projeto.

## Do projeto

11. **Token do GitHub** vem do formulário do front (ou do `GITHUB_TOKEN` no `.env`). Nunca colar em Cérebro, log, banco ou chat; o `.env` está no `.gitignore` e deve continuar lá.
12. **Retomar run exige token no `.env`** (ver pendências): quem for mexer em `resume` precisa tratar isso antes de dizer que "retoma".
13. **Só uma run roda por vez** (`GLOBAL_PIPELINE_SEMAPHORE` com valor 1). Uma run longa deixa as outras em `queued`; não é bug.
14. **Cache de análise é por repositório + commit + `run_test_suite`** e sofre limpeza de 30 dias. Mudar a regra de análise sem invalidar o cache devolve resultado antigo.
15. **Eliminados não vão para o banco por padrão** (`persist_eliminated_repositories = 0`). Estatística de "eliminados" depende dessa opção ligada ou da resposta em memória.
16. **Compilar e testar repositórios de terceiros executa código deles** (`mvn test`). Rodar em Docker/ambiente isolado, não na máquina com dados pessoais; clones ficam em `app/services/repos/` (ignorado pelo git).
17. **JDK ausente** (caminho do SDKMAN diferente de `/home/laris/.sdkman/...`) faz a análise falhar por versão; ajustar `JDK_BASE_DIR`/`SDKMAN_JAVA_DIR`.
18. **Banco SQLite em `/mnt/c` no WSL** dá erro de I/O; o código redireciona para `~/.miner-backend/`, então "o banco sumiu" pode ser só outro caminho.
19. **Versões de Python misturadas**: há `.pyc` de 3.10, 3.13 e 3.14 na árvore, mas o projeto é 3.13. Usar a `.venv` do projeto.
20. **JDKs do SDKMAN no WSL estão vazios** (desde 25/09 11:45): sem `bin/java`, o Maven falha em menos de 1 s com "JAVA_HOME ... not defined correctly". Antes de culpar o código ou os filtros, conferir `ls /home/laris/.sdkman/candidates/java/21.0.2-tem/bin`.
21. **Erro de ambiente vira "teste falhou" e entra no cache por 30 dias** (`error_stage = tests`, `compiled = 1`). Rodar de novo com o mesmo repositório + commit devolve o resultado reprovado sem chamar o Maven. Depois de consertar o ambiente, o cache velho precisa sair ou expirar.
22. **Conferir o branch antes de estudar ou documentar**: o repositório ficou em HEAD solto (`bc4db50`) e a `main` tinha 4 commits a mais. `git status` mostra "HEAD detached".
23. **`git switch`/`checkout` aqui precisa de permissão de apagar**: sem ela, o branch troca mas os arquivos não, e o `git status` mostra tudo modificado. Pedir a permissão antes e conferir o `git status` depois.
24. **O backend roda no WSL**: o banco fica em `/home/laris/.miner-backend/c/Users/laris/Desktop/projeto/miner-backend/minerador.db` (dentro do WSL, não em `Desktop\projeto`). Quem pergunta "cadê o banco" deve procurar lá.
25. **`wsl.exe` herda o `JAVA_HOME` do Windows já estragado** (`C:Program FilesJavajdk-21`). O analyzer sobrescreve, mas qualquer comando solto no WSL que dependa dele falha.
26. **Token do GitHub**: o Córtex não digita credenciais em campos; quem cola é a Larissa. Um token colado no chat deve ser revogado.
27. **No navegador do app, o front (5173) não consegue chamar o backend (8000)** (`ERR_BLOCKED_BY_CLIENT`). Testar pela página `/docs` do backend ou pelo navegador normal.
