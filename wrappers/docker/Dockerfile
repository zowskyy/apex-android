# APEX container image — GUI/mobile web server on port 8765.
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /src
COPY . /src

RUN pip install --no-cache-dir maturin \
    && pip install --no-cache-dir -e ".[mcp]" \
    && maturin build --release -m core/zip_reader/Cargo.toml -o /wheelhouse \
    && maturin build --release -m core/dex_reader/Cargo.toml -o /wheelhouse \
    && pip install --no-cache-dir /wheelhouse/*.whl

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY apex /app/apex

ENV APEX_WEB_WORKSPACE=/data
VOLUME /data
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health')"

CMD ["python", "-m", "apex", "mobile", "--port", "8765", "--workspace", "/data"]
