# APEX container image — GUI/mobile web server on port 8765.
# Base image pinned by digest for reproducible builds (multi-arch index).
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b
FROM ${PYTHON_IMAGE} AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && . "$HOME/.cargo/env" \
    && rustup default stable
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /src

# Lockfiles first for better layer caching
COPY Cargo.toml Cargo.lock ./
COPY core ./core
COPY pyproject.toml setup.py README.md LICENSE NOTICE requirements.txt requirements.lock ./
COPY apex ./apex

RUN pip install --no-cache-dir maturin \
    && pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps -e . \
    && maturin build --release --locked -m core/zip_reader/Cargo.toml -o /wheelhouse \
    && maturin build --release --locked -m core/dex_reader/Cargo.toml -o /wheelhouse \
    && pip install --no-cache-dir /wheelhouse/*.whl

# Redeclare ARG — Docker drops ARG scope after FROM
ARG PYTHON_IMAGE=python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b
FROM ${PYTHON_IMAGE}

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 apex \
    && useradd --system --uid 10001 --gid apex --home-dir /app --shell /usr/sbin/nologin apex

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY apex /app/apex

RUN mkdir -p /data && chown -R apex:apex /app /data

ENV APEX_WEB_WORKSPACE=/data
VOLUME /data
EXPOSE 8765

USER apex

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health')"

CMD ["python", "-m", "apex", "mobile", "--port", "8765", "--workspace", "/data"]
