# Aprendizados — git

- **Funcionalidade que sumiu num merge**: achar o último commit onde ela existia (`git log -S "<trecho>"`) e trazer só os pedaços, sem reverter o merge. Compilar e listar o que ficou de fora.
- Pull/troca de branch bloqueados por alteração local: avisar e deixar o usuário decidir (stash, commit ou descartar).
- Saída longa do git é cortada: o hash do último commit está em `.git\refs\heads\<branch>`.
- Sem console, o git trava pedindo senha: a Medula roda com `GIT_TERMINAL_PROMPT=0` (falha em vez de travar). Credencial do remoto tem que estar no gerenciador do Windows.
- Mensagem de commit: título curto, corpo com o porquê, trailer `Co-Authored-By` do Claude.
