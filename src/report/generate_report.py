"""
个体报告生成脚本：读取宽表 + 常模 → 渲染 Jinja2 模板 → 输出 HTML

用法：
  python src/report/generate_report.py [--user_id <工号>] [--level L3|L4] [--output-dir <路径>]

若不指定 --user_id，则列出前 5 人供选择。

作者：Codex
日期：2026-07-20
"""

import argparse
import json
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))
from src.report import narrative
from src.rag.dev_suggestions import get_development_section
from pathlib import Path

import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from collections import OrderedDict
from jinja2 import Environment, FileSystemLoader

# ── 路径 ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output" / "individual"

DIM_NAMES = [
    "战略思维-科学决策",
    "创新引领-持续精进",
    "全球视野-管理复杂情况",
    "客户导向-珍视客户",
    "数智变革-加强数字应用",
    "发展组织-带兵打仗",
    "追求卓越-高效执行",
]
RATER_SOURCES = ["上级", "协同方", "下级"]
LEVEL_LABELS = {"L3": "战略执行层", "L4": "基层管理者"}
JOHARI_THRESHOLD_SELF = 4.50


def _get_other_threshold(level: str = "L4") -> float:
    """根据层级返回他评阈值。"""
    thresholds = {"L3": 4.30, "L4": 4.40}
    return thresholds.get(level, 4.40)


DOMAIN_MAP = {
    "战略思维-科学决策":  "驱动业务",
    "创新引领-持续精进":  "驱动业务",
    "全球视野-管理复杂情况": "驱动业务",
    "客户导向-珍视客户":  "驱动业务",
    "数智变革-加强数字应用": "组织建设",
    "发展组织-带兵打仗":  "组织建设",
    "追求卓越-高效执行":  "文化旗手",
}


# ── 数据加载 ──────────────────────────────────────────────────────

def load_data(level: str = "L4", user_id: str | None = None) -> pd.DataFrame:
    """加载指定层级的宽表数据，若给定工号则只返回该行。"""
    fname = f"leadership_feedback_level{re.search(r'\d+', level).group()}_wide.csv"
    path = DATA_DIR / "processed" / fname
    df = pd.read_csv(path, encoding="utf-8-sig")

    meta_col = df.columns[0]  # 被评人工号
    if user_id:
        row = df[df[meta_col].astype(str) == str(user_id)]
        if len(row) == 0:
            available = sorted(df[meta_col].astype(str).unique()[:10])
            raise ValueError(f"工号 {user_id} 不存在。前 10 个工号: {available}")
        df = row
    return df


def load_norms(level: str = "L4") -> dict:
    """加载常模统计数据。"""
    path = DATA_DIR / "processed" / f"norm_stats_{level.lower()}.json"
    with open(path, "r", encoding="utf-8") as f:
        norms = json.load(f)
    return norms["dimensions"]


def load_questionnaire(level: str = "L4") -> list[dict]:
    """加载问卷条目结构，用于附录条目表。"""
    path = DATA_DIR / "raw" / f"level{re.search(r'\d+', level).group()}-questionnaire.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    # 列: 域, 维度, 要素, 关键行为描述, firstline manager
    items = []
    for _, row in df.iterrows():
        dim = row.iloc[2] if pd.notna(row.iloc[2]) else ""
        if dim == "-" or not dim:
            continue
        items.append({
            "dimension": dim.strip() if isinstance(dim, str) else "",
            "text": str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else "",
        })
    return items


# ── 图表生成 ──────────────────────────────────────────────────────

