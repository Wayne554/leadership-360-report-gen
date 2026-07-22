#!/usr/bin/env python3
"""L3 全面统计分析 + 图表生成"""
import json, warnings
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats as sp_stats
warnings.filterwarnings("ignore")

plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei"],
  "axes.unicode_minus":False,"figure.dpi":150,"savefig.dpi":300,
  "savefig.bbox":"tight","font.size":10})

COLORS=["#4C72B0","#DD8452","#55A868","#C44E52","#8172B3","#937860","#DA8BC3"]
CSRC=["#4C72B0","#DD8452","#55A868","#C44E52","#8172B3"]
DIMS = ["战略思维-科学决策","创新引领-持续精进","全球视野-管理复杂情况",
        "客户导向-珍视客户","数智变革-加强数字应用","发展组织-带兵打仗","追求卓越-高效执行"]
DIM_SHORT = ["战略思维","创新引领","全球视野","客户导向","数智变革","发展组织","高效执行"]
SOURCES = ["本人","上级","协同方","下级","他评"]

DATA=Path("data/processed/leadership_feedback_level3_wide.csv")
FIG=Path("output/analysis_figures_l3"); FIG.mkdir(parents=True,exist_ok=True)
STATS=Path("data/processed/norm_stats_l3.json")
df=pd.read_csv(DATA,encoding="utf-8-sig"); N=len(df)

# Compute tenure groups
tenure=df["司龄"]
df["司龄分组"]=pd.cut(tenure,[0,3,7,999],
  labels=["3年以下","3-7年","7年以上"],right=False).astype(str)
tenure_groups=df["司龄分组"]

def sf(name): plt.savefig(FIG/name,dpi=300,bbox_inches="tight",facecolor="white",edgecolor="none"); plt.close(); print(" ->",FIG/name)
def c(src,dim): return f"{src}-{dim}"

# ---- Norm stats ----
norm={"N":N,"level":"L3","dimensions":{}}
for dim in DIMS:
  entry={"self":{},"other":{},"sources":{}}
  for src in SOURCES:
    v=df[c(src,dim)].dropna()
    entry["sources"][src]={"N":int(len(v)),"M":round(float(v.mean()),3),
      "SD":round(float(v.std(ddof=1)),3),"P50":round(float(v.median()),3),
      "P25":round(float(v.quantile(0.25)),3),"P75":round(float(v.quantile(0.75)),3)}
  a=df[[c("本人",dim),c("他评",dim)]].dropna()
  g=a.iloc[:,0]-a.iloc[:,1]
  entry["self"]=entry["sources"]["本人"]
  entry["other"]=entry["sources"]["他评"]
  entry["gap"]={"M":round(float(g.mean()),3),"SD":round(float(g.std(ddof=1)),3),
    "Cohen_d":round(float(g.mean()/df[c("他评",dim)].std(ddof=1)),3)}
  for tg in ["3年以下","3-7年","7年以上"]:
    sub=df[df["司龄分组"]==tg][c("他评",dim)].dropna()
    entry.setdefault("tenure_norms",{})[tg]={"N":int(len(sub)),
      "P50":round(float(sub.median()),3),"M":round(float(sub.mean()),3)}
  norm["dimensions"][dim]=entry
STATS.write_text(json.dumps(norm,ensure_ascii=False,indent=2),encoding="utf-8")
print("Norm stats written to norm_stats_l3.json")

# ---- P1: Donut ----
seq=df["一级序列"].value_counts()
t5=seq.head(5);on=seq.iloc[5:].sum()
lab=list(t5.index)+(["其他"] if on>0 else [])
val=list(t5.values)+([on] if on>0 else [])
fig,ax=plt.subplots(figsize=(7,5))
w,_,a=ax.pie(val,labels=None,autopct="%1.1f%%",startangle=90,pctdistance=0.78,
  colors=COLORS+["#AAAAAA"],wedgeprops={"width":0.4,"edgecolor":"white","linewidth":1.5})
for t in a: t.set_fontsize(9); t.set_fontweight("bold")
ax.legend(w,[f"{l} ({v}/{N})" for l,v in zip(lab,val)],title="一级序列",loc="center left",bbox_to_anchor=(0.98,0.5))
ax.set_title("L3 中层管理者 -- 一级序列分布",fontsize=14,fontweight="bold",pad=16)
sf("p1_sequence_donut.png")

# ---- P2: Tenure x Performance ----
to=["3年以下","3-7年","7年以上"]
po=["A","B+"]
ct=pd.crosstab(df["司龄分组"],df["去年年度绩效数据"])
# 只保留A/B+, 其他忽略
for col in po:
  if col not in ct.columns: ct[col]=0
