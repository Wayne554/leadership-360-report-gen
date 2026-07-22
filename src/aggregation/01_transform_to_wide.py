"""
数据处理脚本：将 多行（评价者）→ 1人1行宽表

输出：
  - data/processed/leadership_feedback_level3_wide.csv
  - data/processed/leadership_feedback_level4_wide.csv

作者：Codex
日期：2026-07-20
"""
import pandas as pd
import numpy as np
from pathlib import Path

RAW = Path("data/raw")
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

DIM_NAMES = [
    "战略思维-科学决策", "创新引领-持续精进", "全球视野-管理复杂情况",
    "客户导向-珍视客户", "数智变革-加强数字应用", "发展组织-带兵打仗",
    "追求卓越-高效执行",
]
RATER_ORDER = ["本人", "上级", "协同方", "下级"]
RATER_MAP = {"自己": "本人", "上级": "上级", "下级": "下级", "协同方": "协同方"}

LEVEL_CONFIG = {
    "level3": {
        "file": RAW / "leadership_feedback_level3_rev.csv",
        "dim_cols": {
            "战略思维-科学决策":  (10, 13),
            "创新引领-持续精进":  (13, 16),
            "全球视野-管理复杂情况": (16, 19),
            "客户导向-珍视客户":  (19, 22),
            "数智变革-加强数字应用": (22, 24),
            "发展组织-带兵打仗":  (24, 29),
            "追求卓越-高效执行":  (29, 31),
        },
        "comment_cols": (38, 41),
        "demo_cols":    (41, 48),
        "meta_prefix":  "L3",
    },
    "level4": {
        "file": RAW / "leadership_feedback_level4_rev.csv",
        "dim_cols": {
            "战略思维-科学决策":  (13, 15),
            "创新引领-持续精进":  (15, 17),
            "全球视野-管理复杂情况": (17, 19),
            "客户导向-珍视客户":  (19, 22),
            "数智变革-加强数字应用": (22, 24),
            "发展组织-带兵打仗":  (24, 27),
            "追求卓越-高效执行":  (27, 29),
        },
        "comment_cols": (10, 13),
        "demo_cols":    (36, 43),
        "meta_prefix":  "L4",
    },
}


def compute_dim_means(row, dim_cols):
    scores = {}
    for dim_name, (c_start, c_end) in dim_cols.items():
        vals = row.iloc[c_start:c_end].dropna().astype(float)
        scores[dim_name] = round(vals.mean(), 2) if len(vals) > 0 else np.nan
    return scores


def collect_comments(group, comment_cols):
    q_labels = ["优势评语", "发展建议", "其他建议"]
    result = {}
    for i, label in enumerate(q_labels):
        col = group.columns[comment_cols[0] + i]
        texts = group[col].dropna().tolist()
        result[label] = texts
    return result


def process_level(config):
    print(f"Processing {config['meta_prefix']}...")
    df = pd.read_csv(config["file"], encoding="utf-8")
    print(f"  Read {df.shape}")

    col_user_id = df.columns[0]
    col_rater_rel = df.columns[8]

    # 逐行计算维度均分
    dim_means = df.apply(lambda row: compute_dim_means(row, config["dim_cols"]), axis=1)
    dim_df = pd.DataFrame(dim_means.tolist(), index=df.index)

    records = []
    for user_id, user_group in df.groupby(col_user_id):
        demo = user_group.iloc[0, config["demo_cols"][0]:config["demo_cols"][1]].to_dict()
        demo_col_names = list(df.columns[config["demo_cols"][0]:config["demo_cols"][1]])
        comments = collect_comments(user_group, config["comment_cols"])

        row_data = {}
        for rater_type in RATER_ORDER:
            src_name = {v: k for k, v in RATER_MAP.items()}[rater_type]
            sub = user_group[user_group[col_rater_rel] == src_name]
            if len(sub) == 0:
                for dim in DIM_NAMES:
                    row_data[f"{rater_type}-{dim}"] = np.nan
                continue
            for dim in DIM_NAMES:
                dim_scores = dim_df.loc[sub.index, dim].dropna()
                row_data[f"{rater_type}-{dim}"] = round(dim_scores.mean(), 2) if len(dim_scores) > 0 else np.nan

        # 他评 = 上级 + 协同方 + 下级的聚合
        for dim in DIM_NAMES:
            others = []
            for rt in ["上级", "协同方", "下级"]:
                val = row_data.get(f"{rt}-{dim}")
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    others.append(val)
            row_data[f"他评-{dim}"] = round(np.mean(others), 2) if len(others) > 0 else np.nan

        record = {"被评人工号": user_id, "层级": config["meta_prefix"]}
        for cn in demo_col_names:
            record[cn] = demo.get(cn, np.nan)
        record.update(row_data)
        for label, texts in comments.items():
            record[label] = " ||| ".join(texts) if texts else ""
            record[f"{label}_条数"] = len(texts)
        records.append(record)

    result_df = pd.DataFrame(records)
    base_cols = ["被评人工号", "层级"] + demo_col_names
    score_cols = []
    for rater_type in RATER_ORDER + ["他评"]:
        for dim in DIM_NAMES:
            score_cols.append(f"{rater_type}-{dim}")
    comment_cols_out = ["优势评语", "发展建议", "其他建议",
                        "优势评语_条数", "发展建议_条数", "其他建议_条数"]
    final_cols = [c for c in base_cols + score_cols + comment_cols_out if c in result_df.columns]
    result_df = result_df[final_cols]

    out_path = OUT / ("leadership_feedback_level3_wide.csv" if config["meta_prefix"]=="L3" else "leadership_feedback_level4_wide.csv")
    result_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  Written: {out_path} ({result_df.shape})")
    return result_df


if __name__ == "__main__":
    for level_name, config in LEVEL_CONFIG.items():
        process_level(config)
    print("Done")
