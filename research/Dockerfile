# Reproducible CPU image for the research harness.
# Local neural models (bge-m3, e5, rerankers) are optional: build with --build-arg WITH_LOCAL_MODELS=1.
# On an Apple Silicon Mac, encoding the corpus is ~10x faster natively (MPS) than in this container;
# the embeddings it writes to research/data are reused as-is by container runs.
FROM python:3.12-slim

ARG WITH_LOCAL_MODELS=0
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/app/research/data/hf-cache

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/research
COPY pyproject.toml uv.lock ./
RUN if [ "$WITH_LOCAL_MODELS" = "1" ]; then \
        uv sync --frozen --no-install-project --extra dev --extra local; \
    else \
        uv sync --frozen --no-install-project --extra dev; \
    fi

COPY src ./src
COPY tests ./tests
COPY configs ./configs
COPY scripts ./scripts
RUN uv sync --frozen --extra dev $( [ "$WITH_LOCAL_MODELS" = "1" ] && echo --extra local )

ENTRYPOINT ["ragscale"]
CMD ["--help"]
