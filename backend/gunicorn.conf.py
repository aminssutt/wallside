"""Gunicorn runtime config tuned for SSE + external HTTP calls on Dokploy.

Defaults prioritize stability over raw concurrency to avoid worker kills
when vector stores and enrichment tasks are active.
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread").strip() or "gthread"
workers = _env_int("GUNICORN_WORKERS", 1, minimum=1)
threads = _env_int("GUNICORN_THREADS", 8, minimum=1) if worker_class == "gthread" else 1

timeout = _env_int("GUNICORN_TIMEOUT", 180, minimum=30)
graceful_timeout = _env_int("GUNICORN_GRACEFUL_TIMEOUT", 45, minimum=10)
keepalive = _env_int("GUNICORN_KEEPALIVE", 10, minimum=1)

# Disable worker recycling by default so long SSE streams are never killed
# mid-response when a worker happens to hit the request ceiling. Ops can
# still opt back in via env var if memory pressure demands it.
max_requests = _env_int("GUNICORN_MAX_REQUESTS", 0, minimum=0)
max_requests_jitter = _env_int("GUNICORN_MAX_REQUESTS_JITTER", 0, minimum=0)

# Keep preload disabled by default to limit memory spikes with FAISS + per-worker state.
preload_app = _env_bool("GUNICORN_PRELOAD", False)

# Reduce disk I/O pressure for worker heartbeat/temp files.
worker_tmp_dir = "/dev/shm"

# Avoid too-verbose access logs by default in container stdout.
accesslog = os.getenv("GUNICORN_ACCESSLOG", "-")
errorlog = os.getenv("GUNICORN_ERRORLOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
