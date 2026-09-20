FROM python:3.13-slim

SHELL ["/bin/bash", "-o", "pipefail", "-lc"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SDKMAN_DIR=/home/laris/.sdkman \
    DATABASE_URL=sqlite:////app/data/minerador.db

ENV PATH="${SDKMAN_DIR}/candidates/java/current/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl unzip zip git maven ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p "${SDKMAN_DIR}" \
    && curl -fsSL "https://get.sdkman.io" | bash

RUN source "${SDKMAN_DIR}/bin/sdkman-init.sh" \
    && sed -i 's/sdkman_auto_answer=false/sdkman_auto_answer=true/' "${SDKMAN_DIR}/etc/config" \
    && sdk install java 6.0.119-zulu \
    && sdk install java 7.0.352-zulu \
    && sdk install java 8.0.402-zulu \
    && sdk install java 11.0.22-tem \
    && sdk install java 14.0.2-open \
    && sdk install java 15.0.2-open \
    && sdk install java 16.0.2-open \
    && sdk install java 17.0.10-tem \
    && sdk install java 18.0.2-open \
    && sdk install java 19.0.2-open \
    && sdk install java 20.0.2-open \
    && sdk install java 21.0.2-tem \
    && sdk install java 22.0.2-zulu \
    && sdk install java 23.0.2-zulu \
    && sdk default java 17.0.10-tem

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data app/services/repos app/services/logs \
    && useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app /home/laris/.sdkman

USER appuser

EXPOSE 10000

CMD ["bash", "-lc", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]