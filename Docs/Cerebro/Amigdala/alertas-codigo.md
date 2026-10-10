# Alertas de código

1. **A IDE sobrescreve as edições do Córtex.** Arquivo aberto + salvar = versão antiga volta ao disco. Pedir "Recarregar / Sim para todos" ou fechar a aba sem salvar; conferir o disco depois.
2. **Python escrevendo outra linguagem**: delimitadores podem fechar a string do Python (ex.: o `'''` do comentário XML do VB). Guardar o trecho em arquivo separado ou usar marcador e trocar ao salvar.
3. **`git add -A` pega tudo** que não está no `.gitignore`: conferir `git status` antes de commitar. Repositório com credencial = privado.
4. **Coluna/campo que o usuário ainda vai criar**: código novo não pode quebrar sem ele (checar a existência antes de usar).
5. **Compilou ≠ funciona**: depois de compilar, testar o caminho real ou dizer claramente que não foi testado.
6. **Programa do projeto aberto segura arquivos**: compilação falha por "arquivo em uso" — fechar o programa e compilar de novo.
7. **API local apontando para banco real** grava de verdade: teste é MOVIMENTO.
8. **Código duplicado em dois lugares** (mesma regra em dois projetos/telas): correção num lugar vai para o outro.
