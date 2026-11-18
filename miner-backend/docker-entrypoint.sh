#!/bin/bash
# Roda como root só para ajustar a permissão do volume/disco montado em /app/data
# (discos do Render e volumes do Docker chegam com dono root) e depois
# entrega a execução ao usuário sem privilégios, que roda o Maven nos repositórios minerados.
set -e
mkdir -p /app/data
chown -R appuser:appuser /app/data || echo "Aviso: nao foi possivel ajustar as permissoes de /app/data" >&2
# Só o appuser lê o banco: o sandbox (código dos repositórios minerados) fica de fora.
chmod 700 /app/data || echo "Aviso: nao foi possivel restringir /app/data" >&2
# A pasta dos repositórios pertence ao sandbox (o volume antigo, se existir, vinha como appuser).
chown sandbox:sandbox /app/app/services/repos 2>/dev/null || true
exec runuser -u appuser -- bash -lc "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"