ct=ct[[c for c in po if c in ct.columns]]
ct=ct.reindex(to).fillna(0)
fig,ax=plt.subplots(figsize=(7,5))
x=np.arange(3);w=0.30
for i,p in enumerate(po):
  if p not in ct.columns: continue
  b=ax.bar(x+i*w,ct[p],w,label=p,color=COLORS[i],edgecolor="white",linewidth=0.5)
  for br in b:
    h=br.get_height()
    if h>0: ax.text(br.get_x()+w/2,h+2,int(h),ha="center",va="bottom",fontsize=9)
ax.set_xticks(x+w/2);ax.set_xticklabels(to);ax.set_ylabel("人数");ax.legend(title="绩效")
ax.set_title("L3 司龄分组 x 绩效等级分布",fontsize=14,fontweight="bold")
sns.despine()
sf("p2_tenure_performance.png")

# ---- D1: Faceted boxplot ----
fig,axes=plt.subplots(3,3,figsize=(16,16),sharey=True)
af=axes.flatten()
for i,(dim,short) in enumerate(zip(DIMS,DIM_SHORT)):
  ax=af[i]
  data=[df[c(s,dim)].dropna().values for s in SOURCES]
  bp=ax.boxplot(data,labels=SOURCES,patch_artist=True,widths=0.5,showmeans=True,
    meanprops={"marker":"D","markerfacecolor":"white","markeredgecolor":"black","markersize":5})
  for patch,clr in zip(bp["boxes"],CSRC): patch.set_facecolor(clr); patch.set_alpha(0.65)
  ax.set_title(short,fontweight="bold");ax.set_ylim(0.5,5.5);ax.tick_params(axis="x",labelsize=8)
  for j,s in enumerate(SOURCES):
    ax.text(j+1,5.25,f"N={len(df[c(s,dim)].dropna())}",ha="center",va="top",fontsize=6.5,color="gray")
for j in range(7,9): af[j].set_visible(False)
fig.suptitle("L3 各维度评分分布 -- 分评价源箱线图",fontsize=15,fontweight="bold",y=1.01)
fig.tight_layout()
sf("d1_faceted_boxplot.png")

# ---- D2: KDE overlay ----
fig,ax=plt.subplots(figsize=(10,6))
xg=np.linspace(2,5.2,500)
for i,(dim,short) in enumerate(zip(DIMS,DIM_SHORT)):
  v=df[c("他评",dim)].dropna()
  kde=sp_stats.gaussian_kde(v)
  ax.plot(xg,kde(xg),color=COLORS[i],lw=2,label=f"{short} (M={v.mean():.2f})")
  ax.fill_between(xg,kde(xg),alpha=0.06,color=COLORS[i])
ax.set_xlabel("他评得分");ax.set_ylabel("密度")
ax.set_title("L3 他评得分分布 -- 7维度 KDE 叠加",fontsize=14,fontweight="bold")
ax.legend(fontsize=8.5,loc="upper left");ax.set_xlim(2,5.2);sns.despine()
sf("d2_kde_other_ratings.png")

# ---- D3: Heatmap ----
hm=np.zeros((5,7))
for i,src in enumerate(SOURCES):
  for j,dim in enumerate(DIMS): hm[i,j]=df[c(src,dim)].mean()
fig,ax=plt.subplots(figsize=(11,5))
im=ax.imshow(hm,cmap="RdYlGn",vmin=3.5,vmax=4.8,aspect="auto")
ax.set_xticks(range(7));ax.set_xticklabels(DIM_SHORT,rotation=30,ha="right")
ax.set_yticks(range(5));ax.set_yticklabels(SOURCES)
for i in range(5):
  for j in range(7):
    v=hm[i,j]
    ax.text(j,i,f"{v:.2f}",ha="center",va="center",fontsize=9,color="white" if v<4.1 else "black",fontweight="bold")
fig.colorbar(im,ax=ax,shrink=0.8,pad=0.02)
ax.set_title("L3 评价源 x 维度 -- 均值热力图",fontsize=14,fontweight="bold")
sf("d3_heatmap.png")

# ---- G1: Gap bar ----
gm=[];gd=[]
for dim in DIMS:
  a=df[[c("本人",dim),c("他评",dim)]].dropna()
  g=a.iloc[:,0]-a.iloc[:,1];gm.append(g.mean());gd.append(g.mean()/df[c("他评",dim)].std(ddof=1))
fig,ax=plt.subplots(figsize=(10,5.5))
bc=["#C44E52" if g>0 else "#55A868" for g in gm]
bars=ax.barh(DIM_SHORT,gm,color=bc,edgecolor="white",height=0.55,alpha=0.85)
for bar,g,d in zip(bars,gm,gd):
  lbl=f"+{g:.2f} (d={d:.2f})" if g>0 else f"{g:.2f} (d={d:.2f})"
  ax.text(bar.get_width()+0.005,bar.get_y()+bar.get_height()/2,lbl,va="center",fontsize=9,fontweight="bold")