def make_radar_chart(
    dims: list[str],
    self_scores: list[float],
    other_scores: list[float],
    norm_other_means: list[float],
) -> str:
    """生成七维度雷达图 HTML。marker 白色填充 + 彩色边框。"""
    tickvals = [3.0, 3.5, 4.0, 4.5, 5.0]
    ticktext = ["3.0", "3.5", "4.0", "4.5", "5.0"]
    r_min, r_max = 3.0, 5.0

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=self_scores + [self_scores[0]],
        theta=dims + [dims[0]],
        name="自评",
        line=dict(color="#1a365d", width=1.5),
        marker=dict(size=7, color="white", line=dict(color="#1a365d", width=1.5)),
    ))
    fig.add_trace(go.Scatterpolar(
        r=other_scores + [other_scores[0]],
        theta=dims + [dims[0]],
        name="他评",
        line=dict(color="#e67e22", width=1.5, dash="dash"),
        marker=dict(size=7, color="white", line=dict(color="#e67e22", width=1.5)),
    ))
    fig.add_trace(go.Scatterpolar(
        r=norm_other_means + [norm_other_means[0]],
        theta=dims + [dims[0]],
        name="常模他评均值",
        line=dict(color="#a0aec0", width=1.5, dash="dot"),
        marker=dict(size=5, color="white", line=dict(color="#a0aec0", width=1.5)),
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True, range=[r_min, r_max],
                tickvals=tickvals, ticktext=ticktext,
                gridcolor="#e2e8f0", gridwidth=0.5,
            ),
            angularaxis=dict(
                gridcolor="#e2e8f0", gridwidth=0.5,
                tickfont=dict(size=11),
            ),
            bgcolor="rgba(0,0,0,0)",
        ),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        autosize=True,
        margin=dict(l=60, r=60, t=10, b=60),
        height=520,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="PingFang SC, Microsoft YaHei, sans-serif"),
    )
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": True, "responsive": True, "scrollZoom": True, "modeBarButtonsToRemove": ["toImage", "sendDataToCloud", "zoomIn2d", "zoomOut2d", "autoScale2d", "hoverClosestCartesian", "hoverCompareCartesian"], "modeBarButtonsToAdd": ["resetScale2d"], "displaylogo": False})
def make_line_chart(
    dims: list[str],
    self_scores: list[float],
    superior_scores: list[float],
    peer_scores: list[float],
    subordinate_scores: list[float],
    other_scores: list[float],
) -> str:
    """生成分评价源折线图 HTML。
    横轴=评分，纵轴=维度（旋转版本）。marker 白色填充 + 彩色边框。
    """
    fig = go.Figure()
    line_style = [
        (self_scores, "自评", "#1a365d", "solid", 3.0),
        (superior_scores, "上级", "#e53e3e", "solid", 2.0),
        (peer_scores, "协同方", "#dd6b20", "solid", 2.0),
        (subordinate_scores, "下级", "#38a169", "solid", 2.0),
        (other_scores, "他评", "#718096", "dash", 1.5),
    ]
    for scores, name, color, dash, width in line_style:
        cleaned = [s if (s is not None and not (isinstance(s, float) and np.isnan(s))) else None
                   for s in scores]
        # 交换 x/y：评分上横轴，维度上纵轴
        fig.add_trace(go.Scatter(
            x=cleaned, y=dims, name=name,
            orientation="h",
            line=dict(color=color, width=width, dash=dash),
            marker=dict(size=8, color="white", line=dict(color=color, width=1.5)),
            connectgaps=False,
        ))

    fig.update_layout(
        xaxis=dict(range=[3.0, 5.0], dtick=0.5, gridcolor="#e2e8f0", gridwidth=0.5,
                   title="评分", tickfont=dict(size=10)),
        yaxis=dict(gridcolor="#e2e8f0", gridwidth=0.5, tickfont=dict(size=10)),
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5),
        margin=dict(l=50, r=30, t=10, b=80),
        height=500,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="PingFang SC, Microsoft YaHei, sans-serif"),
        autosize=True,
    )
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": True, "responsive": True, "scrollZoom": True, "modeBarButtonsToRemove": ["toImage", "sendDataToCloud", "zoomIn2d", "zoomOut2d", "autoScale2d", "hoverClosestCartesian", "hoverCompareCartesian"], "modeBarButtonsToAdd": ["resetScale2d"], "displaylogo": False})
def make_johari_chart(
    dims: list[str],
    self_scores: list[float],
    other_scores: list[float],
    level: str = "L4",
) -> str:
    """生成乔哈里视窗四象限散点图 HTML。"""
    colors = {
        "优势区": "#38a169",
        "潜能区": "#3182ce",
        "盲区": "#dd6b20",
        "待发展区": "#e53e3e",
    }
    quadrants = {k: {"dims": [], "scores": []} for k in colors}

    for i, dim in enumerate(dims):
        s = self_scores[i]
        o = other_scores[i]
        if s is None or np.isnan(s) or o is None or np.isnan(o):
            continue
        if s >= JOHARI_THRESHOLD_SELF and o >= _get_other_threshold(level):
            q = "优势区"
        elif s < JOHARI_THRESHOLD_SELF and o >= _get_other_threshold(level):
            q = "潜能区"
        elif s >= JOHARI_THRESHOLD_SELF and o < _get_other_threshold(level):
            q = "盲区"
        else:
            q = "待发展区"
        quadrants[q]["dims"].append(dim)
        quadrants[q]["scores"].append((s, o, dim))

    fig = go.Figure()

    # 背景象限色块（用矩形 + 透明度模拟）
    bg_shapes = [
        # 待发展区 (左下)
        dict(type="rect", x0=1, y0=1, x1=JOHARI_THRESHOLD_SELF, y1=_get_other_threshold(level),
             fillcolor="rgba(229,62,62,0.06)", line=dict(width=0), layer="below"),
        # 盲区 (右下)
        dict(type="rect", x0=JOHARI_THRESHOLD_SELF, y0=1, x1=5, y1=_get_other_threshold(level),
             fillcolor="rgba(221,107,32,0.06)", line=dict(width=0), layer="below"),
        # 潜能区 (左上)
        dict(type="rect", x0=1, y0=_get_other_threshold(level), x1=JOHARI_THRESHOLD_SELF, y1=5,
             fillcolor="rgba(49,130,206,0.06)", line=dict(width=0), layer="below"),
        # 优势区 (右上)
        dict(type="rect", x0=JOHARI_THRESHOLD_SELF, y0=_get_other_threshold(level), x1=5, y1=5,
             fillcolor="rgba(56,161,105,0.06)", line=dict(width=0), layer="below"),
    ]

    for qname, qdata in quadrants.items():
        scores = qdata["scores"]
        if not scores:
            continue
        s_vals, o_vals, labels = zip(*scores)
        fig.add_trace(go.Scatter(
            x=list(s_vals), y=list(o_vals),
            mode="markers+text",
            name=qname,
            text=[d.split("-")[0] for d in labels],
            textposition="top center",
            marker=dict(
                size=14, color=colors[qname],
                line=dict(width=1, color="#fff"),
                symbol="circle",
            ),
            textfont=dict(size=10, color="#1a202c"),
            hovertemplate="<b>%{text}</b><br>自评: %{x:.2f}<br>他评: %{y:.2f}<extra></extra>",
        ))

    # 阈值参考线
    fig.add_hline(y=_get_other_threshold(level), line=dict(color="#718096", width=1, dash="dash"),
                  annotation_text=f"他评阈值={_get_other_threshold(level)}",
                  annotation_position="top right")
    fig.add_vline(x=JOHARI_THRESHOLD_SELF, line=dict(color="#718096", width=1, dash="dash"),
                  annotation_text=f"自评阈值={JOHARI_THRESHOLD_SELF}",
                  annotation_position="top right")
    # 对角线 y=x
    fig.add_trace(go.Scatter(
        x=[1, 5], y=[1, 5], mode="lines",
        line=dict(color="#cbd5e0", width=1, dash="dot"),
        showlegend=False, hoverinfo="skip",
    ))

    fig.update_layout(
        xaxis=dict(range=[3.0, 5.0], dtick=0.5, title="自评", gridcolor="#e2e8f0"),
        yaxis=dict(range=[3.0, 5.0], dtick=0.5, title="他评", gridcolor="#e2e8f0"),
        shapes=bg_shapes,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
        margin=dict(l=50, r=30, t=10, b=60),
        height=520,
        paper_bgcolor="rgba(0,0,0,0)",
        autosize=True,
        font=dict(family="PingFang SC, Microsoft YaHei, sans-serif"),
    )
    return fig.to_html(include_plotlyjs=False, full_html=False, config={"displayModeBar": True, "responsive": True, "scrollZoom": True, "modeBarButtonsToRemove": ["toImage", "sendDataToCloud", "zoomIn2d", "zoomOut2d", "autoScale2d", "hoverClosestCartesian", "hoverCompareCartesian"], "modeBarButtonsToAdd": ["resetScale2d"], "displaylogo": False})


