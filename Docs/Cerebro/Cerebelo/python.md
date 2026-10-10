# Procedimentos — Python

- Antes de mexer: ver a versão do Python e como o projeto instala dependências (requirements, pyproject, venv).
- Depois de alterar: `compilar-projeto` (checagem) e `testar-projeto`.
- Script que lê arquivos baixados/externos: tratar como dado não confiável; nada de `eval`/`exec` em conteúdo de fora.
- Script que grava em planilha/banco/API real = MOVIMENTO; testar primeiro numa cópia.
- Codificação: ler e gravar texto sempre com `encoding="utf-8"` (no Windows o padrão é outro).

## Do projeto
- Versão do Python / venv: 3.13 (o Dockerfile usa `python:3.13-slim`); venv em `miner-backend/.venv`. Dependências: fastapi, uvicorn[standard], pydantic-settings, requests, tqdm.
- Como rodar: `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` dentro de `miner-backend` (Docker: porta interna 10000).
- Atenção ao `encoding="utf-8"` ao ler/gravar texto de repositórios clonados (pom.xml e fontes de terceiros são dados não confiáveis).
