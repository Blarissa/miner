# Miner

Miner é uma plataforma web para descobrir, filtrar e analisar repositórios Java no GitHub. O projeto combina uma API em FastAPI com uma interface React para executar minerações, acompanhar o progresso em tempo real, validar projetos Maven/Spring, verificar compilação e testes, e consultar estatísticas das execuções salvas.

## Descrição Do Projeto

O Miner foi criado para apoiar análises de repositórios Java em larga escala. A aplicação permite buscar projetos no GitHub por código ou metadados, aplicar filtros como versão Java, arquivo, extensão, estrelas, organização e licença, e opcionalmente executar uma análise técnica de cada repositório encontrado.

Durante a análise, o backend pode clonar os projetos, identificar a versão Java declarada, compilar com Maven, executar testes, detectar frameworks e bibliotecas de teste, persistir os resultados em SQLite e gerar estatísticas sobre os repositórios aceitos ou eliminados.

## Principais Funcionalidades

- Busca de repositórios usando a API do GitHub.
- Suporte a Code Search e Repository Search.
- Filtros por versão Java, arquivo, extensão, organização, usuário, licença, estrelas, forks, datas e outros qualificadores.
- Detecção de projetos Maven/Spring.
- Análise opcional de compilação e testes.
- Suporte a múltiplas versões de JDK no backend via Docker.
- Execuções assíncronas identificadas por Run ID.
- Cancelamento e retomada de execuções.
- Persistência em SQLite.
- Estatísticas por execução, incluindo funil de análise, versões Java, testes, tempos e estágios de eliminação.
- Interface web para iniciar buscas, acompanhar progresso e consultar resultados antigos.

## Estrutura Do Repositório

```text
miner/
  miner-backend/
    app/
    Dockerfile
    requirements.txt
    README.md
  miner-front/
    src/
    package.json
    README.md
  README.md
```

## Tecnologias

Backend:

- Python 3.13.
- FastAPI.
- Uvicorn.
- SQLite.
- Git, Maven e JDK para análise dos repositórios.
- Docker para execução empacotada com múltiplas versões de Java.

Frontend:

- React.
- TypeScript.
- Vite.
- Tailwind CSS.
- Lucide React.

## Requisitos Gerais

Para executar localmente sem Docker:

- Python 3.13.
- Node.js e npm.
- Git.
- Maven.
- JDK instalado.
- Banco SQLite em arquivo local.

Para executar o backend com Docker:

- Docker instalado.
- Node.js e npm para executar o front localmente.

## Configuração Do Banco No Windows

A opção mais simples é usar uma pasta fixa para o SQLite:

```powershell
New-Item -ItemType Directory -Path C:\sqlite -Force
New-Item -ItemType File -Path C:\sqlite\minerador.db -Force
```

No arquivo `miner-backend/.env`, configure:

```env
CORS_ORIGINS=["http://localhost:5173"]
DATABASE_URL="jdbc:sqlite:C:\sqlite\minerador.db"
```

O SQLite não precisa de servidor separado. O arquivo pode ser criado manualmente, mas as tabelas são criadas automaticamente pelo backend ao iniciar.

## Executando O Backend Localmente

Entre na pasta do backend:

```powershell
cd miner-backend
```

Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Suba a API:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Acesse:

- API: <http://127.0.0.1:8000>
- Swagger: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

## Executando O Backend Com Docker

Entre na pasta do backend:

```powershell
cd miner-backend
```

Crie um arquivo `.env.docker`:

```env
CORS_ORIGINS=["http://localhost:5173"]
DATABASE_URL=sqlite:////app/data/minerador.db
```

Crie a pasta de dados:

```powershell
New-Item -ItemType Directory -Path .\data -Force
```

Construa a imagem:

```powershell
docker build -t miner-backend .
```

Execute o container:

```powershell
docker run --rm --env-file .env.docker -p 8000:10000 -v ${PWD}\data:/app/data miner-backend
```

O backend ficará disponível em:

```text
http://localhost:8000
```

## Executando O Frontend

Em outro terminal, entre na pasta do front:

```powershell
cd miner-front
```

Crie ou confira o arquivo `miner-front/.env`:

```env
VITE_API_URL=http://localhost:8000
```

Instale as dependências:

```powershell
npm install
```

Suba o servidor de desenvolvimento:

```powershell
npm run dev
```

Acesse:

```text
http://localhost:5173
```

## Fluxo De Uso

1. Suba o backend em `http://localhost:8000`.
2. Suba o front em `http://localhost:5173`.
3. Abra a interface no navegador.
4. Clique em `Nova busca`.
5. Informe uma ou mais queries do GitHub.
6. Informe o token do GitHub no formulário quando a busca exigir autenticação.
7. Configure filtros e opções de análise.
8. Inicie a mineração.
9. Acompanhe o progresso, os resultados parciais e as estatísticas.
10. Use o Run ID para carregar a execução novamente depois.

## Documentação Específica

Cada módulo possui um README próprio com detalhes de configuração e execução:

- Backend: [`miner-backend/README.md`](miner-backend/README.md)
- Frontend: [`miner-front/README.md`](miner-front/README.md)

## Build Do Frontend

Para gerar a versão de produção:

```powershell
cd miner-front
npm run build
```

Para testar o build:

```powershell
npm run preview
```

## Validação Rápida

Backend:

```powershell
cd miner-backend
.\.venv\Scripts\python.exe -m compileall app
```

Frontend:

```powershell
cd miner-front
npm run build
```
