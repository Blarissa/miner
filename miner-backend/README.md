# Miner Backend

API em FastAPI para minerar repositórios Java no GitHub, filtrar projetos Maven/Spring, executar análise de compilação e testes, calcular estatísticas e persistir os resultados em SQLite.

## O Que O Backend Faz

- Busca repositórios pela GitHub REST API usando filtros de código ou de repositório.
- Lê arquivos como `pom.xml` para identificar versão Java, Maven, Spring e bibliotecas de teste.
- Clona projetos Java e, quando solicitado, executa `mvn compile` e `mvn test`.
- Resolve JDKs diferentes para análise, com opção de upgrade automático de versão.
- Mantém execuções assíncronas identificadas por `run_id`.
- Persiste execuções, filtros, candidatos, repositórios aceitos, eliminados, análises, cache e estatísticas em SQLite.
- Expõe documentação interativa em `/docs`.

## Estrutura Principal

```text
app/
  api/routes/
    health.py
    repositories.py
  core/
    config.py
    database.py
    database.sql
  schemas/
    repositories.py
  services/
    analyzer.py
    filters.py
    miner.py
    persistence.py
    persistence_policy.py
    statistics.py
Dockerfile
requirements.txt
```

## Requisitos Para Rodar Localmente

- Python 3.13.
- Git instalado e disponível no `PATH`.
- Maven instalado e disponível no `PATH`, ou wrapper `mvnw` nos repositórios analisados.
- JDK instalado para análise local. O Dockerfile já instala várias versões via SDKMAN.
- Token do GitHub. A busca de código do GitHub exige autenticação.

## Configuração Do `.env`

Crie ou edite o arquivo `.env` na raiz do `miner-backend`.
Exemplo para Windows, usando uma pasta fixa:

```env
CORS_ORIGINS=["http://localhost:5173"]
DATABASE_URL="jdbc:sqlite:C:\sqlite\minerador.db"
```

Variáveis principais:

- `CORS_ORIGINS`: origens permitidas para o front. Em desenvolvimento, mantenha `http://localhost:5173`.
- `DATABASE_URL`: caminho do SQLite. Aceita `jdbc:sqlite:C:\caminho\banco.db` ou `sqlite:///C:/caminho/banco.db`.

O schema é inicializado automaticamente a partir de `app/core/database.sql` quando a API sobe. Se o banco já existir, o backend também aplica migrações simples para colunas novas.

## Banco De Dados No Windows

No Windows, deixe explícito onde o arquivo SQLite vai ficar. Se usar o banco na raiz do projeto, rode este comando no PowerShell dentro de `miner-backend`:

```powershell
New-Item -ItemType File -Path .\minerador.db -Force
```

Se preferir usar `C:\sqlite\minerador.db`, crie a pasta e o arquivo assim:

```powershell
New-Item -ItemType Directory -Path C:\sqlite -Force
New-Item -ItemType File -Path C:\sqlite\minerador.db -Force
```

Depois ajuste o `.env` para apontar para o mesmo caminho:

```env
DATABASE_URL="jdbc:sqlite:C:\sqlite\minerador.db"
```

Observações importantes:

- O SQLite não precisa de servidor separado.
- O arquivo pode ser criado manualmente com os comandos acima, mas as tabelas são criadas pelo backend ao iniciar.
- Não use o mesmo arquivo de banco simultaneamente em dois processos diferentes se estiver fazendo mineração pesada.
- Ao rodar no WSL, caminhos Windows em `DATABASE_URL` são convertidos automaticamente para `~/.miner-backend/` para evitar problemas de I/O do SQLite em `/mnt/c`.

## Execução Local No Windows

Entre na pasta do backend:

```powershell
cd C:\Users\SEU_USUARIO\Desktop\projeto\miner-backend
```

Crie e ative o ambiente virtual, se ainda não existir:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Garanta que o banco informado no `.env` existe:

```powershell
New-Item -ItemType File -Path .\minerador.db -Force
```

Suba a API:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Acesse:

- Swagger/FastAPI: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

## Execução Com Docker

O projeto possui `Dockerfile`. Ele usa `python:3.13-slim`, instala Git, Maven e várias versões de Java via SDKMAN, e expõe a API na porta interna `10000`.

Crie um arquivo separado para Docker, por exemplo `.env.docker`, porque o caminho do banco dentro do container é Linux:

```env
CORS_ORIGINS=["http://localhost:5173"]
DATABASE_URL=sqlite:////app/data/minerador.db
```

Monte uma pasta local para persistir o banco fora do container:

```powershell
New-Item -ItemType Directory -Path .\data -Force
```

Construa a imagem:

```powershell
docker build -t miner-backend .
```

Execute o container mapeando a porta local `8000` para a porta interna `10000`:

```powershell
docker run --rm --env-file .env.docker -p 8000:10000 -v ${PWD}\data:/app/data miner-backend
```

Depois acesse:

- API: <http://127.0.0.1:8000>
- Swagger/FastAPI: <http://127.0.0.1:8000/docs>

Se o front estiver rodando em outro endereço, atualize `CORS_ORIGINS` no `.env.docker`.

## Fluxo Assíncrono

