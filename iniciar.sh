#!/usr/bin/env bash
# Miner - inicia tudo com um comando (precisa só do Docker).
set -u
cd "$(dirname "$0")"

IMAGEM=blarissa/miner:latest
CONTAINER=miner-backend-run
PORTA=8000
URL="http://localhost:${PORTA}"

if ! command -v docker >/dev/null 2>&1; then
  echo "O Docker não foi encontrado. Instale em https://docs.docker.com/get-docker/ e execute de novo." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "O Docker está fechado. Inicie o Docker, espere ele ficar pronto e execute de novo." >&2
  exit 1
fi

abrir() {
  echo "Miner pronto em ${URL}"
  if command -v xdg-open >/dev/null 2>&1; then xdg-open "${URL}" >/dev/null 2>&1 || true   # Linux
  elif [ "$(uname)" = "Darwin" ]; then open "${URL}"                                         # macOS
  fi
  echo
  echo "O Miner está rodando. Deixe este terminal aberto enquanto estiver usando."
  echo "Quando terminar, pressione qualquer tecla para encerrar o Miner."
  echo "(Seus resultados ficam guardados.)"
  read -r -n 1 -s || true
  docker stop "${CONTAINER}" >/dev/null 2>&1 || true
  echo "Miner encerrado."
}

if [ -n "$(docker ps -q --filter "name=^/${CONTAINER}$")" ]; then
  abrir
  exit 0
fi

echo "Verificando a versão do Miner..."
if ! docker pull "${IMAGEM}" && ! docker image inspect "${IMAGEM}" >/dev/null 2>&1; then
  if [ -f miner-backend/Dockerfile ]; then
    echo "Não foi possível baixar o Miner. Preparando a partir dos arquivos locais, pode levar vários minutos..."
    docker build -f miner-backend/Dockerfile -t "${IMAGEM}" . || { echo "Não foi possível preparar o Miner." >&2; exit 1; }
  else
    echo "Não foi possível baixar o Miner. Verifique a internet e tente de novo." >&2; exit 1
  fi
fi

# Token do GitHub: cada pessoa usa o próprio (grátis, sem permissões especiais).
# Ordem: variável de ambiente GITHUB_TOKEN, depois o arquivo guardado, senão pergunta uma única vez.
ARQ_TOKEN="${HOME}/.miner/github_token"
if [ -z "${GITHUB_TOKEN:-}" ] && [ -f "${ARQ_TOKEN}" ]; then
  GITHUB_TOKEN="$(head -n 1 "${ARQ_TOKEN}" | tr -d '[:space:]')"
fi
if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo
  echo "O Miner precisa de um token do GitHub para buscar repositórios. Ele é gratuito."
  echo "Crie em https://github.com/settings/tokens, escolha \"Generate new token\", classic,"
  echo "e NÃO marque nenhuma permissão. Depois cole o token abaixo (ele não aparece enquanto você cola)."
  echo "O token fica guardado só neste computador, em ${ARQ_TOKEN}"
  read -r -s -p "Cole o token e pressione Enter: " GITHUB_TOKEN || true
  echo
  GITHUB_TOKEN="$(printf '%s' "${GITHUB_TOKEN:-}" | tr -d '[:space:]')"
  if [ -z "${GITHUB_TOKEN}" ]; then
    echo "Nenhum token informado. Execute de novo quando tiver o token." >&2
    exit 1
  fi
  mkdir -p "$(dirname "${ARQ_TOKEN}")"
  ( umask 077; printf '%s\n' "${GITHUB_TOKEN}" > "${ARQ_TOKEN}" )
  echo "Token guardado. Para trocar de token, apague o arquivo ${ARQ_TOKEN}"
fi
export GITHUB_TOKEN

docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
echo "Iniciando o Miner..."
# O token vai pelo ambiente (-e sem valor), nunca na linha de comando.
docker run -d --rm --name "${CONTAINER}" -p "${PORTA}:10000" -e GITHUB_TOKEN -v miner-data:/app/data "${IMAGEM}" >/dev/null \
  || { echo "Não foi possível iniciar. Se a porta ${PORTA} estiver em uso, feche o programa que a usa." >&2; exit 1; }

echo "Aguardando o servidor..."
for _ in $(seq 1 60); do
  if curl -s -f "${URL}/health" >/dev/null 2>&1; then abrir; exit 0; fi
  sleep 2
done
echo "O servidor demorou demais para responder. Veja os logs com: docker logs ${CONTAINER}" >&2
exit 1
