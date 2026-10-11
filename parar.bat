@echo off
rem Encerra o Miner. Os resultados ficam guardados no volume miner-data.
docker stop miner-backend-run >nul 2>&1
echo Miner encerrado.
timeout /t 3 >nul
