"""群体画像分析：派生数据生成脚本。
读取宽表 + keywords.json + dimension_distances.json -> 输出群体级聚合数据 JSON。

输出: output/group_profiling_data.json
"""
from __future__ import annotations
import json
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

PROJ = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJ / "data" / "processed"
COMMENTS_DIR = DATA_DIR / "comments"
OUTPUT_DIR = PROJ / "output"

DIM_NAMES = [
    "战略思维-科学决策", "创新引领-持续精进", "全球视野-管理复杂情况",
    "客户导向-珍视客户", "数智变革-加强数字应用", "发展组织-带兵打仗", "追求卓越-高效执行",
]
SOURCES = ["本人", "上级", "协同方", "下级", "他评"]
COMMENT_TYPES = ["优势评语", "发展建议"]

logging.basicConfig(level=logging.INFO, format="%(message)s")

def main():
    logging.info("Loading wide data...")
    l3_df = pd.read_csv(DATA_DIR / "leadership_feedback_level3_wide.csv", encoding="utf-8-sig")
    l4_df = pd.read_csv(DATA_DIR / "leadership_feedback_level4_wide.csv", encoding="utf-8-sig")

    # Assign groups
    l4_df = l4_df.copy()
    l4_promo = pd.to_datetime(l4_df["上一次晋升时间"], errors="coerce")
    l4_df["group"] = "L4_非新晋"
    l4_df.loc[l4_promo.dt.year >= 2025, "group"] = "L4_新晋"
    l3_df = l3_df.copy()
    l3_df["group"] = "L3"
    all_df = pd.concat([l3_df, l4_df], ignore_index=True)
    uid_col = all_df.columns[0]

    groups = ["L3", "L4_新晋", "L4_非新晋"]
    result = {g: {"n": int((all_df["group"] == g).sum())} for g in groups}

    # 1. Rating Statistics
    logging.info("Aggregating rating statistics...")
    for g in groups:
        mask = all_df["group"] == g
        gdf = all_df[mask]
        result[g]["rating"] = {}
        for dim in DIM_NAMES:
            result[g]["rating"][dim] = {}
            for src in SOURCES:
                col = f"{src}-{dim}"
                vals = pd.to_numeric(gdf[col], errors="coerce").dropna()
                if len(vals) == 0:
                    continue
                result[g]["rating"][dim][src] = {
                    "mean": round(float(vals.mean()), 3),
                    "median": round(float(vals.median()), 3),
                    "p25": round(float(vals.quantile(0.25)), 3),
                    "p75": round(float(vals.quantile(0.75)), 3),
                    "n": int(len(vals)),
                }

    # 2. Self-Other Gap Matrix
    logging.info("Computing gap matrices...")
    for g in groups:
        mask = all_df["group"] == g
        gdf = all_df[mask]
        result[g]["gaps"] = {}
        for dim in DIM_NAMES:
            self_col = f"本人-{dim}"
            result[g]["gaps"][dim] = {}
            for src in ["上级", "协同方", "下级", "他评"]:
                src_col = f"{src}-{dim}"
                diff = pd.to_numeric(gdf[src_col], errors="coerce") - pd.to_numeric(gdf[self_col], errors="coerce")
                vals = diff.dropna()
                if len(vals) == 0:
                    continue
                result[g]["gaps"][dim][src] = {
                    "mean": round(float(vals.mean()), 3),
                    "median": round(float(vals.median()), 3),
                    "n": int(len(vals)),
                }

    # 3. Johari Quadrant Distribution
    logging.info("Computing Johari quadrant distribution...")
    dist_path = DATA_DIR / "dimension_distances.json"
    dist_data = json.loads(dist_path.read_text(encoding="utf-8"))
    persons_data = dist_data.get("persons", {})

    for g in groups:
        result[g]["johari"] = {}
        for dim in DIM_NAMES:
            result[g]["johari"][dim] = {"优势区": 0, "潜能区": 0, "盲区": 0, "待发展区": 0}
        n_group = 0
        for idx in range(len(all_df)):
            uid = str(all_df.iloc[idx][uid_col])
            g_label = all_df.iloc[idx]["group"]
            if g_label != g:
                continue
            pdata = persons_data.get(uid)
            if pdata is None:
                continue
            dims_data = pdata.get("dimensions", {})
            if not dims_data:
                continue
            n_group += 1
            for dim in DIM_NAMES:
                dd = dims_data.get(dim)
                if dd:
                    q = dd.get("quadrant", "")
                    if q in result[g]["johari"][dim]:
                        result[g]["johari"][dim][q] += 1
        if n_group > 0:
            for dim in DIM_NAMES:
                for q in result[g]["johari"][dim]:
                    result[g]["johari"][dim][q] = {
                        "count": result[g]["johari"][dim][q],
                        "pct": round(result[g]["johari"][dim][q] / n_group, 4),
                    }
        result[g]["johari_n"] = n_group

    # 4. Keyword Frequencies (Open Coding level, separated by strength/development)
    logging.info("Aggregating keyword frequencies...")
    open_code_freq = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    axial_freq = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    processed = 0
    for idx in range(len(all_df)):
        uid = str(all_df.iloc[idx][uid_col])
        g = all_df.iloc[idx]["group"]
        kw_path = COMMENTS_DIR / f"{uid}_keywords.json"
        if not kw_path.exists():
            continue
        try:
            kw_data = json.loads(kw_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        processed += 1
        for ct in COMMENT_TYPES:
            ct_data = kw_data.get(ct, {})
            if not ct_data:
                continue
            for axial_name, ax_data in ct_data.items():
                if not isinstance(ax_data, dict):
                    continue
                oc = ax_data.get("open_codes", {})
                if not oc:
                    continue
                # Track axial-level mention (at least one open code hit)
                has_hit = False
                for oc_name, oc_data in oc.items():
                    if isinstance(oc_data, dict) and oc_data.get("count", 0) > 0:
                        open_code_freq[g][ct][oc_name] += 1
                        has_hit = True
                if has_hit:
                    axial_freq[g][ct][axial_name] += 1

    logging.info(f"Processed {processed} keyword files")
    for g in groups:
        result[g]["keywords"] = {}
        for ct in COMMENT_TYPES:
            result[g]["keywords"][ct] = {
                "open_codes": dict(open_code_freq[g][ct]),
                "axial_codes": dict(axial_freq[g][ct]),
            }

    # 5. Demographics
    logging.info("Aggregating demographics...")
    demo_cols = {"司龄": 2, "年龄": 3, "直接下属人数": 4, "一级序列": 6, "二级序列": 7, "去年年度绩效数据": 8}
    for g in groups:
        mask = all_df["group"] == g
        gdf = all_df[mask]
        result[g]["demographics"] = {}
        for name, col_idx in demo_cols.items():
            col = all_df.columns[col_idx]
            vals = pd.to_numeric(gdf[col], errors="coerce")
            if vals.notna().sum() > 0:
                result[g]["demographics"][name] = {
                    "mean": round(float(vals.mean()), 2),
                    "median": round(float(vals.median()), 2),
                    "n": int(vals.notna().sum()),
                }
            else:
                vc = gdf[col].value_counts(dropna=False)
                result[g]["demographics"][name] = {
                    "distribution": {str(k): int(v) for k, v in vc.items()},
                }

    # 6. Comment Volume
    logging.info("Computing comment volume...")
    for g in groups:
        mask = all_df["group"] == g
        gdf = all_df[mask]
        result[g]["comment_volume"] = {}
        for col in ["优势评语_条数", "发展建议_条数", "其他建议_条数"]:
            vals = pd.to_numeric(gdf[col], errors="coerce").dropna()
            if len(vals) > 0:
                result[g]["comment_volume"][col] = {
                    "mean": round(float(vals.mean()), 1),
                    "median": round(float(vals.median()), 1),
                    "n": int(len(vals)),
                }

    # Save
    out_path = OUTPUT_DIR / "group_profiling_data.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info(f"Saved: {out_path}")

if __name__ == "__main__":
    main()
