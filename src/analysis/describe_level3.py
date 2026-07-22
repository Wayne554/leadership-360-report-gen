"""
L3 数据描述性报告脚本
输出：data/processed/describe_level3_report.txt
"""
import pandas as pd
import numpy as np
from pathlib import Path

DF = Path("data/processed/leadership_feedback_level3_wide.csv")
OUT = Path("data/processed/describe_level3_report.txt")

DIMS = [
    "战略思维-科学决策", "创新引领-持续精进", "全球视野-管理复杂情况",
    "客户导向-珍视客户", "数智变革-加强数字应用", "发展组织-带兵打仗",
    "追求卓越-高效执行",
]
SOURCES = ["本人", "上级", "协同方", "下级", "他评"]

lines = []
def p(s=""):
    lines.append(str(s))

df = pd.read_csv(DF, encoding="utf-8-sig")
N = len(df)

# ============ 1. 人口学概况 ============
p("=" * 70)
p("L3 数据描述性报告")
p("=" * 70)
p()
p(f"样本量: {N} 名中层管理者")
p()

p("--- 1. 人口统计学概况 ---")
p()

demo_fields = [
    ("司龄（年）", "司龄"),
    ("年龄（岁）", "年龄"),
    ("直接下属人数", "直接下属人数"),
]
for label, col in demo_fields:
    vals = df[col].dropna()
    p(f"{label}:")
    p(f"  N={len(vals):3d} | M={vals.mean():6.2f} | SD={vals.std():6.2f} | "
      f"Min={vals.min():6.1f} | P25={vals.quantile(0.25):6.1f} | "
      f"P50={vals.median():6.1f} | P75={vals.quantile(0.75):6.1f} | Max={vals.max():6.1f}")

# 一级序列
p()
p("一级序列分布:")
seq1 = df["一级序列"].dropna()
for v, c in seq1.value_counts().items():
    p(f"  {v}: {c:3d} ({c/N*100:5.1f}%)")

p()
p("二级序列分布（Top 10）:")
seq2 = df["二级序列"].dropna()
for v, c in seq2.value_counts().head(10).items():
    p(f"  {v}: {c:3d} ({c/N*100:5.1f}%)")

p()
p("去年年度绩效分布:")
perf = df["去年年度绩效数据"].dropna().astype(str)
for v, c in perf.value_counts().items():
    p(f"  {v}: {c:3d} ({c/N*100:5.1f}%)")

# ============ 2. 各维度评分概况（按评价源） ============
p()
p("--- 2. 各维度评分概况（按评价源） ---")
p()

for dim in DIMS:
    p(f"[{dim}]")
    for src in SOURCES:
        col = f"{src}-{dim}"
        vals = df[col].dropna()
        n = len(vals)
        if n == 0:
            p(f"  {src}: 无数据")
            continue
        p(f"  {src}: N={n:3d} | M={vals.mean():6.2f} | SD={vals.std():6.2f} | "
          f"Min={vals.min():4.1f} | P25={vals.quantile(0.25):4.1f} | "
          f"P50={vals.median():4.1f} | P75={vals.quantile(0.75):4.1f} | Max={vals.max():4.1f}")
    p()

# ============ 3. 评价源对比矩阵 ============
p("--- 3. 各维度评价源对比（均值） ---")
p()

header = f"{'维度':20s}" + "".join(f"{s:>8s}" for s in SOURCES)
p(header)
p("-" * 70)
for dim in DIMS:
    means = []
    for src in SOURCES:
        col = f"{src}-{dim}"
        m = df[col].mean()
        means.append(m if not np.isnan(m) else float("nan"))
    row = f"{dim:20s}" + "".join(f"{m:8.2f}" if not np.isnan(m) else "     NaN" for m in means)
    p(row)
p()

# ============ 4. 自评-他评差距 ============
p("--- 4. 自评-他评差距分析 ---")
p()

gap_header = f"{'维度':20s}{'自评均值':>8s}{'他评均值':>8s}{'差距':>8s}{'差距SD':>8s}"
p(gap_header)
p("-" * 60)
for dim in DIMS:
    self_v = df[f"本人-{dim}"].dropna()
    other_v = df[f"他评-{dim}"].dropna()
    if len(self_v) > 0 and len(other_v) > 0:
        s_mean = self_v.mean()
        o_mean = other_v.mean()
        gap = s_mean - o_mean
        # calculate gap SD (pooled across aligned pairs)
        aligned = df[[f"本人-{dim}", f"他评-{dim}"]].dropna()
        pair_gaps = aligned.iloc[:, 0] - aligned.iloc[:, 1]
        gap_sd = pair_gaps.std()
        p(f"{dim:20s}{s_mean:8.2f}{o_mean:8.2f}{gap:+8.2f}{gap_sd:8.2f}")
p()

# ============ 5. 他评来源数概况 ============
p("--- 5. 他评来源数概况 ---")
p()
for src in ["上级", "协同方", "下级"]:
    counts = []
    for _, row in df.iterrows():
        n_rated = sum(1 for d in DIMS if pd.notna(row.get(f"{src}-{d}")))
        if n_rated > 0:
            counts.append(1)
        else:
            counts.append(0)
    p(f"{src}: 有评价数据的人数 = {sum(counts)}/{N}")

# ============ 6. 评分分布直方摘要 ============
p()
p("--- 6. 各评价源评分分布摘要 ---")
p()
for src in SOURCES:
    all_vals = []
    for dim in DIMS:
        col = f"{src}-{dim}"
        all_vals.extend(df[col].dropna().tolist())
    if not all_vals:
        p(f"{src}: 无数据")
        continue
    arr = np.array(all_vals)
    p(f"{src}: 总评分数={len(arr):5d} | M={arr.mean():6.2f} | SD={arr.std():6.2f}")
    # 1-5 分布
    for s in range(1, 6):
        pct = (arr == s).mean() * 100
        p(f"  {s}分: {pct:5.1f}%")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"报告已写入: {OUT}")
print(f"共 {len(lines)} 行")
