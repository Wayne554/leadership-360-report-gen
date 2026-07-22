"""
Phase 3: 代表性评语选取（关键词密度法）。

对每个开放编码（子编码），从该人全部评语中，
按关键词密度排序，选取 Top 2-3 条最能代表该编码的评语原文。

选取规则：
  1. 对一段评语，计算该编码下的关键词命中密度（命中词数 / 总词数）
  2. 优先按命中词数 ≥ 2 筛选，再按密度降序排列
  3. 选取 Top N 条
  4. 评语原文 1:1 取自原始数据，不做任何修改

输出: data/processed/comments/{person_id}_keywords.json（追加 selection 字段）
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.comments.config import COMMENT_CACHE_DIR, COMMENT_COL_NAMES, KEYWORD_DICT

logger = logging.getLogger(__name__)


# ── 分词辅助 ──────────────────────────────────────────────────
_TOKEN_SPLIT = re.compile(r"[\s，。、；：？\!\.\,\;\:\?\(\)（）【】《》\"\'/\\\-\+\=\d]+")


def _tokenize(text: str) -> list[str]:
    """简单分词（按标点+空格切分），返回非空词元。"""
    tokens = [t.strip() for t in _TOKEN_SPLIT.split(text) if t.strip()]
    return tokens if tokens else [text]


def keyword_density(text: str, triggers: list[str]) -> tuple[int, float]:
    """计算一段文本在某组关键词下的命中密度。

    Returns:
        (hit_count, density) — hit_count = 命中的关键词种数（不重复计数）
    """
    tokens = _tokenize(text)
    total_words = len(tokens) if tokens else 1

    # 统计命中
    hit_count = 0
    for trigger in triggers:
        if trigger in text:
            hit_count += 1

    density = hit_count / total_words if total_words > 0 else 0.0
    return hit_count, density


def _get_triggers_for_code(axial: str, sub_code: str) -> list[str]:
    """获取某个开放编码下的所有触发词。"""
    sub_dict = KEYWORD_DICT.get(axial, {})
    return sub_dict.get(sub_code, [])


def _get_all_triggers_for_axial(axial: str) -> list[str]:
    """获取某个主轴编码下的所有触发词。"""
    sub_dict = KEYWORD_DICT.get(axial, {})
    triggers: list[str] = []
    for keywords in sub_dict.values():
        triggers.extend(keywords)
    return triggers


# ── 选取代表性评语 ─────────────────────────────────────────────

def select_representative_quotes(
    axial: str,
    sub_code: str,
    all_texts: list[str],
    top_n: int = 2,
) -> list[dict]:
    """为某个(轴向, 子编码)选取最具代表性的评语。

    Args:
        axial: 主轴编码名称
        sub_code: 开放编码名称
        all_texts: 该人该类型下的全部评语原文列表
        top_n: 选取条数

    Returns:
        [{"text": "...", "hit_count": 3, "density": 0.15}, ...]
    """
    triggers = _get_triggers_for_code(axial, sub_code)
    if not triggers:
        return []

    scored: list[tuple[int, float, str]] = []  # (hit_count, density, text)
    for text in all_texts:
        hit_count, density = keyword_density(text, triggers)
        if hit_count > 0:
            scored.append((hit_count, density, text))

    if not scored:
        return []

    # 排序：先按命中词数降序（至少 ≥ 2 优先），再按密度降序
    scored.sort(key=lambda x: (-x[0], -x[1], len(x[2])))

    result: list[dict] = []
    for hit_count, density, text in scored[:top_n]:
        result.append({
            "text": text,
            "hit_count": hit_count,
            "density": round(density, 4),
        })
    return result


# ── 全量处理接口 ──────────────────────────────────────────────

def run_selection(
    person_id: str,
    input_dir: str | Path | None = None,
) -> dict[str, Any]:
    """对一个人执行全量代表性评语选取。

    读取 _keywords.json → 追加 selection 字段 → 写回
    """
    if input_dir is None:
        input_dir = Path(COMMENT_CACHE_DIR)
    else:
        input_dir = Path(input_dir)

    kw_path = input_dir / f"{person_id}_keywords.json"
    if not kw_path.exists():
        raise FileNotFoundError(f"关键词数据不存在: {kw_path}")

    with open(kw_path, "r", encoding="utf-8") as f:
        kw_data = json.load(f)

    # 读取原始预处理数据（有评语原文）
    raw_path = input_dir / f"{person_id}.json"
    with open(raw_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # 构建评语原文索引：{ comment_type: [text, text, ...] }
    all_texts: dict[str, list[str]] = {}
    for ct in COMMENT_COL_NAMES:
        texts: list[str] = []
        for source, entries in raw_data.get(ct, {}).items():
            for entry in entries:
                if entry.get("text", "").strip():
                    texts.append(entry["text"])
        all_texts[ct] = texts

    # 对每个类型 × 轴向 × 子编码 做选取
    selection_result: dict[str, Any] = {}
    for ct in ["优势评语", "发展建议"]:
        ct_data = kw_data.get(ct, {})
        if not ct_data:
            continue

        ct_selection: dict[str, Any] = {}
        for axial, axial_data in ct_data.items():
            open_codes = axial_data.get("open_codes", {})
            if not open_codes:
                continue

            axial_selection: dict[str, Any] = {}
            for sc_name in open_codes:
                quotes = select_representative_quotes(
                    axial, sc_name, all_texts.get(ct, [])
                )
                if quotes:
                    axial_selection[sc_name] = {
                        "quotes": [q["text"] for q in quotes],
                        "hit_count": quotes[0]["hit_count"],
                        "max_density": max(q["density"] for q in quotes),
                    }
            if axial_selection:
                ct_selection[axial] = axial_selection

        if ct_selection:
            selection_result[ct] = ct_selection

    # 写入 _keywords.json（追加 selection 字段）
    kw_data["selection"] = selection_result
    with open(kw_path, "w", encoding="utf-8") as f:
        json.dump(kw_data, f, ensure_ascii=False, indent=2)

    return selection_result


def run_selection_all(
    level: str = "L4",
    input_dir: str | Path | None = None,
    max_persons: int | None = None,
) -> int:
    """全量运行代表性评语选取。"""
    if input_dir is None:
        input_dir = Path(COMMENT_CACHE_DIR)
    else:
        input_dir = Path(input_dir)

    kw_files = sorted(input_dir.glob("*_keywords.json"))
    if max_persons:
        kw_files = kw_files[:max_persons]

    processed = 0
    for kw_path in kw_files:
        pid = kw_path.stem.replace("_keywords", "")
        try:
            run_selection(pid, input_dir)
            processed += 1
        except Exception as e:
            logger.warning("Selection failed for %s: %s", pid, e)

    logger.info("Selection done: %d files", processed)
    return processed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    run_selection_all(level="L4", max_persons=3)
    print("Done")
    # 验证
    import json
    d = json.load(open("data/processed/comments/10000062_keywords.json", "r", encoding="utf-8"))
    for ct in ["优势评语", "发展建议"]:
        selections = d.get("selection", {}).get(ct, {})
        if selections:
            print("\n=== %s ===" % ct)
            for axial, sc_data in sorted(selections.items()):
                print("  %s:" % axial)
                for sc, sq in sorted(sc_data.items()):
                    quote_text = sq["quotes"][0][:60] if sq["quotes"] else "(none)"
                    print("    %s: %s..." % (sc, quote_text))
