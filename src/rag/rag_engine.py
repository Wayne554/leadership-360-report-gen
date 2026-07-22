# -*- coding: utf-8 -*-
"""RAGFlow context preparation engine.

Phase A of the report pipeline:
  -> Load person evaluation data and comment profile
  -> Search RAGFlow for bottom-3 dimension chunks
  -> Save context JSON for Codex to generate suggestions
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

from src.rag.config import DIMENSION_QUERIES, RAG_CACHE_DIR
from src.rag.retriever import RagflowClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DISTANCE_PATH = PROJECT_ROOT / "data" / "processed" / "dimension_distances.json"
COMMENT_DIR = PROJECT_ROOT / "data" / "processed" / "comments"

logger = logging.getLogger(__name__)


def load_person_eval(person_id: str) -> dict:
    """Load evaluation data: bottom-3, quadrants, distances."""
    with open(DISTANCE_PATH, "r", encoding="utf-8") as f:
        dist_data = json.load(f)

    pdata = dist_data.get("persons", {}).get(person_id)
    if pdata is None:
        raise ValueError(f"Person {person_id} not found")

    return {
        "bottom3_keys": pdata.get("bottom3_keys", []),
        "quadrant": pdata.get("preamble_variant", "standard"),
        "dims": pdata.get("dimensions", []),
        "excluded": dist_data.get("config", {}).get("exclude_dims", ["数智变革"]),
    }


def load_comment_profile(person_id: str) -> dict:
    """Load encoded comment profile for the person."""
    path = COMMENT_DIR / f"{person_id}_encoded.json"
    if not path.exists():
        return {"profile": "", "top_strengths": [], "development_areas": []}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "profile": data.get("profile", ""),
        "top_strengths": [
            a.get("name", "") for a in (data.get("top_axial", []) or [])[:3]
        ],
        "development_areas": [
            a.get("name", "") for a in (data.get("development_axial", []) or [])[:2]
        ],
    }


def search_dimension_chunks(client: RagflowClient, dimension: str, top_k: int = 3) -> list[dict]:
    """Multi-query search for one dimension, deduplicated."""
    queries = DIMENSION_QUERIES.get(dimension, [dimension])
    seen: set[str] = set()
    all_chunks: list[dict] = []

    for query in queries:
        try:
            chunks = client.search(query, top_k=top_k, use_cache=True)
        except Exception:
            chunks = []
        for c in chunks:
            cid = c.get("id", "") or c.get("chunk_id", "")
            if cid and cid not in seen:
                seen.add(cid)
                all_chunks.append(c)

    all_chunks.sort(key=lambda x: x.get("similarity", 0) or 0, reverse=True)
    return all_chunks[:top_k]


def prepare_context(person_id: str, level: str = "L4", top_k: int = 3) -> dict:
    """Phase A: build RAGFlow context for a single person."""
    context: dict = {
        "person_id": person_id,
        "level": level,
        "dimensions": {},
        "comment_profile": {},
    }

    # Step 1: evaluation data
    try:
        eval_data = load_person_eval(person_id)
        context["excluded_dims"] = eval_data["excluded"]
        context["bottom3_keys"] = eval_data["bottom3_keys"]
        context["preamble_variant"] = eval_data.get("quadrant", "standard")
        context["dim_data"] = eval_data["dims"]
    except Exception as e:
        logger.warning("Cannot load eval data: %s", e)
        return context

    # Step 2: comment profile
    context["comment_profile"] = load_comment_profile(person_id)

    # Step 3: RAGFlow search for each bottom-3 dimension
    try:
        client = RagflowClient()
        for dim_key in eval_data["bottom3_keys"]:
            if dim_key in eval_data["excluded"]:
                continue
            chunks = search_dimension_chunks(client, dim_key, top_k)
            context["dimensions"][dim_key] = {
                "chunks": [
                    {
                        "content": c.get("content", ""),
                        "similarity": c.get("similarity", 0),
                        "source": c.get("document_keyword", "unknown"),
                    }
                    for c in chunks
                ]
            }
    except Exception as e:
        logger.warning("RAGFlow search failed: %s", e)

    return context


def save_context(context: dict) -> Path:
    """Save context JSON to rag_cache."""
    RAG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = RAG_CACHE_DIR / f"rag_context_{context['person_id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(context, f, ensure_ascii=False, indent=2)
    return path


def load_context(person_id: str) -> dict | None:
    """Load previously saved context JSON."""
    path = RAG_CACHE_DIR / f"rag_context_{person_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
