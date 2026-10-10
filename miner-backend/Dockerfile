# JDKs vindos de imagens oficiais (reprodutível; sem SDKMAN). A versão exata pode ser fixada
# trocando a tag por um digest (ex.: eclipse-temurin:17-jdk-jammy@sha256:...).
# JDK 6 e 7: imagens da Azul (a 6 está marcada como inativa no Docker Hub, mas ainda baixa).
# Versões intermediárias (14 a 20, 22 a 24) não têm imagem Temurin: use allow_jdk_upgrade.

FROM azul/zulu-openjdk:6 AS jdk6
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM azul/zulu-openjdk:7 AS jdk7
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:8-jdk-jammy AS jdk8
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:11-jdk-jammy AS jdk11
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:17-jdk-jammy AS jdk17
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:21-jdk-jammy AS jdk21
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM eclipse-temurin:25-jdk-jammy AS jdk25
RUN JH="$(dirname "$(dirname "$(readlink -f "$(command -v javac)")")")" \
    && mkdir -p /jdk && cp -a "$JH"/. /jdk/

FROM python:3.13-slim

SHELL ["/bin/bash", "-o", "pipefail", "-lc"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JDK_BASE_DIR=/opt/jdks \
    JDK_LAYOUT=versions \
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
COPY --from=jdk11 /jdk /opt/jdks/11
COPY --from=jdk17 /jdk /opt/jdks/17
COPY --from=jdk21 /jdk /opt/jdks/21
COPY --from=jdk25 /jdk /opt/jdks/25

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