def _safe(val):
# ── 数据提取 ──────────────────────────────────────────────────────

    """NaN → None"""
    if isinstance(val, float) and np.isnan(val):
        return None
    return val


def extract_person(row: pd.Series, norms: dict, questionnaire_items: list[dict]) -> dict:
    """从一行数据提取模板上下文。"""
    ctx = {}

    # 基本信息
    ctx["user_name"] = str(row.iloc[0])
    ctx["user_id"] = str(row.iloc[0])
    ctx["user_level"] = str(row.iloc[1])
    ctx["user_level_label"] = LEVEL_LABELS.get(str(row.iloc[1]), str(row.iloc[1]))

    demo_cols = list(row.index[2:9])
    demo_keys = ["tenure", "age", "direct_reports", "last_promotion",
                 "sequence", "sub_sequence", "performance"]
    for k, col in zip(demo_keys, demo_cols):
        v = row.get(col)
        ctx[f"user_{k}"] = v if pd.notna(v) else ""

    # 一级组织（使用二级序列字段作为组织归属信息）
    ctx["user_org"] = str(row.iloc[7]) if pd.notna(row.iloc[7]) else ""
    # 维度名（常模文件中的键）
    norm_keys = list(norms.keys())

    # 提取各源评分
    self_scores, superior_scores, peer_scores, subordinate_scores, other_scores = [], [], [], [], []
    for dim in DIM_NAMES:
        self_scores.append(_safe(row.get(f"本人-{dim}")))
        superior_scores.append(_safe(row.get(f"上级-{dim}")))
        peer_scores.append(_safe(row.get(f"协同方-{dim}")))
        subordinate_scores.append(_safe(row.get(f"下级-{dim}")))
        other_scores.append(_safe(row.get(f"他评-{dim}")))

    ctx["dimensions"] = DIM_NAMES
    ctx["self_scores"] = self_scores
    ctx["superior_scores"] = superior_scores
    ctx["peer_scores"] = peer_scores
    ctx["subordinate_scores"] = subordinate_scores
    ctx["other_scores"] = other_scores

    # 常模值
    ctx["norm_means"] = [round(norms.get(dim, {}).get("other", {}).get("M", np.nan), 2)
                         for dim in DIM_NAMES]
    ctx["norm_p25"] = [round(norms.get(dim, {}).get("other", {}).get("P25", np.nan), 2)
                       for dim in DIM_NAMES]
    ctx["norm_p75"] = [round(norms.get(dim, {}).get("other", {}).get("P75", np.nan), 2)
                       for dim in DIM_NAMES]
    ctx["norm_other_p50"] = [round(norms.get(dim, {}).get("other", {}).get("P50", np.nan), 2)
                             for dim in DIM_NAMES]
    ctx["norm_self_p50"] = [round(norms.get(dim, {}).get("self", {}).get("P50", np.nan), 2)
                            for dim in DIM_NAMES]

    # 总体均值
    ctx["self_overall_mean"] = np.nanmean([s for s in self_scores if s is not None]) if any(s is not None for s in self_scores) else 0
    ctx["other_overall_mean"] = np.nanmean([o for o in other_scores if o is not None]) if any(o is not None for o in other_scores) else 0
    ctx["self_other_gap"] = ctx["self_overall_mean"] - ctx["other_overall_mean"]
    norm_overall = np.nanmean(ctx["norm_other_p50"])
    ctx["norm_self_p50_overall"] = np.nanmean(ctx["norm_self_p50"])
    ctx["norm_other_p50_overall"] = norm_overall

    # 评价参与度
    rater_keys = {"上级": "上级", "协同方": "协同方", "下级": "下级"}
    ctx["rater_counts"] = {}
    for rk in rater_keys:
        # 判断是否有该源数据：看第一个维度是否有分
        key = f"{rk}-{DIM_NAMES[0]}"
        ctx["rater_counts"][rk] = 1 if _safe(row.get(key)) is not None else 0
    ctx["rater_total"] = sum(ctx["rater_counts"].values())
    # Override rater counts with actual comment data (before _build_item_tables)
    _rc_comment_file = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "comments" / f"{str(row.iloc[0])}.json"
    if _rc_comment_file.exists():
        try:
            with open(_rc_comment_file, "r", encoding="utf-8") as _rcf:
                _rcdata = json.load(_rcf)
            _rcstats = _rcdata.get("stats", {})
            if _rcstats.get("有效评价人数"):
                ctx["rater_total"] = _rcstats["有效评价人数"]
            for _rsk in ["上级", "协同方", "下级"]:
                if _rsk in _rcstats.get("来源分布", {}):
                    ctx["rater_counts"][_rsk] = _rcstats["来源分布"][_rsk]
        except Exception:
            pass

    # 优势 / 待发展维度
    strength_dims, development_dims = [], []
    for i, dim in enumerate(DIM_NAMES):
        other_val = other_scores[i]
        norm_p50 = ctx["norm_other_p50"][i]
        if other_val is not None and not np.isnan(other_val) and norm_p50 is not None and not np.isnan(norm_p50):
            if other_val >= norm_p50:
                strength_dims.append(dim)
            else:
                development_dims.append(dim)
    ctx["strength_dims"] = strength_dims
    ctx["development_dims"] = development_dims

    # 最大差距
    gaps = []
    for i, dim in enumerate(DIM_NAMES):
        s = self_scores[i]
        o = other_scores[i]
        if s is not None and o is not None and not np.isnan(s) and not np.isnan(o):
            gaps.append((abs(s - o), dim, s - o))
    if gaps:
        gaps.sort(key=lambda x: x[0], reverse=True)
        ctx["max_gap_dim"] = gaps[0][1]
        ctx["max_gap_value"] = gaps[0][2]  # 有符号差距
    else:
        ctx["max_gap_dim"] = None
        ctx["max_gap_value"] = 0

    # 评分模式分析
    pattern_type, pattern_desc = _analyze_rating_pattern(self_scores, superior_scores, peer_scores, subordinate_scores)
    ctx["rating_pattern_type"] = pattern_type
    ctx["rating_pattern_desc"] = pattern_desc

    # 最大分歧维度
    mv, md = _find_max_divergence(superior_scores, peer_scores, subordinate_scores)
    ctx["max_divergence_dim"] = md
    ctx["max_divergence_value"] = mv

    # ── 乔哈里视窗 ──
    johari = {}
    for qname, qkey, qclass, qcolor, qdesc, qadv in [
        ("优势区", "q1", "strength", "#38a169",
         "那些您认为自己非常擅长、且他人也非常认可的能力。",
         "更多的运用这些能力，思考它们如何帮助您提升待发展区的能力，以及是否可以在这些领域为他人提供指导。"),
        ("潜能区", "q2", "potential", "#3182ce",
         "那些他人非常认可、但您本人认为有所欠缺的能力。",
         "更多的运用这些能力，思考如何令它们取得更大的效果，是否可以收集更多的反馈以提升自己的信心。"),
        ("盲区", "q3", "blind", "#dd6b20",
         "那些您认为自己非常擅长、但他人认为有所欠缺的能力。盲区之所以危险，恰恰是因为您以前不知道它存在，也就没有机会修正。",
         ""),
        ("待发展区", "q4", "dev", "#e53e3e",
         "那些您自己和他人都认为有所欠缺的能力。",
         ""),
    ]:
        dims_in_quadrant = []
        for i, dim in enumerate(DIM_NAMES):
            s = self_scores[i]
            o = other_scores[i]
            if s is None or np.isnan(s) or o is None or np.isnan(o):
                continue
            ot = _get_other_threshold(ctx["user_level"])
            in_q = (
                (s >= JOHARI_THRESHOLD_SELF and o >= ot and qname == "优势区") or
                (s < JOHARI_THRESHOLD_SELF and o >= ot and qname == "潜能区") or
                (s >= JOHARI_THRESHOLD_SELF and o < ot and qname == "盲区") or
                (s < JOHARI_THRESHOLD_SELF and o < ot and qname == "待发展区")
            )
            if in_q:
                dims_in_quadrant.append(dim)
        johari[qname] = {
            "dims": dims_in_quadrant,
            "color": qcolor,
            "css_class": qclass,
            "tag_class": qclass,
            "description": qdesc,
            "advice": qadv,
        }
    ctx["johari_quadrants"] = johari

    # 乔哈里整体解读
    open_count = len(johari["优势区"]["dims"])
    dev_count = len(johari["待发展区"]["dims"])
    potential_count = len(johari["潜能区"]["dims"])
    blind_count = len(johari["盲区"]["dims"])
    ctx["johari_summary"] = {
        "open_count": open_count,
        "open_summary": f"您在 {open_count} 个维度上获得自他一致的认可"
                        + (f"，主要集中在 {', '.join(johari['优势区']['dims'])}" if open_count > 0 else ""),
        "dev_count": dev_count,
        "dev_summary": f"将 {', '.join(johari['待发展区']['dims'])} 列为首要发展重点" if dev_count > 0 else "暂无共识性待发展维度",
        "overall_takeaway": (
            f"整体来看，{open_count}/7 维度进入优势区，{potential_count}/7 位于潜能区，"
            f"{blind_count}/7 处于盲区，{dev_count}/7 需要在发展区重点关注。"
        ),
    }

    # ── 条目级数据 ──
    ctx["item_tables"] = _build_item_tables(row, questionnaire_items, norms, ctx.get("rater_counts", {}))

    # ── 评语 ──
    comment_labels = ["优势评语", "发展建议", "其他建议"]
    has_comments = False
    raw_comments = OrderedDict()
    for label in comment_labels:
        raw = row.get(label, "")
        if isinstance(raw, str) and raw.strip():
            parts = [p.strip() for p in raw.split("|||") if p.strip()]
            if parts:
                has_comments = True
                raw_comments[label] = parts
    ctx["has_comments"] = has_comments
    ctx["raw_comments_list"] = raw_comments  # 简单列表，来源标记待后续编码完成后完善
    # 评语按类型分组（附录3.2展示用）
    # 清除评语前缀（如 "1、", "2."）和无效数据（"无", "暂无"）
    import re as _re
    def _clean(xx):
        t = xx.strip()
        i = 0
        while i < len(t) and (t[i].isdigit() or t[i] in (chr(46), chr(0x3001), chr(32), chr(0xFF09))):
            i += 1
        t = t[i:].strip()
        return t if t and t not in (chr(26080), chr(26242), chr(45), chr(8212), chr(0x201C), chr(0x201D)) else None
    ctx["appendix_comments_strength"] = [c for c in [_clean(x) for x in raw_comments.get("优势评语", [])] if c]
    ctx["appendix_comments_dev"] = [c for c in [_clean(x) for x in raw_comments.get("发展建议", [])] if c]
    ctx["appendix_has_comments"] = len(ctx["appendix_comments_strength"]) > 0 or len(ctx["appendix_comments_dev"]) > 0
    # 评价来源分组评语（附录3.2展示用）
    ctx["appendix_comments_by_source"] = []
    _person_id = ctx["user_id"]
    _comment_file = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "comments" / f"{_person_id}.json"
    if _comment_file.exists():
        try:
            with open(_comment_file, "r", encoding="utf-8") as _cf:
                _cdata = json.load(_cf)
            # Override rater counts with actual comment stats
            _stats = _cdata.get("stats", {})
            if _stats.get("有效评价人数"):
                ctx["rater_total"] = _stats["有效评价人数"]
            _src_dist = _stats.get("来源分布", {})
            for _sk in ["上级", "协同方", "下级"]:
                if _sk in _src_dist:
                    ctx["rater_counts"][_sk] = _src_dist[_sk]
            _source_label_map = {"上级": "上级评价", "协同方": "协同方评价", "下级": "下级评价"}
            for _stype in ["优势评语", "发展建议"]:
                if _stype not in _cdata:
                    continue
                for _src, _entries in _cdata[_stype].items():
                    if _src not in _source_label_map:
                        continue
                    _cleaned = []
                    for _e in _entries:
                        _t = _e["text"]
                        _c = _t.strip()
                        _i = 0
                        while _i < len(_c) and (_c[_i].isdigit() or _c[_i] in (chr(46), chr(0x3001), chr(32), chr(0xFF09))):
                            _i += 1
                        _c = _c[_i:].strip()
                        if _c and _c not in (chr(26080), chr(26242), chr(45), chr(8212), chr(0x201C), chr(0x201D)):
                            _cleaned.append(_c)
                    if _cleaned:
                        ctx["appendix_comments_by_source"].append({
                            "label": f"[{_source_label_map[_src]}] {_stype}",
                            "comments": _cleaned,
                        })
        except Exception:
            pass

    # ── 评语编码数据 ──
    person_id = ctx["user_id"]
    enc_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "comments" / f"{person_id}_encoded.json"
    if enc_path.exists():
        try:
            with open(enc_path, "r", encoding="utf-8") as _ef:
                _enc = json.load(_ef)
            ctx["comment_profile"] = _enc.get("profile_text", "")
            _axial = _enc.get("axial_codes", {})
            _strength = _axial.get("strength", [])
            _dev = _axial.get("development", [])
            ctx["comment_axial_codes"] = []
            if _strength:
                ctx["comment_axial_codes"].append({
                    "label": "优势项主题",
                    "codes": [{"name": s["name"], "count": s["count"],
                               "source_distribution": s.get("source_distribution",""),
                               "rep_quote": s.get("rep_quote","")} for s in _strength]
                })
            if _dev:
                ctx["comment_axial_codes"].append({
                    "label": "待发展项主题",
                    "codes": [{"name": s["name"], "count": s["count"],
                               "source_distribution": s.get("source_distribution",""),
                               "rep_quote": s.get("rep_quote","")} for s in _dev]
                })
        except Exception:
            ctx["comment_profile"] = ""
            ctx["comment_axial_codes"] = []
    else:
        ctx["comment_profile"] = ""
        ctx["comment_axial_codes"] = []

    return ctx


