# -*- coding: utf-8 -*-
"""叙事层：将证据包转化为有温度的中文叙述文本。

架构：分析层（generate_report.py 中的 extract_person）产出上下文 ctx，
叙事层各函数从 ctx 中提取所需字段，生成 HTML 段落文本。
后续可替换为 LLM 通路（保留相同函数签名）。
"""
from __future__ import annotations
import numpy as np

DIM_NAMES = [
    "战略思维-科学决策",
    "创新引领-持续精进",
    "全球视野-管理复杂情况",
    "客户导向-珍视客户",
    "数智变革-加强数字应用",
    "发展组织-带兵打仗",
    "追求卓越-高效执行",
]

# ── 辅助 ──────────────────────────────────────────────────────────

def _clean(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return val

def _dim_score_pairs(ctx, key):
    """从 ctx 提取维度-分数对，过滤无效值。"""
    dims = ctx.get("dimensions", DIM_NAMES)
    scores = ctx.get(key, [])
    pairs = []
    for i, d in enumerate(dims):
        v = _clean(scores[i] if i < len(scores) else None)
        if v is not None:
            pairs.append((d, v))
    return pairs


# ── 2.1 七维度整体评分 ──────────────────────────────────────────

GAP_SIG = 0.15   # 维度级显著偏差阈值
GAP_MEAN = 0.25  # 整体风格分类阈值
DIVERGE_TH = 0.25  # 协同方-下级分歧阈值

GAP_SIG = 0.15   # 维度级显著偏差阈值
GAP_MEAN = 0.25  # 整体风格分类阈值

def narrative_21(ctx) -> str:
    """生成 2.1 节叙述：您眼中的自己 -> 他人眼中的您 -> 差异（4-branch 风格感知版）。"""
    dims = ctx.get("dimensions", DIM_NAMES)

    self_pairs = _dim_score_pairs(ctx, "self_scores")
    other_pairs = _dim_score_pairs(ctx, "other_scores")
    if not self_pairs or not other_pairs:
        return ""

    self_pairs.sort(key=lambda x: x[1], reverse=True)
    other_pairs.sort(key=lambda x: x[1], reverse=True)

    # 计算维度级 gap
    dim_gaps = []
    for i, d in enumerate(dims):
        s = _clean(ctx.get("self_scores", [None] * 7)[i])
        o = _clean(ctx.get("other_scores", [None] * 7)[i])
        if s is not None and o is not None:
            dim_gaps.append((d, s - o, abs(s - o)))

    # 风格分类
    n_above_sig = sum(1 for _, g, _ in dim_gaps if g > GAP_SIG)
    n_below_sig = sum(1 for _, g, _ in dim_gaps if g < -GAP_SIG)
    gap_val = ctx.get("self_other_gap", 0)

    if n_above_sig >= 2 and n_below_sig >= 2:
        style = "mixed"
    elif gap_val > GAP_MEAN:
        style = "self_enhancing"
    elif gap_val < -GAP_MEAN:
        style = "self_effacing"
    else:
        style = "aligned"

    parts = []

    # --- 您眼中的自己 ---
    top2 = self_pairs[:2]
    bot = self_pairs[-1]
    parts.append(
        f'<p><strong>您眼中的自己</strong><br>'
        f'根据自评，您在 {len(dims)} 个领导力要素中，认为 '
        f'<strong>{top2[0][0]}、{top2[1][0]}</strong> 是自己的核心优势'
        f'（自评 {top2[0][1]:.2f}、{top2[1][1]:.2f} 分），'
        f'而 <strong>{bot[0]}</strong> 等方面则有待进一步提升。</p>'
    )

    # --- 他人眼中的您 ---
    other_top2 = other_pairs[:2]
    parts.append(
        f'<p><strong>他人眼中的您</strong><br>'
        f'在他人的评价中，基于群体<strong>常模</strong><sup style="color:#64748b;font-size:.72rem;">[1]</sup>'
        f'，<strong>{other_top2[0][0]}、{other_top2[1][0]}</strong>'
        f'是被广泛认可的优势领域。</p>'
    )

    # --- 与自评相比（风格分支） ---
    if style == "mixed":
        high2 = sorted([(d, g, a) for d, g, a in dim_gaps if g > 0],
                       key=lambda x: x[2], reverse=True)[:2]
        low2 = sorted([(d, g, a) for d, g, a in dim_gaps if g < 0],
                       key=lambda x: x[2], reverse=True)[:2]
        parts.append(
            f'<p><strong>与自评相比</strong><br>'
            f'您在不同维度上的自我认知呈现出一定的差异——'
            f'在 <strong>{n_above_sig}</strong> 个维度上，您的自评高于他人评价；'
            f'同时在 <strong>{n_below_sig}</strong> 个维度上，您的自评低于他人评价。</p>'
            f'<p>其中，<strong>{high2[0][0]}</strong>（相差 {high2[0][2]:.2f} 分）'
            f'和 <strong>{high2[1][0]}</strong>（相差 {high2[1][2]:.2f} 分）的差距较为突出，'
            f'这一差异可能提示——在这些方面，您的积极意图或付出的努力对他人而言并不完全可见，'
            f'或是他人对您有着更高的期望或要求。</p>'
            f'<p>而在 <strong>{low2[0][0]}</strong>（相差 {low2[0][2]:.2f} 分）'
            f'和 <strong>{low2[1][0]}</strong>（相差 {low2[1][2]:.2f} 分）方面，'
            f'您对自己的评价较为严格，这在一定程度上说明您在这些方面对他人的影响较为可见。</p>'
            f'<p>您还可以从下一节不同评价源评分的对比，'
            f'了解您在不同群体眼中的优劣势情况。</p>'
        )
    elif style == "self_enhancing":
        high2 = sorted([(d, g, a) for d, g, a in dim_gaps if g > 0],
                       key=lambda x: x[2], reverse=True)[:2]
        parts.append(
            f'<p><strong>与自评相比</strong><br>'
            f'您对于自身的领导能力有较强的自信——您的自评在 '
            f'<strong>{n_above_sig}/7</strong> 个维度上高于他人对您的评价。</p>'
            f'<p>其中，<strong>{high2[0][0]}</strong>（相差 {high2[0][2]:.2f} 分，自评高于他评）、'
            f'<strong>{high2[1][0]}</strong>（相差 {high2[1][2]:.2f} 分，自评高于他评）的差距较为明显。'
            f'这一差异可能提示——在这些方面，您的积极意图或付出的努力对他人而言并不完全可见，'
            f'或是他人对您有着更高的期望或要求。</p>'
            f'<p>您还可以从下一节不同评价源评分的对比，'
            f'了解您在不同群体眼中的优劣势情况。</p>'
        )
    elif style == "self_effacing":
        low2 = sorted([(d, g, a) for d, g, a in dim_gaps if g < 0],
                      key=lambda x: x[2])[:2]
        n_prefix = "全部 " if n_below_sig == 7 else ""
        parts.append(
            f'<p><strong>与自评相比</strong><br>'
            f'您对自己要求较高，自我评估较为严格——您的自评在 '
            f'<strong>{n_prefix}{n_below_sig}/7</strong> 个维度上低于他人对您的评价。</p>'
            f'<p>其中，<strong>{low2[0][0]}</strong>（相差 {low2[0][2]:.2f} 分）'
            f'和 <strong>{low2[1][0]}</strong>（相差 {low2[1][2]:.2f} 分）是自评与他评分差最小的两个方面。'
            f'这在一定程度上说明，您在这两方面对他人的影响较为可见，'
            f'有助于您建立对自身优势的认知与信心。</p>'
            f'<p>您还可以从下一节不同评价源评分的对比，'
            f'了解您在不同群体眼中的优劣势情况。</p>'
        )
    else:  # aligned
        aligned_dims = [(d, a) for d, g, a in dim_gaps if a <= 0.10]
        parts.append(
            f'<p><strong>与自评相比</strong><br>'
            f'您有着较为清晰且良好的自我认知——您的自评与他评在整体上较为接近。</p>'
        )
        if aligned_dims:
            parts.append(
                f'<p>其中在 <strong>{aligned_dims[0][0]}、{aligned_dims[1][0]}</strong> 等方面，'
                f'自我认知与他人观察尤为吻合。'
                f'一方面它可能是您真诚领导风格的体现，'
                f'另一方面也说明您与相关方有着相对高频的互动，'
                f'更有可能形成对您个人风格的清晰认知。</p>'
            )
        parts.append(
            f'<p>您还可以从下一节不同评价源评分的对比，'
            f'了解您在不同群体眼中的优劣势情况。</p>'
        )

    # --- 自评与他评的总体差异 ---
    gap_dir = "高于" if gap_val > 0 else "低于"
    max_gap_dim = ctx.get("max_gap_dim", "")
    max_gap_v = abs(ctx.get("max_gap_value", 0))
    self_m = ctx.get("self_overall_mean", 0)
    other_m = ctx.get("other_overall_mean", 0)
    norm_p50 = ctx.get("norm_other_p50_overall", 0)

    if style == "mixed":
        interp = "但这一接近的背后是不同维度上方向各异的差距。"
    elif style == "self_enhancing":
        interp = "这也在一定程度上提示了可能存在的自我认知偏差。"
    elif style == "self_effacing":
        interp = "这在一定程度上反映出您对自己要求较为严格——您对团队和业务的影响与贡献，可能在您的自我评估中被低估了。"
    else:
        interp = "这在一定程度上反映了您对自身领导力表现有着较为准确的判断。"

    max_gap_sentence = (f"其中 <strong>{max_gap_dim}</strong> 的差距最大"
                        f"（相差 {max_gap_v:.2f} 分），") if style != "aligned" else ""

    parts.append(
        f"<p><strong>自评与他评的总体差异</strong><br>"
        f"总体来看，您的自评均值 <strong>{gap_dir}</strong> 他评均值 "
        f"<strong>{abs(gap_val):.2f}</strong> 分"
        f"（自评 {self_m:.2f} 分，他评 {other_m:.2f} 分，"
        f"群体常模他评 P50 为 {norm_p50:.2f} 分）。"
        f"{max_gap_sentence}{interp}"
        f"各维度具体的象限分布和差距详情，将在 2.3 乔哈里视窗中展开。</p>"
    )

    return "\n".join(parts)

ABOVE_EXPLAIN = {
    "战略思维-科学决策": ["您对战略层面的思考深度与前瞻性，可能尚未充分达到上级的期望", "与上级就本领域战略方向进行沟通，可能还不够充分或不够系统", "战略规划与资源配置在上级看来可能更聚焦于短期目标"],
    "创新引领-持续精进": ["在探索新方法、推动改进方面，上级可能期望看到更积极的行动或更显著的效果", "付出的努力可能尚未以充分可感知的方式呈现在上级视野中", "日常执行的负荷可能占据较多精力，创新投入未能满足上级期望"],
    "全球视野-管理复杂情况": ["在应对复杂局面时，上级可能期望您展现出更开阔的视野或更长远的判断", "在跨领域或不确定性环境下的决策应对，可能尚未充分展示"],
    "客户导向-珍视客户": ["在客户需求的深度理解与前瞻响应方面，上级可能期望有更持续的表现", "将客户洞察转化为产品服务改进，可能还需要更有力的推动"],
    "数智变革-加强数字应用": ["在推动数字化工具落地或数据驱动决策方面，上级可能期望看到更主动的作为", "对数字化转型的理解与应用深度，与上级期望可能存在一定差距"],
    "发展组织-带兵打仗": ["在团队建设、人才梯队培养方面，上级可能期望看到更明确的规划或更显著的成果", "在授权的深度与广度上，上级可能认为过于谨慎或不够充分"],
    "追求卓越-高效执行": ["在任务推进的输出质量或过程管理方面，上级可能有更高的要求", "在呈现可量化的阶段性成果或关键节点交付方面，可能还不够清晰"],
}
BELOW_EXPLAIN = {
    "战略思维-科学决策": ["上级比您更广泛地观察到了您在战略思考与决策方面的贡献", "您对自身在战略层面的判断力，可能比上级的感知更为严格"],
    "创新引领-持续精进": ["您推动创新与改进的努力，对上级而言比您自己意识到的更为可见", "您在日常工作中展现的探索精神，可能被自己低估了"],
    "全球视野-管理复杂情况": ["上级对您处理复杂局面的能力有比您自身更高的认可", "您在跨领域协调中的表现，可能给上级留下了比您自己以为更深的印象"],
    "客户导向-珍视客户": ["上级认为您在客户价值方面的投入和成效，超过了您自己的判断", "您对客户需求的理解与响应能力，比您自我评估的更为突出"],
    "数智变革-加强数字应用": ["上级对您在数字化推动方面的努力有更积极的认可", "您在数据驱动决策方面的尝试与成果，可能在自我评估中被低估了"],
    "发展组织-带兵打仗": ["上级比您更充分地看到了您在团队培养与人才发展方面的投入", "您在团队管理方面展现的能力，比您自己认为的更为成熟"],
    "追求卓越-高效执行": ["您在任务推进与结果交付方面的表现，对上级而言比您自己认为的更为可靠", "上级可能对您的执行质量与效率有高于您自身判断的评价"],
}

def _compute_focus_dims(dims, self_scores, other_scores):
    """计算 2.1 风格的焦点维度，供 Part B 使用。"""
    dim_gaps = []
    for i, d in enumerate(dims):
        s = self_scores[i]
        o = other_scores[i]
        if s is not None and o is not None:
            dim_gaps.append((d, s - o, abs(s - o)))
    if not dim_gaps:
        return dims[:2]
    gap_val = np.mean([g for _, g, _ in dim_gaps])
    n_above_sig = sum(1 for _, g, _ in dim_gaps if g > GAP_SIG)
    n_below_sig = sum(1 for _, g, _ in dim_gaps if g < -GAP_SIG)
    if n_above_sig >= 2 and n_below_sig >= 2:
        high = sorted([(d, g, a) for d, g, a in dim_gaps if g > 0], key=lambda x: x[2], reverse=True)[:2]
        low = sorted([(d, g, a) for d, g, a in dim_gaps if g < 0], key=lambda x: x[2], reverse=True)[:2]
        return [high[0][0]] + [low[0][0]]
    elif gap_val > GAP_MEAN:
        high = sorted([(d, g, a) for d, g, a in dim_gaps if g > 0], key=lambda x: x[2], reverse=True)[:2]
        return [d for d, _, _ in high]
    elif gap_val < -GAP_MEAN:
        low = sorted([(d, g, a) for d, g, a in dim_gaps if g < 0], key=lambda x: x[2])[:2]
        return [d for d, _, _ in low]
    else:
        aligned = [(d, a) for d, g, a in dim_gaps if a <= 0.10]
        return [d for d, _ in aligned[:2]] if aligned else dims[:2]

def _classify_superior(dims, self_scores, sup_scores):
    """判定自评-上级的评分模式。"""
    gaps = []
    for i, d in enumerate(dims):
        s = self_scores[i]
        sup = sup_scores[i]
        if s is not None and sup is not None:
            gaps.append((d, s - sup, abs(s - sup)))
    if not gaps:
        return "aligned", []
    n_above = sum(1 for _, g, _ in gaps if g > GAP_SIG)
    n_below = sum(1 for _, g, _ in gaps if g < -GAP_SIG)
    if n_above >= 4:
        top = sorted([(d, g, a) for d, g, a in gaps if g > 0], key=lambda x: x[2], reverse=True)[:2]
        return "self_above", [d for d, _, _ in top]
    elif n_below >= 4:
        top = sorted([(d, g, a) for d, g, a in gaps if g < 0], key=lambda x: x[2], reverse=True)[:2]
        return "self_below", [d for d, _, _ in top]
    elif n_above >= 2 and n_below >= 2:
        high = sorted([(d, g, a) for d, g, a in gaps if g > 0], key=lambda x: x[2], reverse=True)[0]
        low = sorted([(d, g, a) for d, g, a in gaps if g < 0], key=lambda x: x[2], reverse=True)[0]
        return "mixed", [high[0], low[0]]
    else:
        return "aligned", []


def narrative_22(ctx) -> str:
    """生成 2.2 节叙述：各评价来源评分对比（Part A: 本人-上级 + Part B: 协同方-下级锚定焦点维度）。"""
    dims = ctx.get("dimensions", DIM_NAMES)
    self_scores = [_clean(ctx.get("self_scores", [None] * 7)[i]) for i in range(len(dims))]
    sup_scores = [_clean(ctx.get("superior_scores", [None] * 7)[i]) for i in range(len(dims))]
    peer_scores = [_clean(ctx.get("peer_scores", [None] * 7)[i]) for i in range(len(dims))]
    sub_scores = [_clean(ctx.get("subordinate_scores", [None] * 7)[i]) for i in range(len(dims))]

    # 计算聚合他评（用于焦点维度检测）
    other_scores = []
    for i in range(len(dims)):
        vals = [v for v in [sup_scores[i], peer_scores[i], sub_scores[i]] if v is not None]
        other_scores.append(float(np.mean(vals)) if vals else None)

    focus_dims = _compute_focus_dims(dims, self_scores, other_scores)
    parts = []

    # ═══ Part A: 本人与上级 ═══
    ss_style, ss_dims = _classify_superior(dims, self_scores, sup_scores)

    if ss_style == "self_above" and len(ss_dims) >= 2:
        d1, d2 = ss_dims[0], ss_dims[1]
        # 查找具体差距
        g1 = abs(self_scores[dims.index(d1)] - sup_scores[dims.index(d1)])
        g2 = abs(self_scores[dims.index(d2)] - sup_scores[dims.index(d2)])
        exp1 = "\n  * ".join(ABOVE_EXPLAIN.get(d1, [""])[:3])
        exp2 = "\n  * ".join(ABOVE_EXPLAIN.get(d2, [""])[:2])
        parts.append(f'<p><strong>本人与上级的评分差异</strong><br>'
                     f'上级在 <strong>{d1}</strong>（相差 {g1:.2f} 分）和 <strong>{d2}</strong>（相差 {g2:.2f} 分）方面的评分低于您的自评。</p>'
                     f'<p>这可能意味着——</p>'
                     f'<p><strong>{d1}</strong> 方面：<br>  * {exp1}</p>'
                     f'<p><strong>{d2}</strong> 方面：<br>  * {exp2}</p>')

    elif ss_style == "self_below" and len(ss_dims) >= 2:
        d1, d2 = ss_dims[0], ss_dims[1]
        g1 = abs(self_scores[dims.index(d1)] - sup_scores[dims.index(d1)])
        g2 = abs(self_scores[dims.index(d2)] - sup_scores[dims.index(d2)])
        exp1 = "\n  * ".join(BELOW_EXPLAIN.get(d1, [""])[:2])
        exp2 = "\n  * ".join(BELOW_EXPLAIN.get(d2, [""])[:2])
        parts.append(f'<p><strong>本人与上级的评分差异</strong><br>'
                     f'上级在 <strong>{d1}</strong>（相差 {g1:.2f} 分）和 <strong>{d2}</strong>（相差 {g2:.2f} 分）方面的评分高于您的自评。</p>'
                     f'<p>这可能意味着——</p>'
                     f'<p><strong>{d1}</strong> 方面：<br>  * {exp1}</p>'
                     f'<p><strong>{d2}</strong> 方面：<br>  * {exp2}</p>')

    elif ss_style == "mixed" and len(ss_dims) >= 2:
        d_high, d_low = ss_dims[0], ss_dims[1]
        g_high = abs(self_scores[dims.index(d_high)] - sup_scores[dims.index(d_high)])
        g_low = abs(self_scores[dims.index(d_low)] - sup_scores[dims.index(d_low)])
        exp_high = "\n  * ".join(ABOVE_EXPLAIN.get(d_high, [""])[:2])
        exp_low = "\n  * ".join(BELOW_EXPLAIN.get(d_low, [""])[:2])
        # Count above/below
        ss_gaps = [(d, self_scores[i] - sup_scores[i]) for i, d in enumerate(dims) if self_scores[i] is not None and sup_scores[i] is not None]
        na = sum(1 for _, g in ss_gaps if g > GAP_SIG)
        nb = sum(1 for _, g in ss_gaps if g < -GAP_SIG)
        parts.append(f'<p><strong>本人与上级的评分差异</strong><br>'
                     f'您的自评与上级评分在不同维度上方向各异——在 {na} 个维度上您的自评高于上级，'
                     f'在 {nb} 个维度上低于上级。</p>'
                     f'<p>其中，<strong>{d_high}</strong>（相差 {g_high:.2f} 分）方面您的自评高于上级：<br>  * {exp_high}</p>'
                     f'<p>而在 <strong>{d_low}</strong>（相差 {g_low:.2f} 分）方面上级评分高于您的自评：<br>  * {exp_low}</p>')

    else:  # aligned
        parts.append(f'<p><strong>本人与上级的评分差异</strong><br>'
                     f'您的自我评估与上级对您的评估相对一致。这可能意味着您与上级有着相对高频且高质量的互动，'
                     f'双方对您的领导力表现有着较为接近的认知与判断。</p>'
                     f'<p>同时，若角色变化或承担更大的职责，上级对您的期望和要求也会随之发生改变——'
                     f'当前表现出的优势可能成为未来的基线标准。'
                     f'因此，主动对齐新阶段的期望与要求，将帮助您在变化中持续校准方向，'
                     f'保持双方对您领导力表现的共识。</p>')

    # ═══ Part B: 协同方与下级（锚定焦点维度） ═══
    parts.append(f'<p><strong>协同方与下级的评分差异</strong><br>'
                 f'以下进一步拆解协同方与下级在 2.1 所关注维度上的评分差异。</p>')

    found_divergence = False
    processed = []

    for fd in focus_dims:
        i = dims.index(fd)
        p = peer_scores[i]
        s = sub_scores[i]
        if p is None or s is None:
            continue
        gap = round(p - s, 2)
        ga = abs(gap)
        processed.append((fd, gap, ga, p, s))
        if ga >= DIVERGE_TH:
            found_divergence = True
            if gap < 0:  # peer < sub (typical)
                parts.append(f'<p>在 <strong>{fd}</strong> 方面，协同方与下级的评分差异较为明显（相差 {ga:.2f} 分）：'
                             f'协同方评分 {p:.2f} 分，下级评分 {s:.2f} 分。<br>'
                             f'这可能意味着——<br>'
                             f'  * 从互动水平来看：下级在日常工作中与您有更密切的互动，对您在该维度的表现有更持续的观察；'
                             f'而协同方的接触相对有限，评分更多基于项目协作中的片段印象。<br>'
                             f'  * 从期望差异来看：协同方在跨部门协作中更倾向于横向比较与对标，评价视角更为严格；'
                             f'而下级更关注您在日常管理中为他们创造的条件与支持。</p>')
            else:  # peer > sub (atypical)
                parts.append(f'<p>在 <strong>{fd}</strong> 方面，协同方的评分高于下级（相差 {ga:.2f} 分）：'
                             f'协同方评分 {p:.2f} 分，下级评分 {s:.2f} 分。<br>'
                             f'这可能意味着——<br>'
                             f'  * 从行为可见性来看：您在该维度的领导力表现可能在跨团队协作中更为突出，'
                             f'而在面向团队内部时展现相对有限。<br>'
                             f'  * 从互动水平来看：与下级的日常互动中，该维度的相关行为可能尚未以同等强度被感知。</p>')
            break  # 只报告第一个显著分歧

    if not found_divergence:
        if processed:
            pd_names = "、".join(f'「{d}」' for d, _, _, _, _ in processed)
            parts.append(f'<p>在 {pd_names} 方面，协同方与下级的评分较为一致。'
                         f'这说明 2.1 报告中提示的差异主要集中在您与评价者之间，'
                         f'不同评价群体（协同方与下级）之间的内部差异较小，'
                         f'您在不同互动场景下的领导力表现具有较好的整体一致性。</p>')
        else:
            # Fallback: scan all available dims
            all_gaps = []
            for i, d in enumerate(dims):
                p = peer_scores[i]
                s = sub_scores[i]
                if p is not None and s is not None:
                    all_gaps.append((d, round(p-s, 2), abs(round(p-s, 2)), p, s))
            if all_gaps:
                all_gaps.sort(key=lambda x: x[2], reverse=True)
                d, gap, ga, p, s = all_gaps[0]
                if ga >= DIVERGE_TH:
                    parts.append(f'<p>在 <strong>{d}</strong> 方面，协同方与下级的评分差异较为明显（相差 {ga:.2f} 分）：'
                                 f'协同方评分 {p:.2f} 分，下级评分 {s:.2f} 分。</p>')
                else:
                    parts.append(f'<p>多数维度上协同方与下级的评分较为接近，'
                                 f'说明您的领导力表现具有较好的跨场景一致性。</p>')
            else:
                parts.append(f'<p>协同方与下级的评分数据有限，无法进行详细的对比分析。</p>')

    return "\n".join(parts)
def narrative_23_opening(ctx) -> str:
    """生成乔哈里视窗开篇（阈值说明 + Q&A 引子）。"""
    t_self = ctx.get("johari_threshold_self", 4.50)
    t_other = ctx.get("johari_threshold_other", 4.40)
    return (
        '<p>图中横轴为自评评分，纵轴为他评评分。'
        f'两条虚线分别为自评阈值（<strong>{t_self:.2f} 分</strong>）和他评阈值（<strong>{t_other:.2f} 分</strong>），'
        '基于全体被评价者的评分中位数确定——高于阈值的评分意味着处于群体的前 50% 区间。</p>'
        '<p>"不知道自己不知道"往往是个人成长的困境。通过比较自我认知与他人反馈，'
        '我们得以了解自己眼中与他人眼中自我的差异——'
        '这些差异也是我们打破信息茧房、提升自我认知、理解对他人影响的绝佳机会。</p>'
    )


# ── 2.4 开放式评语（引语 + 画像 + 主轴编码） ──────────────────
# 此函数的输入需要从评语编码文件加载，不依赖 ctx

def narrative_24_intro(ctx) -> str:
    """评语部分的引语（静态，来自 Q&A）。"""
    return (
        '<p>较之于单纯的评分，我们相信来自于他人开放式评语中更为高频的描述，代表了您在他人眼中真正的样子，'
        '它们也是您校准自我认知，理解他人期望的绝佳机会。</p>'
    )


# ── 2.5 发展行动建议（结语） ────────────────────────────────────

def narrative_25_closing() -> str:
    """发展建议结语（移除 SMH 引用后）。"""
    return (
        '<p>以上建议综合了您的360°评估数据以及同事开放式评语的编码分析。'
        '建议您从中选择 1-2 个维度，与您的上级或 HRBP 沟通后，制定个人发展计划。</p>'
    )

# ── 常模说明注记 ──────────────────────────────────────────────

def narrative_norm_desc(ctx) -> str:
    """生成常模说明注记（2.1节用）。"""
    return '<sup style="color:#64748b;font-size:.72rem;">[1]</sup>'


# ── 数智变革排除说明注记 ──────────────────────────────────────

def narrative_excluded_dim_note(ctx) -> str:
    """生成数智变革排除说明注记（2.5节用）。"""
    return '<sup style="color:#64748b;font-size:.72rem;">[2]</sup>'

