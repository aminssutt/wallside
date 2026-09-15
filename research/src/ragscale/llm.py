"""Gemini client with a persistent SQLite cache, retries and token accounting.

Every call is keyed by (model, kind, payload, config) so experiments are re-runnable for free and
bit-identical: a cached response is returned instead of calling the API again.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

import numpy as np

from . import paths

log = logging.getLogger(__name__)


class _Cache:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v BLOB NOT NULL, created REAL NOT NULL)")
        self._lock = threading.Lock()

    def get(self, key: str) -> bytes | None:
        with self._lock:
            row = self._conn.execute("SELECT v FROM kv WHERE k = ?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, value: bytes) -> None:
        with self._lock:
            self._conn.execute("INSERT OR REPLACE INTO kv (k, v, created) VALUES (?, ?, ?)", (key, value, time.time()))


def _key(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class Usage:
    calls: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    by_model: dict[str, dict[str, int]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, model: str, inp: int, out: int, think: int) -> None:
        with self._lock:
            self.calls += 1
            self.input_tokens += inp
            self.output_tokens += out
            self.thinking_tokens += think
            m = self.by_model.setdefault(model, {"calls": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0})
            m["calls"] += 1
            m["input_tokens"] += inp
            m["output_tokens"] += out
            m["thinking_tokens"] += think

    def hit(self) -> None:
        with self._lock:
            self.cache_hits += 1

    def summary(self) -> dict:
        return {
            "api_calls": self.calls,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "thinking_tokens": self.thinking_tokens,
            "by_model": self.by_model,
        }


_RETRYABLE = ("429", "500", "502", "503", "504", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE", "timed out", "Timeout")
# Billing/quota exhaustion also comes back as 429 but never resolves by waiting.
_FATAL = ("credits are depleted", "billing", "API key not valid", "PERMISSION_DENIED", "exceeded your current quota")


class FatalAPIError(RuntimeError):
    """The API cannot serve any further request (billing, invalid key): abort the whole batch."""


class CacheMiss(RuntimeError):
    """Offline mode: the response is not in the local cache."""


class Gemini:
    def __init__(self, max_workers: int = 8, cache_path=None, offline: bool | None = None):
        """offline=True (or RAGSCALE_OFFLINE=1): serve only cached responses, never call the API."""
        from google import genai

        self.offline = offline if offline is not None else os.getenv("RAGSCALE_OFFLINE", "0") == "1"
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key and not self.offline:
            raise RuntimeError("GOOGLE_API_KEY is not set (expected in the repo-root .env)")
        self._client = None if self.offline else genai.Client(api_key=api_key)
        self._cache = _Cache(cache_path or paths.CACHE_DIR / "gemini.sqlite")
        self.usage = Usage()
        self.max_workers = max_workers

    # ------------------------------------------------------------------ helpers
    def _with_retries(self, fn: Callable[[], Any], what: str, attempts: int = 8) -> Any:
        for attempt in range(attempts):
            try:
                return fn()
            except Exception as exc:  # google-genai raises several error types; classify by message
                msg = str(exc)
                if any(tok in msg for tok in _FATAL):
                    raise FatalAPIError(msg[:300]) from exc
                if attempt == attempts - 1 or not any(tok in msg for tok in _RETRYABLE):
                    raise
                delay = min(60.0, 2**attempt) * (0.5 + random.random())
                log.warning("%s failed (%s); retry %d in %.1fs", what, msg[:160], attempt + 1, delay)
                time.sleep(delay)
        raise AssertionError("unreachable")

    # --------------------------------------------------------------- embeddings
    def embed(self, texts: Sequence[str], model: str, task_type: str, batch_size: int = 100) -> np.ndarray:
        """Embed texts (cached per text). Returns float32 L2-normalized matrix."""
        from google.genai import types

        keys = [_key("embed", model, task_type, t) for t in texts]
        out: list[np.ndarray | None] = []
        missing: list[int] = []
        for i, k in enumerate(keys):
            blob = self._cache.get(k)
            if blob is None:
                out.append(None)
                missing.append(i)
            else:
                self.usage.hit()
                out.append(np.frombuffer(blob, dtype=np.float32))

        if missing and self.offline:
            raise CacheMiss(f"{len(missing)} embeddings not cached for {model}/{task_type}")
        batches = [missing[i : i + batch_size] for i in range(0, len(missing), batch_size)]

        def run(batch: list[int]) -> None:
            contents = [texts[i] for i in batch]
            resp = self._with_retries(
                lambda: self._client.models.embed_content(
                    model=model, contents=contents, config=types.EmbedContentConfig(task_type=task_type)
                ),
                f"embed[{model}]",
            )
            self.usage.add(model, sum(len(c) for c in contents) // 4, 0, 0)  # API returns no token count; ~4 chars/token
            for i, emb in zip(batch, resp.embeddings):
                vec = np.asarray(emb.values, dtype=np.float32)
                self._cache.put(keys[i], vec.tobytes())
                out[i] = vec

        self._map(run, batches, desc=f"embed {model}")
        matrix = np.stack(out).astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.clip(norms, 1e-12, None)

    # --------------------------------------------------------------- generation
    def generate(
        self,
        prompt: str,
        model: str,
        system: str | None = None,
        temperature: float = 0.0,
        json_schema: dict | None = None,
        max_output_tokens: int = 4096,
        thinking_budget: int | None = None,
        cache_tag: str = "",
    ) -> dict:
        """Returns {"text", "json" (if schema), "usage"}; cached by all inputs."""
        from google.genai import types

        config_repr = {
            "system": system,
            "temperature": temperature,
            "schema": json_schema,
            "max_output_tokens": max_output_tokens,
            "thinking_budget": thinking_budget,
            "tag": cache_tag,
        }
        key = _key("generate", model, prompt, config_repr)
        blob = self._cache.get(key)
        if blob is not None:
            self.usage.hit()
            return json.loads(blob)
        if self.offline:
            raise CacheMiss(f"generate[{model}] not cached")

        cfg: dict[str, Any] = {"temperature": temperature, "max_output_tokens": max_output_tokens}
        if system:
            cfg["system_instruction"] = system
        if json_schema is not None:
            cfg["response_mime_type"] = "application/json"
            cfg["response_json_schema"] = json_schema
        if thinking_budget is not None:
            cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)

        resp = self._with_retries(
            lambda: self._client.models.generate_content(
                model=model, contents=prompt, config=types.GenerateContentConfig(**cfg)
            ),
            f"generate[{model}]",
        )
        meta = resp.usage_metadata
        usage = {
            "input_tokens": int(getattr(meta, "prompt_token_count", 0) or 0),
            "output_tokens": int(getattr(meta, "candidates_token_count", 0) or 0),
            "thinking_tokens": int(getattr(meta, "thoughts_token_count", 0) or 0),
        }
        self.usage.add(model, usage["input_tokens"], usage["output_tokens"], usage["thinking_tokens"])
        text = resp.text or ""
        result: dict[str, Any] = {"text": text, "usage": usage, "model": model}
        if json_schema is not None:
            try:
                result["json"] = json.loads(text)
            except json.JSONDecodeError:
                result["json"] = None
        finish = resp.candidates[0].finish_reason if resp.candidates else None
        result["finish_reason"] = str(finish)
        if result.get("json", True) is not None:  # never cache unparseable/truncated output
            self._cache.put(key, json.dumps(result, ensure_ascii=False).encode("utf-8"))
        return result

    def _map(self, fn: Callable[[Any], Any], items: Iterable[Any], desc: str = "") -> list[Any]:
        from tqdm import tqdm

        items = list(items)
        if not items:
            return []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            return list(tqdm(pool.map(fn, items), total=len(items), desc=desc, leave=False))

    def map_generate(self, prompts: Sequence[dict], desc: str = "generate") -> list[dict]:
        """Parallel generate over kwargs dicts; failures become {"error": ...} instead of aborting the batch."""

        def run(kwargs: dict) -> dict:
            try:
                return self.generate(**kwargs)
            except FatalAPIError:
                raise
            except Exception as exc:
                log.error("generation failed: %s", str(exc)[:300])
                return {"error": str(exc)}

        return self._map(run, prompts, desc=desc)