def _analyze_rating_pattern(self_scores, superior_scores, peer_scores, subordinate_scores):
    """检测评分模式。"""
    sup_valid = [s for s in superior_scores if s is not None and not np.isnan(s)]
    sub_valid = [s for s in subordinate_scores if s is not None and not np.isnan(s)]

    if sup_valid and sub_valid:
        sup_mean = np.mean(sup_valid)
        sub_mean = np.mean(sub_valid)
        if sub_mean - sup_mean > 0.3:
            return "sub_generous", "下级评分显著高于上级（差距 > 0.3），可能反映了对下属的关注度较高，但上级视角尚需加强。"
        if sup_mean - sub_mean > 0.3:
            return "sup_strict", "上级评分显著高于下级，可能反映了较好的向上管理能力，但在团队日常管理上有提升空间。"
    return "balanced", "各评价源评分模式较为均衡，不存在极端差异。"


def _find_max_divergence(superior, peer, subordinate):
    """找出各源评分分歧最大的维度。"""
    max_div, max_dim = 0, None
    for i, dim in enumerate(DIM_NAMES):
        vals = [v for v in [superior[i], peer[i], subordinate[i]]
                if v is not None and not np.isnan(v)]
        if len(vals) >= 2:
            spread = max(vals) - min(vals)
            if spread > max_div:
                max_div = spread
                max_dim = dim
    return round(max_div, 2), max_dim


