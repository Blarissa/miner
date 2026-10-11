# JDKs vindos de imagens oficiais (reprodutível; sem SDKMAN). A versão exata pode ser fixada
# trocando a tag por um digest (ex.: eclipse-temurin:17-jdk-jammy@sha256:...).
# A tag azul/zulu-openjdk:6 está marcada como inativa no Docker Hub (2018), mas ainda baixa.
# Versões sem imagem Temurin (6, 7, 9, 10, 12 a 16, 18 a 20, 22 a 24) vêm da Azul (azul/zulu-openjdk:<n>).

FROM azul/zulu-openjdk:6 AS jdk6
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:7 AS jdk7
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:8-jdk-jammy AS jdk8
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:9 AS jdk9
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:10 AS jdk10
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:11-jdk-jammy AS jdk11
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:12 AS jdk12
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:13 AS jdk13
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:14 AS jdk14
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:15 AS jdk15
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:16 AS jdk16
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:17-jdk-jammy AS jdk17
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:18 AS jdk18
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:19 AS jdk19
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:20 AS jdk20
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:21-jdk-jammy AS jdk21
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:22 AS jdk22
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:23 AS jdk23
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:24 AS jdk24
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:25-jdk-jammy AS jdk25
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:26-jdk-jammy AS jdk26
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM python:3.13-slim

SHELL ["/bin/bash", "-o", "pipefail", "-lc"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JDK_BASE_DIR=/opt/jdks \
    JAVA_HOME=/opt/jdks/17 \
    DATABASE_URL=sqlite:////app/data/minerador.db

ENV PATH="/opt/jdks/17/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl unzip zip git maven ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=jdk6 /jdk /opt/jdks/6
COPY --from=jdk7 /jdk /opt/jdks/7
COPY --from=jdk8 /jdk /opt/jdks/8
COPY --from=jdk9 /jdk /opt/jdks/9
COPY --from=jdk10 /jdk /opt/jdks/10
COPY --from=jdk11 /jdk /opt/jdks/11
COPY --from=jdk12 /jdk /opt/jdks/12
COPY --from=jdk13 /jdk /opt/jdks/13
COPY --from=jdk14 /jdk /opt/jdks/14
COPY --from=jdk15 /jdk /opt/jdks/15
COPY --from=jdk16 /jdk /opt/jdks/16
COPY --from=jdk17 /jdk /opt/jdks/17
COPY --from=jdk18 /jdk /opt/jdks/18
COPY --from=jdk19 /jdk /opt/jdks/19
COPY --from=jdk20 /jdk /opt/jdks/20
COPY --from=jdk21 /jdk /opt/jdks/21
COPY --from=jdk22 /jdk /opt/jdks/22
COPY --from=jdk23 /jdk /opt/jdks/23
COPY --from=jdk24 /jdk /opt/jdks/24
COPY --from=jdk25 /jdk /opt/jdks/25
COPY --from=jdk26 /jdk /opt/jdks/26

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data app/services/repos app/services/logs \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

# USER appuser  # antes: rodava direto como appuser; agora o entrypoint ajusta /app/data e troca para appuser
RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

EXPOSE 10000

# CMD ["bash", "-lc", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
ENTRYPOINT ["/app/docker-entrypoint.sh"]