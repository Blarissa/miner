# Procedimentos de código

## Ciclo de cada alteração
1. Trazer a versão atual dos arquivos (o usuário edita na IDE também).
2. Ler o método vizinho e seguir o mesmo padrão (onde fica o SQL, como loga, como monta tela/rota).
3. Editar com script lendo o arquivo real; manter codificação (BOM/CRLF) do original.
4. Compilar/testar pela Medula (`compilar-projeto` / `testar-projeto`), ler os erros (arquivo e linha) e corrigir **antes** de entregar.
5. Tela: `print-janela` → abrir o PNG e conferir o layout.
6. Dizer o que foi conferido de verdade e o que não foi.

## Arquivos
- Classe/arquivo novo: registrar no projeto se a stack exigir (ex.: `<Compile Include=... />` no `.vbproj`).
- Configuração com segredo (`.config`, `.env`, `appsettings`) nunca vai para o Cérebro nem para commit público.

## Testes
- Lógica nova: simular casos normal, borda e inválido antes do teste real.
- Teste contra banco/API de produção ou que envia algo = MOVIMENTO: avisar e esperar o "pode".

## Git
- Perguntar antes de qualquer comando que grava; commit e push só quando pedirem, separados.
- Antes do commit: `projeto-git-status`, mostrar o que entra e a mensagem (`mensagem_commit.txt`).
- Pull/troca de branch bloqueados por alteração local: avisar e deixar o usuário decidir (stash, commit ou descartar).

## Do projeto
- Como compilar/rodar (backend): `cd miner-backend`, ativar `.venv`, `pip install -r requirements.txt`, `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Conferir em `/health` e `/docs`. Checagem de sintaxe: `.\.venv\Scripts\python.exe -m compileall app`.
- Como rodar (front): `cd miner-front`, `npm install`, `npm run dev` (porta 5173). `VITE_API_URL` no `.env` do front aponta para o backend. Checagem: `npm run build` (`tsc -b && vite build`) e `npm run lint`.
- Como testar: `miner-backend/tests/test_pipeline_controls.py` (unittest; cobre filtros, estatísticas, cache, JDK, retomada, cancelamento). Não há testes no front. Os testes não devem chamar a API real do GitHub.
- Docker: `docker build -t miner-backend .` e `docker run --rm --env-file .env.docker -p 8000:10000 -v ${PWD}\data:/app/data miner-backend`.
- Onde publica: não há publicação; uso local/Docker. Não há CI (`.github/` vazio).
- Subir pelo Córtex: ações da Medula `backend-dev` / `front-dev` e as de parar (`backend-dev-parar`, `front-dev-parar`); pedido em `medula\fila\<id>.json`, resultado em `medula\resultados`. O backend roda no WSL (alerta 24). Log do backend: `medula\logs\backend-dev.log`.
- Evidência de uma run: log do backend (motivos de rejeição) e o banco do WSL (`analysis_results.error_message`); eliminados só ficam no banco com "salvar eliminados" ligado.
- Chamar a API de teste: página `http://localhost:8000/docs` (o front não alcança o backend no navegador do app, alerta 27). O token é colado pela Larissa, nunca por mim.
- Padrão do código: backend em `snake_case` com `from __future__ import annotations`, funções pequenas de conversão de payload (`payload_bool` aparece repetida em vários arquivos); mensagens de erro da API em português sem acento.