def _build_item_tables(row: pd.Series, questionnaire_items: list[dict], norms: dict, rater_counts: dict | None = None) -> list[dict]:
    """构建条目级得分表数据。"""
    # 将问卷条目按维度分组
    dim_items = {d: [] for d in DIM_NAMES}
    for qitem in questionnaire_items:
        dim = qitem.get("dimension", "")
        if dim in dim_items and qitem["text"]:
            dim_items[dim].append(qitem["text"])

    tables = []
    for dim in DIM_NAMES:
        items = dim_items[dim]
        if not items:
            continue

        peer_na = dim in ("数智变革-加强数字应用", "发展组织-带兵打仗")

        entries = []
        for idx, text in enumerate(items):
            self_val = _safe(row.get(f"本人-{dim}"))
            sup = _safe(row.get(f"上级-{dim}"))
            peer = None if peer_na else _safe(row.get(f"协同方-{dim}"))
            sub = _safe(row.get(f"下级-{dim}"))

            entries.append({
                "no": idx + 1,
                "text": text,
                "本人": self_val,
                "上级": sup,
                "协同方": peer,
                "协同方_na": peer_na,
                "下级": sub,
            })

        # counts
        counts = {}
        for src in RATER_SOURCES:
            col = f"{src}-{dim}"
            v = row.get(col)
            has_data = v is not None and not (isinstance(v, float) and np.isnan(v))
            counts[src] = (rater_counts or {}).get(src, 1) if has_data else 0

        tables.append({
            "dimension": dim,
            "rows": entries,
            "counts": counts,
        })
    return tables


