FROM docker.io/library/python:3.13-slim-trixie

RUN apt-get update && \
    apt-get install -y --no-install-recommends restic && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python3 -m pip install --break-system-packages --no-cache-dir .

ENTRYPOINT ["restic-profile"]
CMD ["--help"]
