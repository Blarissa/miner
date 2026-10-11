@echo off
rem Miner - inicia tudo com um clique (precisa so do Docker Desktop aberto).
setlocal
cd /d "%~dp0"

set IMAGEM=miner-backend
set CONTAINER=miner-backend-run
set PORTA=8000
set URL=http://localhost:%PORTA%

where docker >nul 2>&1
if errorlevel 1 (
    echo O Docker Desktop nao foi encontrado neste computador.
    echo Instale em https://www.docker.com/products/docker-desktop/ e execute este arquivo de novo.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo O Docker Desktop esta fechado. Abra o Docker Desktop, espere ele iniciar e execute este arquivo de novo.
    pause
    exit /b 1
)

rem Ja esta rodando? Entao so abre o navegador.
for /f %%i in ('docker ps -q --filter "name=^/%CONTAINER%$"') do set JA_RODANDO=%%i
if defined JA_RODANDO goto abrir

rem Primeira vez: prepara a imagem (JDKs, Maven e a tela). Demora alguns minutos.
docker image inspect %IMAGEM% >nul 2>&1
if errorlevel 1 (
    echo Preparando o Miner pela primeira vez. Isso pode levar varios minutos...
    docker build -f miner-backend\Dockerfile -t %IMAGEM% .
    if errorlevel 1 (
        echo Nao foi possivel preparar o Miner. Veja a mensagem acima.
        pause
        exit /b 1
    )
)

docker rm -f %CONTAINER% >nul 2>&1
echo Iniciando o Miner...
docker run -d --rm --name %CONTAINER% -p %PORTA%:10000 -v miner-data:/app/data %IMAGEM% >nul
if errorlevel 1 (
    echo Nao foi possivel iniciar. Se a porta %PORTA% estiver em uso, feche o programa que a usa e tente de novo.
    pause
    exit /b 1
)

echo Aguardando o servidor...
set /a TENTATIVAS=0
:espera
curl -s -f %URL%/health >nul 2>&1
if not errorlevel 1 goto abrir
set /a TENTATIVAS+=1
if %TENTATIVAS% GEQ 60 (
    echo O servidor demorou demais para responder. Veja os logs com: docker logs %CONTAINER%
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto espera

:abrir
echo Miner pronto em %URL%
start "" %URL%
echo Para encerrar, execute parar.bat.
timeout /t 5 >nul
endlocal