# ── 报告生成 ──────────────────────────────────────────────────────

CHART_NAMES = ["radar_chart_html", "line_chart_html", "johari_chart_html"]


def generate_report(ctx: dict, output_path: Path, template_name: str = "individual_report.html"):
    """渲染并保存 HTML 报告。"""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR / "reports")))
    env.trim_blocks = True
    env.globals["CJK_NUMS"] = ["一", "二", "三", "四", "五", "六", "七"]
    env.globals["chr"] = chr
    env.lstrip_blocks = True

    template = env.get_template(template_name)
    html = template.render(**ctx)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"  Report saved: {output_path}")


# ── 主入口 ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="生成 360° 领导力反馈个体报告")
    parser.add_argument("--user_id", type=str, default=None, help="被评价人工号")
    parser.add_argument("--level", type=str, default="L4", choices=["L3", "L4"], help="层级")
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR), help="输出目录")
    parser.add_argument("--list", action="store_true", help="列出该层级下的所有人")
    args = parser.parse_args()

    print(f"Loading {args.level} data...")
    df = load_data(args.level)

    user_col = df.columns[0]
    all_users = sorted(df[user_col].astype(str).unique())

    if args.list:
        print(f"Found {len(all_users)} users in {args.level}:")
        for uid in all_users[:20]:
            print(f"  {uid}")
        if len(all_users) > 20:
            print(f"  ... and {len(all_users) - 20} more")
        return

    if args.user_id:
        if args.user_id not in all_users:
            print(f"User {args.user_id} not found. Available: {all_users[:10]}")
            return
        target_users = [args.user_id]
    else:
        # 默认取前 1 人演示
        target_users = all_users[:1]
        print(f"No user_id specified. Using first user: {target_users[0]}")

    print(f"Loading norms for {args.level}...")
    norms = load_norms(args.level)

    print(f"Loading questionnaire for {args.level}...")
    qitems = load_questionnaire(args.level)

    output_dir = Path(args.output_dir)

    for uid in target_users:
        print(f"\nGenerating report for {uid}...")
        user_df = load_data(args.level, uid)
        row = user_df.iloc[0]

        ctx = extract_person(row, norms, qitems)
        ctx["johari_threshold_self"] = JOHARI_THRESHOLD_SELF
        ctx["johari_threshold_other"] = _get_other_threshold(args.level)

        # 报告元信息
        ctx["report_title"] = "领导力360°反馈报告"
        ctx["report_subtitle"] = f"{args.level} 基层管理者 · 2026年度"
        ctx["report_date"] = "2026年7月"
        ctx["report_year"] = "2026"
        ctx["foreword_html"] = (
            "<p>本报告基于2026年度360°领导力评估数据生成。360°评估通过收集被评价人本人、上级、协同方、下级"
            "四个维度的反馈，提供多维度的领导力画像，帮助管理者了解自身优势与待发展领域。</p>"
            "<p>评估涵盖 <strong>3大领域</strong>（驱动业务、组织建设、文化旗手）下的 <strong>7个领导力要素</strong>，"
            "采用 Likert 5点量表（1=远低于期望，3=符合期望，5=远超期望）。</p>"
            "<p>报告中使用了 <strong>乔哈里视窗</strong>（Johari Window）框架来分析自评与他评的认知差异，"
            "帮助您识别<strong>优势区</strong>（自他共识的优势）、<strong>潜能区</strong>（他人认可的潜在优势）、"
            "<strong>盲区</strong>（自评高于他评的维度）和<strong>待发展区</strong>（自他共识的提升方向）。</p>"
            "<p><strong>报告阅读提示</strong>：建议按章节顺序阅读，重点关注第2.3节乔哈里视窗的象限分析"
            "和第2.5节的发展建议。您可以选择性地查看附录中的条目级得分和评语原文。</p>"
        )

        # 生成图表
        print("  Generating charts...")
        # 生成叙事文本
        print("  Generating narratives...")
        ctx["narrative_21_html"] = narrative.narrative_21(ctx)
        ctx["narrative_22_html"] = narrative.narrative_22(ctx)
        ctx["narrative_23_opening_html"] = narrative.narrative_23_opening(ctx)
        ctx["narrative_24_intro_html"] = narrative.narrative_24_intro(ctx)
        ctx["narrative_25_closing_html"] = narrative.narrative_25_closing()
        # Development suggestions
        dev_section = get_development_section(uid)
        ctx["dev_section"] = dev_section
        ctx["has_dev_section"] = len(dev_section.get("dimensions", [])) > 0
        ctx["level"] = args.level
        ctx["norm_desc"] = narrative.narrative_norm_desc(ctx)
        ctx["excluded_dim_note"] = narrative.narrative_excluded_dim_note(ctx)

        ctx["radar_chart_html"] = make_radar_chart(
            DIM_NAMES, ctx["self_scores"], ctx["other_scores"], ctx["norm_means"])
        ctx["line_chart_html"] = make_line_chart(
            DIM_NAMES, ctx["self_scores"], ctx["superior_scores"],
            ctx["peer_scores"], ctx["subordinate_scores"], ctx["other_scores"])
        ctx["johari_chart_html"] = make_johari_chart(
            DIM_NAMES, ctx["self_scores"], ctx["other_scores"], level=args.level)

        out_path = output_dir / args.level / f"report_{uid}.html"
        generate_report(ctx, out_path)
        # Run QA automatically
        try:
            qa_ctx = make_qa_ctx(ctx)
            qa_path = output_dir / args.level / f"qa_{uid}.md"
            generate_qa_report(qa_ctx, qa_path)
        except Exception as e:
            print(f"  QA check failed: {e}")

    print("\nDone.")


