"""Development suggestions module.

Pipeline position: Phase C --- get_development_section()
  - Reads pre-written actions from dev_config.json (always)
  - Reads RAGFlow+LLM generated suggestions from rag_cache (if available)
  - Auto-generates from rag_context if suggestions not pre-computed
  - Hybrid merge: pre-written actions + RAGFlow insight + SMH quote
"""
from __future__ import annotations
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DISTANCE_PATH = PROJECT_ROOT / "data" / "processed" / "dimension_distances.json"
CONFIG_PATH = Path(__file__).parent / "dev_config.json"
SUGGESTIONS_DIR = PROJECT_ROOT / "data" / "processed" / "rag_cache"

_config_cache = None
_distances_cache = None


def _load_config():
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _config_cache = json.load(f)
    return _config_cache


def _load_distances():
    global _distances_cache
    if _distances_cache is None:
        with open(DISTANCE_PATH, encoding="utf-8") as f:
            _distances_cache = json.load(f)
    return _distances_cache


def _load_rag_suggestions(person_id: str) -> dict | None:
    """Load pre-computed suggestions, or generate via DeepSeek LLM, or fall back to rule-based."""
    path = SUGGESTIONS_DIR / f"rag_suggestions_{person_id}.json"
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("method") in ("deepseek_llm",):
                return data
        except Exception:
            pass
    # Try DeepSeek LLM synthesis
    try:
        from src.rag.llm_synthesizer import synthesize_suggestions
        result = synthesize_suggestions(person_id)
        if result:
            return result
    except Exception:
        pass
    # Fall back to rule-based from rag_context
    return _auto_generate_from_context(person_id)


def _auto_generate_from_context(person_id: str) -> dict | None:
    """Generate inline dimension insights from saved rag_context.
    Auto-triggers context preparation if rag_context not yet prepared.
    """
    ctx_path = SUGGESTIONS_DIR / f"rag_context_{person_id}.json"
    if not ctx_path.exists():
        try:
            from src.rag.rag_engine import prepare_context, save_context
            context = prepare_context(person_id)
            if context.get("dimensions"):
                save_context(context)
                ctx_path = SUGGESTIONS_DIR / f"rag_context_{person_id}.json"
        except Exception:
            return None
    if not ctx_path.exists():
        return None
    try:
        with open(ctx_path, encoding="utf-8") as f:
            context = json.load(f)
    except Exception:
        return None
    dims = context.get("dimensions", {})
    if not dims:
        return None
    result = {"dimensions": {}, "mode": "auto_context"}
    for dim_name, dim_data in dims.items():
        chunks = dim_data.get("chunks", [])
        if not chunks:
            continue
        top = chunks[0]
        top_content = top.get("content", "")
        top_source = top.get("source", "unknown")
        insight = f"\u6839\u636e\u300a{top_source}\u300b\u4e2d\u7684\u76f8\u5173\u5185\u5bb9\uff1a{top_content[:200]}"
        quote = ""
        if len(chunks) > 1:
            sec = chunks[1]
            sec_source = sec.get("source", "unknown")
            quote = f"\u2014\u2014\u300a{sec_source}\u300b"
        result["dimensions"][dim_name] = {"insight": insight, "quote": quote}
    return result if result["dimensions"] else None



def _sanitize_quote(quote: str) -> str:
    """Clean DeepSeek quotes: remove leading separators, drop empty/source-only quotes."""
    if not quote:
        return ""
    cleaned = re.sub(r'^[\s*—\-–=]+', '', quote).strip()
    if not cleaned:
        return ""
    # Drop if just a source attribution (Chinese brackets, source prefix)
    source_only = ["《", "（", "(", "来源", "Successful"]
    for s in source_only:
        if cleaned.startswith(s):
            return ""
    # Drop book/document title patterns (no actual quote content)
    title_pats = [
        r'^The\s+\w+\s+(Handbook|Guide|Leadership|Management|Development)',
        r'^[A-Z][a-z]+_[A-Z]',
        r'^Leadership_'
    ]
    for pat in title_pats:
        if re.match(pat, cleaned):
            return ""
    return cleaned



def get_person_distance_data(person_id):
    data = _load_distances()
    return data.get("persons", {}).get(person_id)


def get_priority_dimensions(person_id):
    pdata = get_person_distance_data(person_id)
    if pdata is None:
        return []
    return pdata.get("bottom3_keys", [])


def get_preamble(person_id):
    cfg = _load_config()
    pdata = get_person_distance_data(person_id)
    if pdata is None:
        return ""
    v = pdata.get("preamble_variant", "standard")
    return cfg.get("preamble_variants", {}).get(v, "")


def get_actions(dim_name):
    cfg = _load_config()
    return cfg.get("dev_actions", {}).get(dim_name, [])


def get_development_section(person_id):
    """Hybrid: pre-written actions + RAGFlow insights if available."""
    pdata = get_person_distance_data(person_id)
    if pdata is None:
        return {"preamble": "", "dimensions": [], "mode": "empty"}

    b3 = pdata.get("bottom3_keys", [])
    cfg = _load_config()
    excluded = cfg.get("excluded_dims", ["\u6570\u667a\u53d8\u9769"])

    rag_suggestions = _load_rag_suggestions(person_id)
    mode = "hybrid" if rag_suggestions else "static"

    dims = []
    for key in b3:
        if any(ex in key for ex in excluded):
            continue
        dim_entry = {"name": key, "actions": get_actions(key)}
        if rag_suggestions:
            dim_rag = rag_suggestions.get("dimensions", {}).get(key, {})
            if dim_rag:
                dim_entry["insight"] = dim_rag.get("insight", "")
                # Phase 0.4: prefer LLM-generated actions over pre-written
                if "actions" in dim_rag:
                    dim_entry["actions"] = dim_rag["actions"]
                dim_entry["quote"] = _sanitize_quote(dim_rag.get("quote", ""))
                dim_entry["is_hybrid"] = True
            else:
                dim_entry["is_hybrid"] = False
        else:
            dim_entry["is_hybrid"] = False
        dims.append(dim_entry)

    return {"preamble": get_preamble(person_id), "dimensions": dims, "mode": mode}
