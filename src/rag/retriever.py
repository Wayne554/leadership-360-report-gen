"""RAGFlow 检索器：从向量知识库检索发展性反馈。"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from src.rag.config import (
    ALL_DATASETS,
    DIMENSION_QUERIES,
    FALLBACK_ADVICE,
    RAGFLOW_API_KEY,
    RAGFLOW_API_URL,
    RAG_CACHE_DIR,
    SIMILARITY_THRESHOLD,
    TOP_K,
)

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 7
CACHE_TTL_SECONDS = CACHE_TTL_DAYS * 86400


def _request_json(url, api_key, *, method="GET", body=None, content_type="application/json", timeout=30):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    }
    if body is not None:
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        logger.warning("RAGFlow HTTP %s: %s", exc.code, exc.reason)
        raise
    except urllib.error.URLError as exc:
        logger.warning("RAGFlow connection failed: %s", exc.reason)
        raise

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Non-JSON response: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object from server")

    return payload


def _ensure_success(payload):
    code = payload.get("code")
    if code != 0:
        msg = payload.get("message", f"API error code {code}")
        raise ValueError(msg)
    return payload


def _extract_chunks(payload):
    data = payload.get("data", {})
    if not data:
        return []
    chunks = data.get("chunks", [])
    if not chunks:
        chunks = data if isinstance(data, list) else []
    return chunks


def _cache_path(dimension, query):
    raw = f"{dimension}||{query}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return RAG_CACHE_DIR / f"{dimension}_{h}.json"


def _read_cache(cache_path):
    if not cache_path.exists():
        return None
    age = time.time() - cache_path.stat().st_mtime
    if age > CACHE_TTL_SECONDS:
        cache_path.unlink(missing_ok=True)
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_cache(cache_path, chunks):
    RAG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


class RagflowClient:
    """RAGFlow API 客户端。"""

    def __init__(self, base_url=RAGFLOW_API_URL, api_key=RAGFLOW_API_KEY, dataset_ids=None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.dataset_ids = dataset_ids or ALL_DATASETS

    def search(self, query, top_k=TOP_K, threshold=SIMILARITY_THRESHOLD, use_cache=True):
        """检索 RAGFlow 向量知识库。"""
        if use_cache:
            for dim_name, queries in DIMENSION_QUERIES.items():
                if query in queries:
                    cp = _cache_path(dim_name, query)
                    cached = _read_cache(cp)
                    if cached is not None:
                        return cached
                    break

        body = {
            "question": query,
            "dataset_ids": self.dataset_ids,
            "top_k": top_k,
            "similarity_threshold": threshold,
        }

        try:
            payload = _request_json(
                f"{self.base_url}/api/v1/retrieval",
                self.api_key,
                method="POST",
                body=json.dumps(body).encode("utf-8"),
            )
            payload = _ensure_success(payload)
            chunks = _extract_chunks(payload)
        except Exception as exc:
            logger.warning("RAGFlow search failed: %s", exc)
            return []

        if use_cache:
            for dim_name, queries in DIMENSION_QUERIES.items():
                if query in queries:
                    _write_cache(_cache_path(dim_name, query), chunks)
                    break

        return chunks

    def search_by_dimension(self, dimension, top_k=TOP_K):
        """对单个领导力维度执行多 query 检索，合并去重后返回。"""
        queries = DIMENSION_QUERIES.get(dimension, [dimension])
        seen = set()
        all_chunks = []

        for query in queries:
            chunks = self.search(query, top_k=top_k)
            for chunk in chunks:
                cid = chunk.get("chunk_id", "")
                if cid and cid not in seen:
                    seen.add(cid)
                    all_chunks.append(chunk)

        all_chunks.sort(key=lambda c: c.get("similarity", 0) or 0, reverse=True)
        return all_chunks[:top_k]


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = RagflowClient()
    return _client


def search_by_dimension(dimension, top_k=3):
    client = _get_client()
    return client.search_by_dimension(dimension, top_k=top_k)


def search_development_feedback(dimension, user_context=None, top_k=3):
    """为某个领导力维度获取发展性反馈。"""
    client = _get_client()

    try:
        chunks = client.search_by_dimension(dimension, top_k=top_k)
    except Exception as exc:
        logger.warning("RAG retrieval failed for %s: %s", dimension, exc)
        chunks = []

    quotes = []
    for c in chunks:
        doc_name = c.get("document_name", "")
        content = c.get("content", "")
        content = " ".join(content.split())
        if len(content) > 600:
            content = content[:597] + "..."
        if content:
            quotes.append({
                "source": doc_name,
                "content": content,
                "similarity": round(c.get("similarity", 0) or 0, 4),
            })

    fallback_used = len(quotes) == 0

    if fallback_used:
        advice_text = FALLBACK_ADVICE.get(dimension, "")
    else:
        parts = []
        for q in quotes:
            src = q["source"]
            if "Successful Managers Handbook" in src or "Handboook" in src:
                src_short = "《Successful Manager's Handbook》"
            elif "FYI" in src:
                src_short = "《FYI for Your Improvement》"
            else:
                src_short = src
            parts.append(f"【{src_short}】{q['content']}")
        advice_text = "\n\n".join(parts)

    return {
        "dimension": dimension,
        "quotes": quotes,
        "advice_text": advice_text,
        "fallback_used": fallback_used,
    }


def generate_development_section(development_dims, top_k=3):
    """为多个待发展维度批量生成发展建议章节。"""
    results = []
    for dim in development_dims:
        feedback = search_development_feedback(dim, top_k=top_k)
        results.append(feedback)
    return results


def clear_cache(dimension=None):
    count = 0
    for f in RAG_CACHE_DIR.glob("*.json"):
        if dimension is None or f.name.startswith(dimension):
            f.unlink()
            count += 1
    return count
