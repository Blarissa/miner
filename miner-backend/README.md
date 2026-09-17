# Miner Backend

API em FastAPI para minerar repositórios Java no GitHub, aplicar filtros sobre arquivos do projeto, analisar compilação/testes Maven e persistir os resultados em SQLite.

## Funcionalidades

- Busca repositórios usando a GitHub REST API.
- Suporta filtros por repositório ou por código.
- Aplica regras de conteúdo com regex em arquivos como `pom.xml`.
- Extrai automaticamente a versão Java de `pom.xml`.
- Confirma uso de Spring no `pom.xml` e em imports de `src/main/java`.
- Clona projetos Java e executa análise Maven.
- Detecta versão Java, compilação, presença de testes e resultado dos testes.
- Persiste execuções, filtros, repositórios, análises, estatísticas e cache em SQLite.
- Executa mineração como job assíncrono com `run_id`.
- Expõe documentação interativa com Scalar em `/scalar`.

## Estrutura

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
```

## Requisitos

- Python 3.13 ou compatível com a `.venv` do projeto.
- Git instalado e disponível no `PATH`.
- Maven instalado e disponível no `PATH`, ou wrapper `mvnw` nos repositórios analisados.
- JDK instalado. Por padrão, o analyzer usa o JDK da versão Java selecionada/detectada; o upgrade automático pode ser habilitado pelo usuário.
- Token do GitHub para usar a API sem limite muito baixo.

## Configuração

Crie ou edite o arquivo `.env` na raiz do `miner-backend`:

```env
GITHUB_TOKEN=seu_token_github
DATABASE_URL=jdbc:sqlite:C:\sqlite\sqlite.db
```

Variáveis principais:

- `GITHUB_TOKEN`: token usado quando o payload não envia `github_token`.
- `DATABASE_URL`: caminho do SQLite. Aceita `jdbc:sqlite:C:\sqlite\sqlite.db` ou `sqlite:///C:/sqlite/sqlite.db`.

Ao executar o backend no WSL, um caminho Windows configurado no `DATABASE_URL` e
convertido automaticamente para o filesystem nativo do WSL em
`~/.miner-backend/`. Isso evita erros de I/O do SQLite ao usar WAL em `/mnt/c`.

Valores padrão ficam em [app/core/config.py](app/core/config.py).

## Como Rodar

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Depois acesse:

- Scalar: <http://127.0.0.1:8000/scalar>
- Swagger/FastAPI: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>

## Fluxo Assíncrono

O endpoint `POST /repositories/search` cria uma execução e retorna imediatamente um `run_id`.

### 1. Criar uma mineração

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

### 2. Consultar status

```http
GET /repositories/runs/{run_id}
```

Exemplo de resposta:

```json
{
  "id": 1,
  "status": "running",
  "progress_stage": "mining",
  "total_candidates": 0,
  "processed_repositories": 0,
  "accepted_repositories": 0,
  "eliminated_repositories": 0,
  "statistics_scope": "accepted",
  "include_statistics": 1,
  "require_buildable": 0,
  "require_tests_passed": 0,
  "persist_eliminated_repositories": 0,
  "max_repos": 5,
  "max_workers": 3,
  "analyzer_workers": 2,
  "delay_seconds": 0.0,
  "started_at": "2026-09-01 12:00:00",
  "finished_at": null,
  "error_message": null
}
```

Status esperados:

- `queued`: execução criada e aguardando início.
- `running`: job em execução.
- `completed`: job finalizado com sucesso.
- `failed`: job falhou.

Estágios esperados:

- `queued`
- `mining`
- `mined`
- `analyzing`
- `building_statistics`
- `persisting`
- `completed`
- `failed`

### 3. Consultar repositórios do run

```http
GET /repositories/runs/{run_id}/repositories
```

Retorna os repositórios já persistidos para a execução.

### 4. Consultar estatísticas do run

```http
GET /repositories/runs/{run_id}/statistics
```

Retorna as estatísticas persistidas, quando existirem.

## Filtrar Repositórios em Memória

```http
POST /repositories/filter
```

Exemplo:

