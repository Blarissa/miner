# Aprendizados gerais

Lições que valem para qualquer projeto. Projeto novo: ler uma vez. Lição de uma tecnologia específica vai para o arquivo do perfil (ex.: `aprendizados-dotnet.md`).

## Jeito de trabalhar que deu certo

- **Pedido curto/genérico**: estudar o que existe → listar o que está quebrado/faltando → perguntar com opções (a recomendada primeiro) → fazer só o escolhido; o resto vira pendência.
- **"Funciona lá e não aqui"**: achar o caso que funciona, comparar passo a passo, listar as diferenças e aplicar só depois do "pode aplicar". Dar visibilidade (log, print, exemplo real) antes de adivinhar.
- Ler linha a linha o print, log ou documento que o usuário manda — a pista costuma estar lá.
- O usuário reclamou do formato: refazer **no padrão dele** (olhar como ele fez o vizinho) em vez de defender a primeira versão.
- Cada entrega com conferência: casos normal, borda e inválido simulados antes; conferência real quando for seguro.
- Dúvida: procurar primeiro no Cérebro e no material do projeto; só perguntar o que não dá para descobrir.

## Memória (o próprio Cérebro)

- Diário curto e por assunto; o que vale para sempre sobe para `MemoriaLongoPrazo/` — senão o conhecimento fica enterrado num dia antigo.
- Pendência sem data e sem dono vira lixo: toda pendência nova entra numa seção com a data.
- Decisão anotada com a frase de quem decidiu evita discutir de novo.

## Arquivos no PC do usuário (bridge)

- Editar com script que lê o arquivo real, nunca redigitando de memória (a saída de ferramenta pode vir cortada).
- Substituição por âncora: âncora repetida troca o lugar errado → `assert count == 1`; ao cortar entre duas âncoras, procurar a segunda **a partir** da primeira.
- Manter a codificação do original (BOM, CRLF/LF) e conferir antes de gravar.
- Gravar com `expectedMtimeMs` para não passar por cima de edição mais nova do usuário.

## Segurança

- Distribuir senha: link de uso único com passphrase combinada; o login vai em outra mensagem.
- Teste que manda algo de verdade: destino da equipe ou inexistente, nunca inventado.

## Diagnóstico de "não acha mais resultados" (2026-10-08)

- Ler a mensagem real da falha antes de culpar filtros ou código: aqui o erro estava gravado no banco (`JAVA_HOME ... not defined correctly`) e explicava tudo.
- Falha de ambiente classificada como falha do item (teste/compilação) polui estatística e cache. Separar "o repositório é ruim" de "a máquina não consegue avaliar".
- Cache de resultado negativo precisa de regra: não guardar erro de infraestrutura, ou expirar rápido.
- Conferir o branch e o `git status` no começo; documentar um commit antigo gera Cérebro errado.
- Sem a credencial, quem precisa dela cola em campo próprio (ou painel injetado): o Córtex nunca digita senha/token e pede sempre que precisar.
- Ferramenta de navegador do app pode bloquear chamadas entre portas de localhost; testar o backend pela própria página dele.
