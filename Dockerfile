# Multi-stage production build for CodeGraph MCP & Engine
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip build \
    && python -m build --wheel

# Runtime stage
FROM python:3.12-slim-bookworm AS runner

LABEL org.opencontainers.image.title="CodeGraph MCP" \
      org.opencontainers.image.description="Deterministic, local-first code graph engine and MCP server" \
      org.opencontainers.image.version="3.0.1" \
      org.opencontainers.image.source="https://github.com/raghurammrsd/CODEGRAPH_MCP"

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -rf /tmp/*.whl

# Expose default Web UI port and FastMCP stream
EXPOSE 8765

# Non-root user for enterprise container security
RUN useradd -m -u 1001 codegraph && chown -R codegraph:codegraph /workspace
USER codegraph

ENV PYTHONUNBUFFERED=1 \
    CODEGRAPH_PORT=8765 \
    CODEGRAPH_HOST=0.0.0.0

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8765/api/status || exit 1

ENTRYPOINT ["python", "-m", "codegraph"]
CMD ["ui", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
