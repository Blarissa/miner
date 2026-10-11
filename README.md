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
- Suporte a JDKs 6 a 26 prontos na imagem Docker (o JDK é escolhido pela versão declarada no projeto).
- Execuções assíncronas identificadas por Run ID.
- Cancelamento e retomada de execuções.
- Persistência em SQLite.
- Estatísticas por execução, incluindo funil de análise, versões Java, testes, tempos e estágios de eliminação.
- Interface web para iniciar buscas, acompanhar progresso e consultar resultados antigos.
- Página de estatísticas com gráficos (funil, resultado por versão do Java, bibliotecas de teste).

## Início Rápido (Docker, sem clonar o projeto)

Requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e **aberto**. Não é preciso instalar Java, Maven, Python nem Node.

**Windows**

1. Baixe o [`iniciar.bat`](https://raw.githubusercontent.com/Blarissa/miner/main/iniciar.bat) (botão direito, "Salvar link como"; confira se o arquivo ficou com o nome `iniciar.bat`, e não `.txt`).
2. Dê dois cliques nele.
3. Na primeira vez ele baixa a imagem do Miner (alguns GB, leva alguns minutos). Depois o navegador abre em <http://localhost:8000>.
4. Quando terminar de usar, volte à janela preta e pressione qualquer tecla para encerrar o Miner.

**Linux / macOS**

```bash
curl -O https://raw.githubusercontent.com/Blarissa/miner/main/iniciar.sh
chmod +x iniciar.sh
./iniciar.sh
```

Para encerrar: `./parar.sh` (baixe também o [`parar.sh`](https://raw.githubusercontent.com/Blarissa/miner/main/parar.sh)) ou `docker stop miner-backend-run`.

Detalhes:

- Os resultados ficam guardados no volume Docker `miner-data` e continuam depois de encerrar.
- A imagem fica publicada no Docker Hub: [`blarissa/miner`](https://hub.docker.com/r/blarissa/miner). Você não precisa de conta nem de login para baixá-la. Cada vez que o script abre, ele verifica se há versão nova.
- Se você clonou o repositório e estiver sem internet, o script constrói a imagem a partir dos arquivos locais (leva uns 20 minutos).
- Se fechar a janela sem apertar uma tecla, o Miner continua rodando; use o `parar.bat`.
- Você precisa de um token do GitHub (campo no formulário) para buscas por código.
- A API tem documentação em <http://localhost:8000/api/docs> e a documentação do projeto em <http://localhost:8000/docs>.

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
  .github/workflows/     # publica a imagem Docker
  iniciar.bat / iniciar.sh   # sobe o Miner com um clique
  parar.bat / parar.sh       # encerra o Miner
  README.md
```

## Tecnologias

Backend:

- Python 3.13, FastAPI, Uvicorn e SQLite.
- Git, Maven 3.9 e JDKs 6 a 26 (na imagem Docker: eclipse-temurin e azul/zulu em `/opt/jdks`).

Frontend:

- React, TypeScript, Vite, Tailwind CSS e Lucide React.

Na imagem Docker o front já vem compilado e é servido pelo próprio backend, na mesma porta (8000). Por isso o Docker não precisa de configuração.

Observação: o Maven 3.9 exige Java 8 ou superior, então repositórios que declaram Java 6 ou 7 só são analisados com a opção de permitir atualização do JDK.

## Executando Sem Docker (desenvolvimento)

Requisitos: Python 3.13, Node.js e npm, Git, Maven e um ou mais JDKs.

O analisador descobre os JDKs sozinho: usa `JDK_BASE_DIR` (se definido), `/opt/jdks`, o SDKMAN ou os JDKs da máquina. Nenhum caminho pessoal é necessário.

O banco SQLite é criado automaticamente em `~/.miner/minerador.db`. Para usar outro arquivo, defina `DATABASE_URL` no `miner-backend/.env`, por exemplo:

```env
DATABASE_URL="sqlite:///C:/sqlite/minerador.db"
```

### Backend

```powershell
cd miner-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- API: <http://127.0.0.1:8000>
- Swagger: <http://127.0.0.1:8000/api/docs>
- Health check: <http://127.0.0.1:8000/health>

### Frontend (modo desenvolvimento)

```powershell
cd miner-front
npm install
npm run dev
```

Confira o `miner-front/.env`:

```env
VITE_API_URL=http://localhost:8000
```

Acesse <http://localhost:5173>. Para o backend aceitar essa origem, deixe `CORS_ORIGINS=["http://localhost:5173"]` no `miner-backend/.env`.

## Construindo A Imagem Docker Manualmente

Execute na **raiz** do projeto (o contexto inclui o front):

```powershell
docker build -f miner-backend/Dockerfile -t miner-backend .
docker run -d --rm --name miner-backend-run -p 8000:10000 -v miner-data:/app/data miner-backend
```

Para publicar a imagem no Docker Hub (mantenedora):

```powershell
docker login
docker build -f miner-backend/Dockerfile -t blarissa/miner:latest .
docker push blarissa/miner:latest
```

O primeiro build leva cerca de 20 minutos por causa dos 21 JDKs. Abra <http://localhost:8000>.

## Fluxo De Uso

1. Suba o Miner (`iniciar.bat`) e abra <http://localhost:8000>.
2. Clique em `Nova busca`.
3. Informe uma ou mais queries do GitHub.
4. Informe o token do GitHub no formulário quando a busca exigir autenticação.
5. Configure filtros e opções de análise.
6. Inicie a mineração.
7. Acompanhe o progresso, os resultados parciais e as estatísticas.
8. Use o Run ID para carregar a execução novamente depois.

## Documentação Específica

Cada módulo possui um README próprio com detalhes de configuração e execução:

- Backend: [`miner-backend/README.md`](miner-backend/README.md)
- Frontend: [`miner-front/README.md`](miner-front/README.md)

## Validação Rápida

Backend (testes):

```powershell
cd miner-backend
python -m unittest
```

Frontend:

```powershell
cd miner-front
npm run build
npm run lint
```