def make_qa_ctx(ctx: dict) -> dict:
    """从 ctx 提取 QA 检查所需的关键字段。"""
    qa = {}
    qa["user_id"] = ctx.get("user_id")
    qa["user_level"] = ctx.get("user_level")
    qa["has_radar"] = bool(ctx.get("radar_chart_html"))
    qa["has_line"] = bool(ctx.get("line_chart_html"))
    qa["has_johari"] = bool(ctx.get("johari_chart_html"))
    qa["has_narrative_21"] = bool(ctx.get("narrative_21_html"))
    qa["has_narrative_22"] = bool(ctx.get("narrative_22_html"))
    qa["has_dev_section"] = ctx.get("has_dev_section", False)
    qa["has_comment_profile"] = bool(ctx.get("comment_profile"))
    qa["self_mean"] = float(ctx.get("self_overall_mean", 0))
    qa["other_mean"] = float(ctx.get("other_overall_mean", 0))
    qa["rater_total"] = ctx.get("rater_total", 0)
    counts = ctx.get("rater_counts", {})
    qa["rater_source_count"] = sum(1 for v in counts.values() if v > 0)
    qa["dimension_count"] = len(ctx.get("dimensions", []))
    qa["johari_quadrant_dims"] = sum(
        len(q.get("dims", [])) for q in ctx.get("johari_quadrants", {}).values()
    )
    n21 = ctx.get("narrative_21_html", "")
    qa["has_self_perspective"] = "您眼中的自己" in n21
    qa["has_other_perspective"] = "他人眼中的您" in n21
    qa["section_count"] = sum([
        bool(ctx.get(f"narrative_2{i}_html")) for i in [1, 2]
    ]) + bool(ctx.get("narrative_23_opening_html"))
    return qa


