#!/usr/bin/env bash
# Miner - inicia tudo com um comando (precisa só do Docker).
set -u
cd "$(dirname "$0")"

IMAGEM=ghcr.io/blarissa/miner:latest
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
  echo "Para encerrar, execute ./parar.sh"
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

docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
echo "Iniciando o Miner..."
docker run -d --rm --name "${CONTAINER}" -p "${PORTA}:10000" -v miner-data:/app/data "${IMAGEM}" >/dev/null \
  || { echo "Não foi possível iniciar. Se a porta ${PORTA} estiver em uso, feche o programa que a usa." >&2; exit 1; }

echo "Aguardando o servidor..."
for _ in $(seq 1 60); do
  if curl -s -f "${URL}/health" >/dev/null 2>&1; then abrir; exit 0; fi
  sleep 2
done
echo "O servidor demorou demais para responder. Veja os logs com: docker logs ${CONTAINER}" >&2
exit 1