ax.axvline(0,color="black",lw=1)
ax.set_xlabel("自评均值 - 他评均值");ax.set_title("L3 自评-他评差距分析 (含 Cohen d)",fontsize=14,fontweight="bold")
sns.despine()
sf("g1_gap_bar.png")

# ---- G2: Self-other scatter ----
sm=[df[c("本人",d)].mean() for d in DIMS]
om=[df[c("他评",d)].mean() for d in DIMS]
fig,ax=plt.subplots(figsize=(8,7))
ax.scatter(om,sm,s=200,c=COLORS[:7],edgecolors="white",linewidth=1.5,zorder=5)
for o,s,short in zip(om,sm,DIM_SHORT):
  ax.annotate(short,(o,s),textcoords="offset points",xytext=(8,6),fontsize=10,fontweight="bold")
lo=min(min(sm),min(om))-0.1;hi=max(max(sm),max(om))+0.1
ax.plot([lo,hi],[lo,hi],"k--",lw=1,alpha=0.4,label="自评=他评")
sp50=np.median(sm);op50=np.median(om)
ax.axhline(sp50,color="gray",lw=1,ls=":",alpha=0.6)
ax.axvline(op50,color="gray",lw=1,ls=":",alpha=0.6)
for txt,xr,yr,clr in [("优势区",hi-0.25,hi-0.05,"#55A868"),("盲区",lo+0.05,hi-0.05,"#DD8452"),("潜能区",hi-0.25,lo+0.05,"#4C72B0"),("待发展区",lo+0.05,lo+0.05,"#C44E52")]:
  ax.text(xr,yr,txt,fontsize=11,color=clr,fontweight="bold",ha="left" if "待" in txt else "right")
ax.set_xlabel("他评均值 (群体常模参考)");ax.set_ylabel("自评均值 (群体常模参考)")
ax.set_title("L3 群体层面: 自评 vs. 他评趋势",fontsize=14,fontweight="bold")
ax.set_xlim(lo,hi);ax.set_ylim(lo,hi);ax.set_aspect("equal");ax.legend(fontsize=9)
sf("g2_self_other_scatter.png")

# ---- J1: Density + threshold ----
fig,axes=plt.subplots(3,3,figsize=(15,13))
af=axes.flatten()
for i,(dim,short) in enumerate(zip(DIMS,DIM_SHORT)):
  ax=af[i]
  v=df[c("他评",dim)].dropna();p50=v.median();mv=v.mean()
  kde=sp_stats.gaussian_kde(v)
  xg=np.linspace(max(1.5,v.min()-0.3),min(5.5,v.max()+0.3),300);d=kde(xg)
  ax.fill_between(xg,d,alpha=0.25,color=COLORS[i]);ax.plot(xg,d,color=COLORS[i],lw=2)
  ax.axvline(p50,color="#C44E52",lw=2.5,ls="--",label=f"P50={p50:.2f}")
  ax.axvline(mv,color="#4C72B0",lw=1.5,ls=":",label=f"M={mv:.2f}")
  ax.text(p50-0.08,max(d)*0.85,f"\u2193{(v<p50).mean()*100:.0f}%",ha="right",fontsize=8,color="#C44E52",fontweight="bold")
  ax.set_title(short,fontweight="bold");ax.set_xlim(2,5.2);ax.set_ylabel("密度");ax.legend(fontsize=7,loc="upper left")
for j in range(7,9): af[j].set_visible(False)
fig.suptitle("L3 他评得分密度分布 -- P50 vs. M",fontsize=14,fontweight="bold",y=1.01)
fig.tight_layout()
sf("j1_density_threshold.png")

# ---- C1: Comment counts ----
clabs=["优势评语","发展建议","其他建议"]
tot=[df[f"{l}_条数"].sum() for l in clabs]
mn=[df[f"{l}_条数"].mean() for l in clabs]
sdv=[df[f"{l}_条数"].std(ddof=1) for l in clabs]
fig,ax=plt.subplots(figsize=(8,4))
bars=ax.barh(clabs,mn,xerr=sdv,color=COLORS[:3],edgecolor="white",height=0.5,capsize=4,alpha=0.8)
for b,t,m,s in zip(bars,tot,mn,sdv):
  ax.text(b.get_width()+0.05,b.get_y()+b.get_height()/2,f"共{t}条 (M={m:.1f}, SD={s:.1f})",va="center",fontsize=10,fontweight="bold")
ax.set_xlabel("人均条数")
ax.set_title(f"L3 开放式评语概况 (总计 {sum(tot):,} 条)",fontsize=14,fontweight="bold")
sns.despine()
sf("c1_comment_counts.png")
print("\nDone! All 9 figures generated.")