O endpoint `POST /repositories/search` cria uma execução e retorna imediatamente um `run_id`.

### 1. Criar Uma Mineração

```http
POST /repositories/search
```

Exemplo de payload:

```json
{
  "max_repos": 5,
  "max_workers": 3,
  "analyzer_workers": 2,
  "delay": 0,
  "analyze": false,
  "require_buildable": false,
  "require_tests_passed": false,
  "persist_eliminated_repositories": false,
  "include_statistics": true,
  "statistics_scope": "accepted",
  "filters": [
    {
      "name": "java-maven-junit",
      "search_type": "code",
      "query": "junit",
      "filename": "pom.xml",
      "extension": "xml",
      "language": "XML",
      "file_path": "pom.xml",
      "content_rules": [
        {
          "field_name": "build",
          "patterns": ["<artifactId>maven-compiler-plugin</artifactId>|<project"],
          "required": false,
          "fixed_value": "Maven"
        },
        {
          "field_name": "test_framework",
          "patterns": ["junit"],
          "required": false,
          "fixed_value": "JUnit"
        },
        {
          "field_name": "java_version",
          "patterns": [
            "<java\\.version>\\s*([^<]+)\\s*</java\\.version>",
            "<maven\\.compiler\\.source>\\s*([^<]+)\\s*</maven\\.compiler\\.source>"
          ],
          "required": false
        }
      ]
    }
  ]
}
```

Resposta:

```json
{
  "run_id": 1,
  "status": "queued",
  "status_url": "/repositories/runs/1",
  "repositories_url": "/repositories/runs/1/repositories",
  "statistics_url": "/repositories/runs/1/statistics"
}
```

### 2. Consultar Status

```http
GET /repositories/runs/{run_id}
```

Status esperados:

- `queued`: execução criada e aguardando início.
- `running`: job em execução.
- `completed`: job finalizado com sucesso.
- `failed`: job falhou.
- `cancelled`: job cancelado.

Estágios comuns:

- `queued`
- `mining`
- `mined`
- `analyzing`
- `building_statistics`
- `persisting`
- `completed`
- `failed`

### 3. Consultar Repositórios Do Run

```http
GET /repositories/runs/{run_id}/repositories
```

### 4. Consultar Estatísticas Do Run

```http
GET /repositories/runs/{run_id}/statistics
```

### 5. Cancelar Ou Retomar Uma Execução

```http
POST /repositories/runs/{run_id}/cancel
POST /repositories/runs/{run_id}/resume
```

## Análise Maven

Quando `analyze`, `require_buildable` ou `require_tests_passed` está ativo, o backend chama o analyzer.

O analyzer:

- clona ou atualiza o repositório;
- confirma o commit analisado com `git rev-parse HEAD`;
- localiza o `pom.xml` na raiz;
- tenta resolver o JDK da versão Java selecionada ou detectada;
- executa `mvn compile -B -q -DskipTests`;
- se solicitado, detecta testes pela presença de arquivos `.java` em `src/test/java` e executa `mvn test -B`;
- marca o repositório como eliminado quando falha em clone, estrutura, JDK, compilação, ausência de testes ou testes.

Os clones ficam em:

```text
app/services/repos/
```

Os logs ficam em:

```text
app/services/logs/
```

## Seleção De JDK

O upgrade automático de JDK é controlado por `allow_jdk_upgrade`.

O analyzer registra duas versões:

- `java_version`: versão declarada ou detectada no repositório.
- `effective_java_version`: versão do JDK realmente usada na compilação/teste.

Quando `allow_jdk_upgrade` está desativado, `effective_java_version` deve ser igual a `java_version`. Se o JDK correspondente não estiver disponível, ou se o `pom.xml` exigir uma versão maior que a selecionada, o repositório é eliminado em `jdk_resolution`.

Quando `allow_jdk_upgrade` está ativado, o analyzer pode usar o menor JDK superior disponível para conseguir iniciar o Maven, atender ao `pom.xml` ou reagir a uma falha que indique versão Java insuficiente.

## Critérios Spring E Testes

Durante a mineração, um candidato só é aceito quando:

- o `pom.xml` indica uso de Spring, por exemplo por `org.springframework` ou artefatos `spring-*`;
- pelo menos um arquivo `.java` em `src/main/java` contém import de `org.springframework`.

Dependências de teste declaradas no `pom.xml` não bastam para reconhecer testes. Para a análise com testes, é necessário existir pelo menos um arquivo `.java` dentro de `src/test/java`.

## Cache De Análise

O backend usa `analysis_cache` para evitar reanalisar o mesmo repositório no mesmo commit.

A chave do cache é:

```text
repository_id + commit_sha + run_test_suite
```

Durante a mineração, o backend busca o SHA da branch padrão. Durante a análise, o analyzer confirma o `HEAD` real clonado. Se houver cache para o commit e modo de teste solicitados, o resultado é reaproveitado com `cache_hit: true`.

## Validação Local

Para checar sintaxe/importação:

```powershell
.\.venv\Scripts\python.exe -m compileall app
```

Para listar as rotas expostas no OpenAPI:

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print('\n'.join(sorted(app.openapi()['paths'].keys())))"
```