def generate_qa_report(qa_ctx: dict, output_path: Path):
    """生成 QA 检查报告（Markdown）。"""
    checks = [
        ("人员信息完整", bool(qa_ctx.get("user_id")), "user_id"),
        ("层级翻译存在", bool(qa_ctx.get("user_level")), "user_level"),
        ("雷达图存在", qa_ctx.get("has_radar", False), "radar_chart_html"),
        ("折线图存在", qa_ctx.get("has_line", False), "line_chart_html"),
        ("乔哈里图存在", qa_ctx.get("has_johari", False), "johari_chart_html"),
        ("2.1叙事存在", qa_ctx.get("has_narrative_21", False), "narrative_21_html"),
        ("2.2叙事存在", qa_ctx.get("has_narrative_22", False), "narrative_22_html"),
        ("2.1含‘您眼中的自己’", qa_ctx.get("has_self_perspective", False), ""),
        ("2.1含‘他人眼中的您’", qa_ctx.get("has_other_perspective", False), ""),
        ("发展建议存在", qa_ctx.get("has_dev_section", False), "dev_section"),
        ("常模维度数=7", qa_ctx.get("dimension_count", 0) == 7, ""),
        ("自评均值>0", qa_ctx.get("self_mean", 0) > 0, ""),
        ("他评均值>0", qa_ctx.get("other_mean", 0) > 0, ""),
        ("评价参与度>0", qa_ctx.get("rater_total", 0) > 0, ""),
        ("评价人数≥来源数", qa_ctx.get("rater_total", 0) >= qa_ctx.get("rater_source_count", 0), ""),
        ("评价人数>来源数", qa_ctx.get("rater_total", 0) > qa_ctx.get("rater_source_count", 0), ""),
        ("乔哈里象限有维度分布", qa_ctx.get("johari_quadrant_dims", 0) > 0, ""),
    ]

    lines_out = ["# 报告 QA 检查结果", "", f"检查时间: 2026-07-21", f"受检人: {qa_ctx.get("user_id", "N/A")}", ""]
    lines_out.append("## 检查项")
    lines_out.append("")
    lines_out.append("| 序号 | 检查项 | 结果 | 字段 |")
    lines_out.append("|------|--------|------|------|")
    passed = 0
    for idx, (name, ok, field) in enumerate(checks, 1):
        status = "✅ 通过" if ok else "❌ 未通过"
        if ok:
            passed += 1
        lines_out.append(f"| {idx} | {name} | {status} | {field} |")
    lines_out.append("")
    lines_out.append(f"**总分**: {passed}/{len(checks)}")
    lines_out.append("")
    if passed == len(checks):
        lines_out.append("> 所有检查项通过。")
    else:
        lines_out.append("> 存在未通过项，请检查对应字段。")

    report = "\n".join(lines_out)
    output_path.write_text(report, encoding="utf-8")
    print(f"  QA report saved: {output_path}")
    return output_path


if __name__ == "__main__":
    main()
