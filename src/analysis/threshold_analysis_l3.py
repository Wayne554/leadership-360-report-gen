#!/usr/bin/env python3
"""L3 乔哈里视窗阈值选择分析"""
import json, warnings
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
warnings.filterwarnings("ignore")

plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei"],
  "axes.unicode_minus":False,"savefig.dpi":300,"savefig.bbox":"tight"})

COLORS = ["#4C72B0","#DD8452","#55A868","#C44E52","#8172B3","#937860","#DA8BC3"]

FIG = Path("output/analysis_figures_l3")
DATA = Path("data/processed/leadership_feedback_level3_wide.csv")
FIG.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(DATA, encoding="utf-8-sig")

DIMS = ["战略思维-科学决策","创新引领-持续精进","全球视野-管理复杂情况",
        "客户导向-珍视客户","数智变革-加强数字应用","发展组织-带兵打仗","追求卓越-高效执行"]
SHORT = ["战略思维","创新引领","全球视野","客户导向","数智变革","发展组织","高效执行"]

self_t = 4.5

def sf(name): plt.savefig(FIG/name,dpi=300,bbox_inches="tight",facecolor="white"); plt.close(); print(f"  -> {FIG/name}")
def c(src,dim): return f"{src}-{dim}"

# ---- 自评 P50 确认 ----
print("=== 自评 P50 各维度 ===")
for dim in DIMS:
    v = df[c("本人", dim)].dropna()
    print(f"  {dim}: P50={v.median():.2f}, M={v.mean():.3f}")

# ---- 他评 P50 确认 ----
print("\n=== 他评 P50 各维度 ===")
for dim in DIMS:
    v = df[c("他评", dim)].dropna()
    print(f"  {dim}: P50={v.median():.2f}, M={v.mean():.3f}, P25={v.quantile(0.25):.2f}, P75={v.quantile(0.75):.2f}")

# Compute quadrant data for both thresholds
results = {}
for ot in [4.4, 4.3]:
    rows = []
    for dim in DIMS:
        p = df[[c("本人", dim), c("他评", dim)]].dropna()
        sh = p[c("本人", dim)] >= self_t
        oh = p[c("他评", dim)] >= ot
        n = len(p)
        a = (sh & oh).sum() / n
        b = (sh & ~oh).sum() / n
        po = (~sh & oh).sum() / n
        dq = (~sh & ~oh).sum() / n
        rows.append({"dim": dim, "arena": a, "blind": b, "potential": po, "develop": dq, "n": n})
    results[ot] = rows

# 打印象限分布表
for ot in [4.4, 4.3]:
    print(f"\n=== 他评阈值={ot} 象限分布 ===")
    for r in results[ot]:
        print(f"  {r['dim']:　<15} 优势区={r['arena']*100:5.1f}%  盲区={r['blind']*100:5.1f}%  潜能区={r['potential']*100:5.1f}%  待发展区={r['develop']*100:5.1f}%")

# ---- F1: 优势区对比 4.4 vs 4.3 ----
print("\n[F1] 优势区阈值对比 ...")
fig, ax = plt.subplots(figsize=(10, 5.5))
x = np.arange(7); w = 0.30
for i, (ot, label, off, color) in enumerate([(4.4, "4.4", -w/2, "#C44E52"), (4.3, "4.3", w/2, "#55A868")]):
    vals = [r["arena"]*100 for r in results[ot]]
    bars = ax.bar(x + off, vals, w, label=label, color=color, alpha=0.80, edgecolor="white")
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x()+w/2, bar.get_height()+0.8, f"{v:.1f}%", ha="center", va="bottom", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(SHORT, fontsize=10)
ax.set_ylabel("落入优势区的比例")
ax.set_title("L3 乔哈里视窗: 他评阈值 4.4 vs 4.3 的\"优势区\"对比", fontsize=13, fontweight="bold")
ax.legend(title="他评阈值")
sns.despine()
sf("f1_threshold_comparison.png")

# ---- F2: 4.4 方案四象限堆叠图 ----
print("[F2] 4.4 方案四象限堆叠 ...")
fig, ax = plt.subplots(figsize=(11, 6))
bottom = np.zeros(7)
data44 = results[4.4]
for key, label, color in [("arena", "优势区", "#55A868"), ("blind", "盲区", "#DD8452"),
                           ("potential", "潜能区", "#4C72B0"), ("develop", "待发展区", "#C44E52")]:
    vals = np.array([r[key]*100 for r in data44])
    bars = ax.barh(SHORT, vals, left=bottom, label=label, color=color, edgecolor="white",
                   height=0.55, alpha=0.85)
    for bar, v in zip(bars, vals):
        if v > 8:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_y()+bar.get_height()/2,
                    f"{v:.1f}%", ha="center", va="center", fontsize=8, fontweight="bold", color="white")
    bottom += vals
ax.set_xlabel("占比 (%)")
ax.set_title("L3 他评阈值 4.4 方案: 四象限分布", fontsize=14, fontweight="bold")
ax.legend(loc="lower right", fontsize=9)
ax.set_xlim(0, 100); sns.despine()
sf("f2_quadrant_44_stacked.png")

# ---- F3: 维度他评分布 + 阈值线 ----
print("[F3] 维度他评分布 + 阈值线 ...")
fig, ax = plt.subplots(figsize=(11, 6))
for i, (dim, short) in enumerate(zip(DIMS, SHORT)):
    vals = df[c("他评", dim)].dropna()
    p50 = vals.median(); p25 = vals.quantile(0.25); p75 = vals.quantile(0.75)
    ax.errorbar(p50, i, xerr=[[p50-p25], [p75-p50]], fmt="o", color=COLORS[i],
                capsize=4, capthick=1.5, markersize=10, label=short, zorder=5)
    ax.text(p50+0.03, i-0.15, f"P50={p50:.2f}", fontsize=8, color=COLORS[i], fontweight="bold")
ax.axvline(4.4, color="#C44E52", lw=2.5, ls="--", label="候选阈值 (4.4)", zorder=10)
ax.axvline(4.3, color="#55A868", lw=2, ls=":", label="候选阈值 (4.3)", zorder=10)
ax.set_yticks(range(7)); ax.set_yticklabels(SHORT); ax.set_xlabel("他评得分")
ax.set_title("L3 各维度他评分布中位数 (P50) 与候选阈值", fontsize=14, fontweight="bold")
ax.set_xlim(3.5, 5.0); ax.legend(fontsize=9); sns.despine()
sf("f3_threshold_position.png")

print("\nDone! 3 figures generated.")