```json
{
  "repositories": [
    {
      "repo_name": "owner/project",
      "repo_url": "https://github.com/owner/project",
      "metadata": {
        "java_version": "17"
      },
      "has_tests": true,
      "tests_passed": true,
      "eliminated": false
    }
  ],
  "filters": {
    "java_versions": ["17"],
    "repo_name": "project",
    "has_tests": true,
    "tests_passed": true,
    "eliminated": false
  }
}
```

## Análise Maven

Quando `analyze`, `require_buildable` ou `require_tests_passed` está ativo, o backend chama o analyzer.

O analyzer:

- clona ou atualiza o repositório;
- confirma o commit analisado com `git rev-parse HEAD`;
- localiza o `pom.xml` na raiz;
- tenta resolver o JDK da versão Java selecionada/detectada;
- executa `mvn compile -B -q -DskipTests`;
- se solicitado, detecta testes apenas pela presença de arquivos `.java` em `src/test/java` e executa `mvn test -B`;
- marca o repositório como eliminado quando falha em clone, estrutura, JDK, compilação, ausência de testes ou testes.

### Seleção de JDK durante a análise

O upgrade automático de JDK é uma opção da análise, controlada por `allow_jdk_upgrade`.

O analyzer registra duas versões:

- `java_version`: versão declarada ou detectada no repositório.
- `effective_java_version`: versão do JDK realmente usada na compilação/teste.

Quando `allow_jdk_upgrade` está desativado, `effective_java_version` deve ser igual a `java_version`. Se o JDK correspondente não estiver disponível, ou se o `pom.xml` exigir uma versão maior que a selecionada, o repositório é eliminado na etapa `jdk_resolution`.

Quando `allow_jdk_upgrade` está ativado, o analyzer pode usar o menor JDK superior disponível para conseguir iniciar o Maven, atender ao `pom.xml` ou reagir a uma falha que indique versão Java insuficiente. Nesse caso, o repositório pode ser considerado válido se compilar e, quando solicitado, passar nos testes com o JDK efetivo. A saída mantém as duas versões para deixar claro que a validade depende do ambiente adaptado.

## Critérios Spring

Durante a mineração, um candidato só é aceito quando:

- o `pom.xml` indica uso de Spring, por exemplo por `org.springframework` ou artefatos `spring-*`;
- pelo menos um arquivo `.java` em `src/main/java` contém import de `org.springframework`.

Dependências de teste declaradas no `pom.xml` não são usadas para reconhecer testes. Para a análise com testes, é necessário existir pelo menos um arquivo `.java` dentro de `src/test/java`.

A saída persistida inclui metadados úteis para auditoria e filtros futuros, incluindo branch padrão, commit SHA, licença, estrelas e data do último push.

Os clones ficam em:

```text
app/services/repos/
```

Os logs ficam em:

```text
app/services/logs/
```

## Detecção de Versão Java

Quando o miner baixa um arquivo `pom.xml`, ele tenta preencher `metadata.java_version` automaticamente antes de chamar o analyzer.

Campos procurados:

- `maven.compiler.release`
- `maven.compiler.source`
- `maven.compiler.target`
- `java.version`
- `jdk.version`
- `release`
- `source`
- `target`

Versões no formato antigo são normalizadas:

```text
1.8 -> 8
1.7 -> 7
```

Se uma `content_rule` também extrair `java_version`, o valor da regra explícita tem prioridade sobre a detecção automática.

## Cache de Análise

O backend usa `analysis_cache` para evitar reanalisar o mesmo repositório no mesmo commit.

A chave do cache é:

```text
repository_id + commit_sha + run_test_suite
```

Durante a mineração, o backend busca o SHA da branch padrão. Durante a análise, o analyzer confirma o `HEAD` real clonado. Se houver cache para o commit e modo de teste solicitados, o resultado é reaproveitado com `cache_hit: true`.

## Banco de Dados

O SQLite é inicializado automaticamente com o schema em:

```text
app/core/database.sql
```

Tabelas principais:

- `mining_runs`
- `search_filters`
- `repositories`
- `run_repositories`
- `analysis_results`
- `analysis_cache`
- `run_statistics`

## Validação Local

Para checar sintaxe/importação:

```powershell
.\.venv\Scripts\python.exe -m compileall app
```

Para listar as rotas expostas no OpenAPI:

```powershell
.\.venv\Scripts\python.exe -c "from app.main import app; print('\n'.join(sorted(app.openapi()['paths'].keys())))"
```
