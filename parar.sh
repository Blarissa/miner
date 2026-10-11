#!/usr/bin/env bash
# Encerra o Miner. Os resultados ficam guardados no volume miner-data.
docker stop miner-backend-run >/dev/null 2>&1
echo "Miner encerrado."
