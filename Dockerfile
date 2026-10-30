FROM python:3.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CQ4OE_DATA_DIR=/app/data

RUN apt-get update && apt-get install -y --no-install-recommends openjdk-17-jre-headless curl gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && python -m pip check

COPY CQ2Term ./CQ2Term
COPY CQ2Onto ./CQ2Onto
COPY web ./web
COPY docker/entrypoint.sh ./docker/entrypoint.sh

RUN groupadd --system --gid 10001 cq4oe \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app --no-create-home cq4oe \
    && mkdir -p /app/data \
    && chown -R cq4oe:cq4oe /app/data

EXPOSE 8000
ENTRYPOINT ["/bin/sh", "/app/docker/entrypoint.sh"]
