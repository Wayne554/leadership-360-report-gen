import json
from pathlib import Path
import pandas as pd
import numpy as np

SELF_THRESHOLD = 4.50
OTHER_THRESHOLDS = {"L3": 4.30, "L4": 4.40}
EXCLUDED_DIMS = ["数智变革-加强数字应用"]

DIMS = ["战略思维-科学决策","创新引领-持续精进","全球视野-管理复杂情况",
        "客户导向-珍视客户","数智变革-加强数字应用","发展组织-带兵打仗","追求卓越-高效执行"]

def get_quadrant(self_s, other_s, level):
    ot = OTHER_THRESHOLDS.get(level, 4.40)
    if self_s >= SELF_THRESHOLD and other_s >= ot:
        return "优势区"
    elif self_s < SELF_THRESHOLD and other_s >= ot:
        return "潜能区"
    elif self_s >= SELF_THRESHOLD and other_s < ot:
        return "盲区"
    else:
        return "待发展区"

def get_preamble_variant(dimensions):
    pos = {"优势区", "潜能区"}
    pos_count = sum(1 for dd in dimensions.values() if dd["quadrant"] in pos)
    if pos_count >= 7:
        return "positive"
    elif pos_count >= 5:
        return "mostly_positive"
    else:
        return "standard"

all_persons = {}
for level, csv_name in [("L3", "leadership_feedback_level3_wide.csv"),
                        ("L4", "leadership_feedback_level4_wide.csv")]:
    path = f"data/processed/{csv_name}"
    df = pd.read_csv(path, encoding="utf-8-sig")
    user_col = df.columns[0]
    print(f"Loading {level}: {len(df)} persons from {csv_name}")
    for idx, row in df.iterrows():
        pid = str(row[user_col])
        dims = {}
        for dim in DIMS:
            sv = row.get(f"本人-{dim}")
            ov = row.get(f"他评-{dim}")
            if pd.isna(sv) or pd.isna(ov):
                continue
            sv, ov = float(sv), float(ov)
            dist = round(np.sqrt(sv**2 + ov**2), 4)
            quad = get_quadrant(sv, ov, level)
            dims[dim] = {"self": sv, "other": ov, "distance": dist, "quadrant": quad}
        candidate = [d for d in DIMS if d not in EXCLUDED_DIMS and d in dims]
        sorted_dims = sorted(candidate, key=lambda d: dims[d]["distance"])
        bottom3_keys = sorted_dims[:3]
        bottom3_data = {k: dims[k] for k in bottom3_keys}
        pv = get_preamble_variant(dims)
        all_persons[pid] = {
            "dimensions": dims,
            "bottom3_keys": bottom3_keys,
            "bottom3_data": bottom3_data,
            "preamble_variant": pv,
        }

result = {
    "level": "L3+L4",
    "count": len(all_persons),
    "excluded_dim": "数智",
    "thresholds": {"self": SELF_THRESHOLD, "other": OTHER_THRESHOLDS},
    "persons": all_persons,
}

out_path = Path("data/processed/dimension_distances.json")
out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

variants = {}
for pid, pdata in all_persons.items():
    v = pdata["preamble_variant"]
    variants[v] = variants.get(v, 0) + 1

print(f"\nWritten {len(all_persons)} persons to {out_path}")
print(f"Thresholds: self=4.50, L3=4.30, L4=4.40")
print(f"Preamble variant distribution:")
for v, c in sorted(variants.items(), key=lambda x: -x[1]):
    print(f"  {v}: {c} ({c/len(all_persons)*100:.1f}%)")
