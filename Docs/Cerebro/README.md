# Cérebro — projeto

Miner: plataforma web (FastAPI + React) para descobrir, filtrar e analisar repositórios Java no GitHub (compilação, testes, estatísticas em SQLite).

Memória de trabalho entre os chats. Fica junto do projeto (dentro do repositório ou da pasta do trabalho) e viaja com ele.
Criado em 2026-10-08 · tipo de projeto: codigo, python

## Quem é quem

| Parte | O que é | Onde fica |
|---|---|---|
| **Córtex** | O Claude no chat: pensa, decide, produz e pede as ações | o chat |
| **Cérebro** | Estas notas: o que foi feito, decidido, aprendido e o que falta | esta pasta |
| **Medula** (opcional) | Programa no PC que executa uma lista fechada de ações e mostra avisos | `medula\` na pasta do projeto |

## Início do dia — "bom dia" (o Córtex lê nesta ordem)

1. `README.md` (este arquivo)
2. `Amigdala/` (todos os arquivos) — o que NÃO pode dar errado
3. `CortexPreFrontal/pendencias.md` — o que está em aberto e o próximo passo
4. O diário mais recente em `Hipocampo/`
5. Sob demanda: `MemoriaLongoPrazo/`, `Cerebelo/`, `LoboTemporal/`

Depois diz em poucas linhas o estado do projeto e propõe por onde começar.

## Fim do dia — "síntese diária"

1. Criar `Hipocampo/AAAA-MM-DD.md` (modelo em `Hipocampo/_modelo.md`).
2. Atualizar `CortexPreFrontal/pendencias.md` (marcar `[x]`, acrescentar as novas com data, atualizar "Atualizado em").
3. Acrescentar as decisões do dia em `MemoriaLongoPrazo/decisoes.md`.
4. O que virou conhecimento estável (regra, estrutura, receita) vai para `MemoriaLongoPrazo/` ou `Cerebelo/`.
5. Armadilha nova → `Amigdala/alertas.md`. Lição que vale para qualquer projeto → `MemoriaLongoPrazo/aprendizados-gerais.md`.
6. Atualizar o índice abaixo. Nada de commit/publicação sem o usuário pedir.

## Estrutura

| Pasta | Função no cérebro | O que guardamos aqui |
|---|---|---|
| `Amigdala/` | Alerta e risco | Armadilhas conhecidas e cuidados antes de mexer |
| `CortexPreFrontal/` | Planejamento | Pendências, próximos passos, perguntas em aberto |
| `Hipocampo/` | Memória recente | Um diário por dia de trabalho |
| `MemoriaLongoPrazo/` | Conhecimento consolidado | Visão geral, regras, decisões, aprendizados |
| `Cerebelo/` | Movimentos automáticos | Como trabalhamos: combinados, procedimentos, receitas |
| `LoboTemporal/` | Linguagem e referências | Fontes, sistemas, APIs, documentos e contatos (nunca segredos) |

Regra de ouro: **cada informação mora em um lugar só**. Diário conta o que aconteceu; o que vale para sempre sobe para `MemoriaLongoPrazo/` ou `Cerebelo/`.

## Índice

- [Hipocampo/2026-10-08.md](Hipocampo/2026-10-08.md)
- [Amigdala/alertas-codigo.md](Amigdala/alertas-codigo.md)
- [Amigdala/alertas.md](Amigdala/alertas.md)
- [Cerebelo/codigo.md](Cerebelo/codigo.md)
- [Cerebelo/combinados.md](Cerebelo/combinados.md)
- [Cerebelo/procedimentos.md](Cerebelo/procedimentos.md)
- [Cerebelo/python.md](Cerebelo/python.md)
- [CortexPreFrontal/pendencias.md](CortexPreFrontal/pendencias.md)
- [LoboTemporal/referencias.md](LoboTemporal/referencias.md)
- [MemoriaLongoPrazo/aprendizados-gerais.md](MemoriaLongoPrazo/aprendizados-gerais.md)
- [MemoriaLongoPrazo/aprendizados-git.md](MemoriaLongoPrazo/aprendizados-git.md)
- [MemoriaLongoPrazo/arquitetura.md](MemoriaLongoPrazo/arquitetura.md)
- [MemoriaLongoPrazo/banco-de-dados.md](MemoriaLongoPrazo/banco-de-dados.md)
- [MemoriaLongoPrazo/decisoes.md](MemoriaLongoPrazo/decisoes.md)
- [MemoriaLongoPrazo/visao-geral.md](MemoriaLongoPrazo/visao-geral.md)
