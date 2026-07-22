"""
Phase 2: 开放编码 + 关键词提取。

核心逻辑：
  1. 对每段评语，按 KEYWORD_DICT 中的触发词做子串匹配（最长优先）
  2. 同一关键词在一段评语中重复出现仅计 1 次
  3. 同一关键词被同一评价人在同类型下多次提及仅计 1 次（rater_id 去重）
  4. 统计每个开放编码的频次、评价人数、来源分布
  5. 统计每个主轴编码（6个视角）的聚合频次

输出: data/processed/comments/{person_id}_keywords.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from src.comments.config import (
    COMMENT_CACHE_DIR,
    COMMENT_COL_NAMES,
    KEYWORD_DICT,
    get_all_triggers,
    resolve_axial,
    is_noise,
)

logger = logging.getLogger(__name__)


# ── 关键词匹配核心 ──────────────────────────────────────────────

# 全局预编译：触发词按长度降序排列，长词优先匹配
_ALL_TRIGGERS: list[str] = get_all_triggers()


def match_keywords(text: str) -> dict[str, str]:
    """在单段文本中匹配所有触发词，返回 {trigger: axial_category}。
    
    策略：对每个轴向类别内的子编码，扫描文本中是否包含任意触发词。
    采用触发词列表统一扫描（已按长度降序排列），第一次匹配优先。
    """
    result: dict[str, str] = {}
    for trigger in _ALL_TRIGGERS:
        if trigger in text:
            # 如果已被同轴向的更长的词覆盖，跳过
            # 例如 "沟通能力" 已匹配过 → "沟通" 不再重复计入
            already_covered = False
            for matched_trigger in result:
                if trigger in matched_trigger:
                    already_covered = True
                    break
            if not already_covered:
                # 反查 axial + sub_code
                for axial, sub_dict in KEYWORD_DICT.items():
                    for sc_name, keywords in sub_dict.items():
                        if trigger in keywords:
                            result[trigger] = axial
                            break
                    if trigger in result:
                        break
    return result


# ── 频次统计 ────────────────────────────────────────────────────

def count_keywords_for_person(
    person_data: dict,
) -> dict[str, Any]:
    """对一个人的评语做完整的关键词统计。

    Returns:
        {
            "person_id": "...",
            "优势评语": {
                "工作投入&态度": {
                    "count": 9,          # 同一 trigger 去重后的命中总数
                    "persons": 5,         # 不同 rater_id 数
                    "source_dist": {"下级": 3, "协同方": 2},
                    "open_codes": {       # 子编码粒度
                        "执行力": {"count": 4, "persons": 3, "rater_ids": [...]},
                        ...
                    }
                },
                ...
            },
            "发展建议": { ... },
        }
    """
    result: dict[str, Any] = {
        "person_id": person_data.get("person_id", ""),
        "level": person_data.get("level", ""),
    }

    # 初始化轴向数据结构
    axial_structure: dict[str, dict] = {}
    for axial, sub_dict in KEYWORD_DICT.items():
        axial_structure[axial] = {
            "count": 0,
            "persons": 0,
            "source_dist": {},
            "open_codes": {},
        }
        for sc_name in sub_dict:
            axial_structure[axial]["open_codes"][sc_name] = {
                "count": 0, "persons": 0, "rater_ids": [],
            }

    for comment_type in ["优势评语", "发展建议"]:
        type_data = person_data.get(comment_type, {})
        if not type_data:
            result[comment_type] = {}
            continue

        # 复制轴向结构
        axial_counts: dict[str, dict] = {
            k: {
                "count": 0, "persons": 0,
                "source_dist": {},
                "axial_rater_ids": set(),
                "open_codes": {
                    sc: {"count": 0, "rater_ids": set()}
                    for sc in KEYWORD_DICT[k]
                },
            }
            for k in KEYWORD_DICT
        }

        for source, entries in type_data.items():
            for entry in entries:
                rater_id = entry.get("rater_id", "")
                text = entry.get("text", "")

                if is_noise(text):
                    continue

                matches = match_keywords(text)
                if not matches:
                    continue

                # 按轴向分组，记录 rater_id 去重
                for trigger, axial in matches.items():
                    if axial not in axial_counts:
                        continue

                    # 找到具体的开放编码
                    sc_name = None
                    for scn, keywords in KEYWORD_DICT[axial].items():
                        if trigger in keywords:
                            sc_name = scn
                            break
                    if sc_name is None:
                        continue

                    # 轴向级：rater 去重
                    if rater_id not in axial_counts[axial]["axial_rater_ids"]:
                        axial_counts[axial]["axial_rater_ids"].add(rater_id)
                        axial_counts[axial]["count"] += 1

                    # 来源分布：rater 去重
                    if rater_id not in axial_counts[axial]["source_dist"].get(source, set()):
                        axial_counts[axial]["source_dist"].setdefault(source, set()).add(rater_id)

                    # 开放编码级：rater 去重
                    oc = axial_counts[axial]["open_codes"][sc_name]
                    if rater_id not in oc["rater_ids"]:
                        oc["rater_ids"].add(rater_id)
                        oc["count"] += 1

        # 转换为可序列化格式
        serialized: dict[str, Any] = {}
        for axial, data in sorted(axial_counts.items()):
            if data["count"] == 0:
                continue
            oc_serialized: dict[str, Any] = {}
            for sc_name, sc_data in sorted(data["open_codes"].items()):
                if sc_data["count"] > 0:
                    oc_serialized[sc_name] = {
                        "count": sc_data["count"],
                        "persons": len(sc_data["rater_ids"]),
                    }
            serialized[axial] = {
                "count": data["count"],
                "persons": len(data["axial_rater_ids"]),
                "source_dist": {
                    src: len(rids) for src, rids in sorted(data["source_dist"].items())
                },
                "open_codes": oc_serialized,
            }
        result[comment_type] = serialized

    # 简单统计
    total_hits = sum(
        v.get("count", 0) for ct in ["优势评语", "发展建议"]
        for v in result.get(ct, {}).values()
    )
    result["stats"] = {"总关键词命中数": total_hits}

    return result


# ── 文件级接口 ──────────────────────────────────────────────────

def extract_keywords_file(
    person_id: str,
    input_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """读取单人的预处理 JSON，做关键词提取，输出到文件。
    
    Returns:
        关键词统计结果 dict
    """
    if input_dir is None:
        input_dir = Path(COMMENT_CACHE_DIR)
    else:
        input_dir = Path(input_dir)
    if output_dir is None:
        output_dir = Path(COMMENT_CACHE_DIR)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    in_path = input_dir / f"{person_id}.json"
    if not in_path.exists():
        raise FileNotFoundError(f"预处理数据不存在: {in_path}")

    with open(in_path, "r", encoding="utf-8") as f:
        person_data = json.load(f)

    kw_result = count_keywords_for_person(person_data)

    out_path = output_dir / f"{person_id}_keywords.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(kw_result, f, ensure_ascii=False, indent=2)

    return kw_result


def extract_keywords_all(
    level: str = "L4",
    input_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    max_persons: int | None = None,
) -> int:
    """全量做关键词提取。"""
    if input_dir is None:
        input_dir = Path(COMMENT_CACHE_DIR)
    else:
        input_dir = Path(input_dir)
    if output_dir is None:
        output_dir = Path(COMMENT_CACHE_DIR)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(input_dir.glob("[0-9]*.json"))
    # 排除 _keywords.json 等带后缀的
    json_files = [f for f in json_files if "_" not in f.stem]

    if max_persons:
        json_files = json_files[:max_persons]

    processed = 0
    for in_path in json_files:
        pid = in_path.stem
        out_path = output_dir / f"{pid}_keywords.json"
        if out_path.exists():
            continue
        try:
            extract_keywords_file(pid, input_dir, output_dir)
            processed += 1
        except Exception as e:
            logger.warning("Keywords extraction failed for %s: %s", pid, e)

    logger.info("Keywords extraction done: %d files", processed)
    return processed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    extract_keywords_all(level="L4", max_persons=3)
    print("Done")
    # 打印一个示例
    import json
    pid = "10000062"
    with open(f"data/processed/comments/{pid}_keywords.json", "r") as f:
        d = json.load(f)
    for ct in ["优势评语", "发展建议"]:
        print(f"\n=== {ct} ===")
        for axial, data in sorted(d.get(ct, {}).items()):
            print(f"  {axial}: count={data['count']}, persons={data['persons']}")
            for sc, sc_data in sorted(data['open_codes'].items()):
                print(f"    - {sc}: {sc_data['count']}")
    print("Stat:", d["stats"]["总关键词命中数"])
