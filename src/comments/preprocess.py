"""
Phase 1: 评语数据准备。

从原始 _rev.csv 出发，按被评人分组，恢复每个评价人的评语原文与来源归属，
剔除自评、过滤噪声，输出每人一份结构化 JSON。

输出: data/processed/comments/{person_id}.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from src.comments.config import (
    COMMENT_CACHE_DIR,
    COMMENT_COL_NAMES,
    RAW_LEVEL_CONFIGS,
    REL_MAP,
    RATER_SOURCES_TO_KEEP,
    is_noise,
)

logger = logging.getLogger(__name__)


# ── 读原始数据 ──────────────────────────────────────────────────

def load_raw_data(level: str = "L4") -> tuple[pd.DataFrame, str, str]:
    """加载指定层级的原始评语数据。
    
    Returns:
        (df, rater_id_col_name, user_id_col_name)
    """
    cfg = RAW_LEVEL_CONFIGS[level]
    path = Path(cfg["file"])
    df = pd.read_csv(path, encoding="utf-8-sig")

    # 标准化关系列
    rel_col = df.columns[cfg["rel_col"]]
    df["_关系"] = df[rel_col].map(REL_MAP)

    # 剔除自评
    df = df[df["_关系"].isin(RATER_SOURCES_TO_KEEP)].copy()

    # 取评语列并重命名
    c_start, c_end = cfg["comment_cols"]
    comment_columns = list(df.columns[c_start:c_end])
    rename_map = dict(zip(comment_columns, COMMENT_COL_NAMES))
    df.rename(columns=rename_map, inplace=True)

    rater_id_col = df.columns[cfg["rater_id_col"]]
    user_id_col = df.columns[0]  # 被评人工号

    return df, rater_id_col, user_id_col


# ── 单被评人预处理 ──────────────────────────────────────────────

def preprocess_one_person(
    person_df: pd.DataFrame,
    rater_id_col: str,
    person_id: str,
    level: str = "",
) -> dict:
    """将一个人的多行评语数据转化为结构化字典。"""
    result = {
        "person_id": person_id,
        "level": level,
        "优势评语": {},
        "发展建议": {},
        "其他建议": {},
        "stats": {},
    }

    for comment_type in COMMENT_COL_NAMES:
        type_data: dict[str, list[dict]] = {}

        for _, row in person_df.iterrows():
            raw_text = row.get(comment_type, "")
            if not isinstance(raw_text, str) or not raw_text.strip():
                continue
            raw_text = raw_text.strip()

            if is_noise(raw_text):
                continue

            source = str(row.get("_关系", ""))
            rater_id = str(row.get(rater_id_col, ""))

            if source not in type_data:
                type_data[source] = []
            type_data[source].append({
                "rater_id": rater_id,
                "text": raw_text,
            })

        result[comment_type] = type_data

    # 统计
    # Count unique raters from ALL rating data (not just comment writers)
    all_rater_ids: set[str] = set()
    all_raters_by_source: dict[str, set[str]] = {}
    total_entries = 0
    # Count from the raw person_df first (captures ALL raters, including score-only)
    for _, _row in person_df.iterrows():
        _src = str(_row.get("_\u5173\u7cfb", ""))
        _rid = str(_row.get(rater_id_col, ""))
        if _src not in all_raters_by_source:
            all_raters_by_source[_src] = set()
        all_raters_by_source[_src].add(_rid)
        all_rater_ids.add(_rid)
    # Count entries from structured comment data
    for ctype in COMMENT_COL_NAMES:
        for src, entries in result[ctype].items():
            total_entries += len(entries)
    source_counts = {src: len(ids) for src, ids in all_raters_by_source.items()}

    result["stats"] = {
        "有效评价人数": len(all_rater_ids),
        "来源分布": dict(sorted(source_counts.items())),
        "评语总条数": total_entries,
    }

    return result


# ── 全量处理 ────────────────────────────────────────────────────

def run_preprocess(
    level: str = "L4",
    output_dir: str | Path | None = None,
    max_persons: int | None = None,
) -> Path:
    """全量运行 Phase 1 预处理。"""
    if output_dir is None:
        output_dir = Path(COMMENT_CACHE_DIR)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df, rater_id_col, user_id_col = load_raw_data(level)

    all_persons = sorted(df[user_id_col].unique())
    if max_persons:
        all_persons = all_persons[:max_persons]

    processed = 0
    skipped = 0
    for pid in all_persons:
        pid_str = str(pid)
        out_path = output_dir / f"{pid_str}.json"
        if out_path.exists():
            skipped += 1
            continue

        person_df = df[df[user_id_col] == pid]
        result = preprocess_one_person(
            person_df, rater_id_col, pid_str, level=level
        )

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        processed += 1

    logger.info(
        "Preprocess %s done: total=%d, new=%d, cached=%d",
        level, len(all_persons), processed, skipped,
    )
    return Path(output_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_preprocess(level="L4", max_persons=3)
