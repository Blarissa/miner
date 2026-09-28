# Miner Front

Interface web em React, TypeScript, Vite e Tailwind CSS para operar o Miner Backend. O front permite iniciar minerações no GitHub, acompanhar a execução em tempo quase real, carregar consultas antigas pelo Run ID, visualizar repositórios encontrados e consultar estatísticas da análise.

## O Que A Interface Faz

- Inicia buscas no GitHub usando Code Search ou Repository Search.
- Permite informar múltiplas queries na mesma execução.
- Envia filtros como versão Java, arquivo, extensão, estrelas, forks, licença, organização, usuário, datas e outros qualificadores.
- Permite exigir apenas projetos buildáveis ou apenas projetos com testes aprovados.
- Permite habilitar upgrade automático de JDK na análise.
- Acompanha o progresso consultando o backend a cada 5 segundos.
- Mostra resultados parciais enquanto a mineração ainda está rodando.
- Permite cancelar e retomar execuções quando o backend disponibiliza essa ação.
- Carrega execuções antigas informando o Run ID.
- Mostra estatísticas da execução, funil de análise, versões Java, tempos, frameworks de teste, bibliotecas de mock/assertion e estágios de eliminação.
- Inclui uma página de documentação dentro da própria aplicação.

## Tecnologias

- React 19.
- TypeScript.
- Vite.
- Tailwind CSS.
- Lucide React para ícones.

## Estrutura Principal

```text
src/
  api/
    repositories.ts
  components/
    DocumentationPage.tsx
    MiningDashboard.tsx
    StatisticsPage.tsx
  models/
    types.ts
  App.tsx
  main.tsx
```

## Requisitos

- Node.js instalado.
- npm instalado.
- Miner Backend rodando e acessível pela URL configurada em `VITE_API_URL`.

## Configuração Do `.env`

Crie ou edite o arquivo `.env` na raiz do `miner-front`:

```env
VITE_API_URL=http://localhost:8000
```

Essa URL deve apontar para o backend. Se o backend estiver rodando via Docker com `-p 8000:10000`, mantenha `http://localhost:8000`.

No backend, o `CORS_ORIGINS` precisa permitir o endereço do front. Em desenvolvimento, o Vite normalmente roda em:

```text
http://localhost:5173
```

Então o `.env` do backend deve conter:

```env
CORS_ORIGINS=["http://localhost:5173"]
```

## Como Executar Em Desenvolvimento

Entre na pasta do front:

```powershell
cd C:\Users\SEU_USUARIO\Desktop\projeto\miner-front
```

Instale as dependências:

```powershell
npm install
```

Confira o `.env`:

```env
VITE_API_URL=http://localhost:8000
```

Suba o servidor de desenvolvimento:

```powershell
npm run dev
```

Acesse a URL exibida pelo Vite. Normalmente será:

```text
http://localhost:5173
```

Para usar a aplicação corretamente, o backend precisa estar rodando antes ou durante o uso do front.

## Como Usar Com O Backend

1. Suba o backend em `http://localhost:8000`.
2. Suba o front com `npm run dev`.
3. Acesse `http://localhost:5173`.
4. Na tela inicial, escolha `Nova busca` para iniciar uma mineração ou informe um Run ID antigo para carregar uma execução persistida.
5. Na tela de mineração, informe a query, o token do GitHub se necessário, os filtros e as opções de análise.
6. Clique em `Iniciar Mineração`.
7. Acompanhe o progresso, os repositórios retornados e as estatísticas.

## Scripts Disponíveis

Executa o front em modo desenvolvimento:

```powershell
npm run dev
```

Gera a versão de produção em `dist/`:

```powershell
npm run build
```

Executa o lint:

```powershell
npm run lint
```

Serve localmente o build de produção:

```powershell
npm run preview
```

## Build De Produção

Para gerar os arquivos finais:

```powershell
npm run build
```

Depois, para testar localmente:

```powershell
npm run preview
```

O preview usa os arquivos de `dist/`. A URL do backend continua vindo de `VITE_API_URL`, então ajuste o `.env` antes de gerar o build caso vá apontar para outro servidor.

## Observações Importantes

- A busca de código do GitHub exige autenticação. Informe o token no formulário ou configure `GITHUB_TOKEN` no backend.
- O front não minera repositórios sozinho; ele apenas chama a API do backend.
- As execuções ficam salvas no banco SQLite do backend, não no navegador.
- Para carregar uma execução antiga, use o Run ID exibido durante a mineração.
- Se a tela mostrar erro de conexão, confira se `VITE_API_URL` está correto e se o backend está rodando.
- Se houver erro de CORS, confira `CORS_ORIGINS` no `.env` do backend.
