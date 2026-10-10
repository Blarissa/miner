# Procedimentos (como trabalhamos)

Os combinados pessoais do usuário ficam em `Cerebelo/combinados.md` (vêm da pasta `Usuario/` da Fórmula). Os procedimentos da tecnologia do projeto ficam nos arquivos dos perfis (ex.: `Cerebelo/codigo.md`).

## Sempre
- **Dúvida**: primeiro o Cérebro e o material do projeto; só perguntar o que não dá para descobrir.
- **Seguir o padrão que já existe** (nomes, formato, estrutura). Na dúvida, copiar o jeito do vizinho.
- Pedidos de demonstração/teste rápido não vão para o Cérebro.
- Ao terminar cada tarefa: aviso de fim de tarefa na Medula (se instalada).

## Arquivos no PC do usuário
1. **Sempre** trazer a versão atual antes de editar (o usuário edita também).
2. Editar com script lendo o arquivo real, nunca redigitando.
3. Gravar com `expectedMtimeMs`; saída com nome novo por versão quando regravar.
4. Conferir o resultado (abrir, compilar, print) **antes** de entregar.

## Medula (executora no PC) — se instalada
- Pedido: gravar `medula\fila\<id>.json` (a pasta `medula` fica dentro do projeto) = `{"id": "<id>", "acao": "<nome>"}`.
  Campos opcionais: `"projeto": "<apelido>"` (projeto da config; sem ele = projeto padrão) e `"app": "<apelido>"` (só para `abrir`).
- Resultado: `resultados\<id>.json` (`status`, `categoria`, `saida`, tempos). Esperar alguns segundos e trazer o arquivo.
- `ping` lista as ações e projetos disponíveis — use no começo do dia se tiver dúvida.
- **Reflexo** (consulta, compilar, print, servidor local): pode pedir direto.
- **Movimento** (git que grava, envio para fora, gravação em sistema real): perguntar no chat antes; o usuário ainda clica **Autorizar** na tela (5 min). `nao_autorizado` = não executou.
- Ação nova: o Córtex propõe o trecho do `medula.config.json` e mostra no chat; o usuário grava (ou deixa o Córtex gravar) e **aprova na tela** quando a Medula recarrega. Sem aprovação na tela a Medula continua com a config antiga.
- Commit: escrever `medula\mensagem_commit.txt`, mostrar no chat, pedir `projeto-git-commit-msg`; push em pedido separado.

## Aviso de fim de tarefa
- No início da tarefa: guardar `date +%s`. No fim: gravar
  `medula\avisos\<nome>_<id>.json` = `{"tarefa": "...", "duracao_segundos": N, "detalhe": "..."}`.

## Rotina do dia
- **Bom dia**: a Medula roda sozinha 1x por dia (git, pendências, URL, falado). O Córtex lê o Cérebro na ordem do README.
- **Síntese diária**: ver README. Se o PC estiver fora do ar, deixar os arquivos prontos e gravar quando voltar.

## Do projeto
- Como rodar, conferir e testar: ver `Cerebelo/codigo.md` e `Cerebelo/python.md` (seção "Do projeto").
- Mexer em busca/análise: ler antes `MemoriaLongoPrazo/arquitetura.md` e os alertas 11 a 19; qualquer teste que busque no GitHub de verdade gasta limite do token e é MOVIMENTO (avisar antes).
- Mexer no schema: editar `core/database.sql` e a migração em `core/database.py` juntos, e conferir `banco-de-dados.md` (alerta 8).
