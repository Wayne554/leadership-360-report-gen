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

def narrative_21(ctx) -> str:
    """生成 2.1 节叙述：您眼中的自己 → 他人眼中的您 → 差异。"""
    dims = ctx.get("dimensions", DIM_NAMES)

    self_pairs = _dim_score_pairs(ctx, "self_scores")
    other_pairs = _dim_score_pairs(ctx, "other_scores")
    if not self_pairs or not other_pairs:
        return ""

    self_pairs.sort(key=lambda x: x[1], reverse=True)
    other_pairs.sort(key=lambda x: x[1], reverse=True)

    # 一致性 / 差异点检测
    alignment, divergence = [], []
    for d in dims:
        s = _clean(ctx.get("self_scores", [None] * 7)[dims.index(d)])
        o = _clean(ctx.get("other_scores", [None] * 7)[dims.index(d)])
        if s is not None and o is not None:
            gap_abs = abs(s - o)
            if gap_abs <= 0.10:
                alignment.append((d, gap_abs))
            elif gap_abs >= 0.50:
                divergence.append((d, gap_abs, s - o))

    parts = []

    # —— 您眼中的自己 ——
    top2 = self_pairs[:2]
    bot = self_pairs[-1]
    parts.append(
        f'<p><strong>您眼中的自己</strong><br>'
        f'根据自评，您在 {len(dims)} 个领导力要素中，认为 '
        f'<strong>{top2[0][0]}、{top2[1][0]}</strong> 是自己的核心优势'
        f'（自评 {top2[0][1]:.2f}、{top2[1][1]:.2f} 分），'
        f'而 <strong>{bot[0]}</strong> 等方面则有待进一步提升。</p>'
    )

    # —— 他人眼中的您 ——
    other_top2 = other_pairs[:2]
    parts.append(
        f'<p><strong>他人眼中的您</strong><br>'
        f'在他人的评价中，基于群体<strong>常模</strong><sup style="color:#64748b;font-size:.72rem;">[1]</sup>'
        f'，<strong>{other_top2[0][0]}、{other_top2[1][0]}</strong>'
        f'是被广泛认可的优势领域。</p>'
    )

    sub_parts = []
    if alignment:
        align_str = "、".join(a[0] for a in alignment[:2])
        sub_parts.append(
            f'在 <strong>{align_str}</strong> 方面，您与周围人的认知较为接近'
            f'——他评与自评的差距在 0.1 分以内，说明自我认知与他人观察较为吻合'
        )
    if divergence:
        div_strs = []
        for d in divergence[:2]:
            sign = "高于" if d[2] > 0 else "低于"
            div_strs.append(f'{d[0]}（相差 {abs(d[2]):.2f} 分，自评{sign}他评）')
        sub_parts.append(
            f'在 {"; ".join(div_strs)} 方面，您的自评明显{"高于" if divergence[0][2] > 0 else "低于"}他评，'
            f'这一差异可能提示——您的努力或积极意图对他人而言并不完全可见，'
            f'或者您与评价者对行为标准有着不同的理解与预期。'
            f'详见下一节乔哈里视窗分析。'
        )

    if sub_parts:
        parts.append('<p>与自评相比：</p><ul>')
        for item in sub_parts:
            parts.append(f'<li>{item}</li>')
        parts.append('</ul>')

    # —— 自评与他评的总体差异 ——
    gap_val = ctx.get("self_other_gap", 0)
    gap_dir = "高于" if gap_val > 0 else "低于"
    max_gap = ctx.get("max_gap_dim", "")
    max_gap_v = abs(ctx.get("max_gap_value", 0))
    self_m = ctx.get("self_overall_mean", 0)
    other_m = ctx.get("other_overall_mean", 0)
    norm_p50 = ctx.get("norm_other_p50_overall", 0)

    parts.append(
        f'<p><strong>自评与他评的总体差异</strong><br>'
        f'总体来看，您的自评均值 <strong>{gap_dir}</strong> 他评均值 '
        f'<strong>{abs(gap_val):.2f}</strong> 分'
        f'（自评 {self_m:.2f} 分，他评 {other_m:.2f} 分，'
        f'群体常模他评 P50 为 {norm_p50:.2f} 分）。'
        f'其中 <strong>{max_gap}</strong> 的差距最大（相差 {max_gap_v:.2f} 分），'
        f'它可能提示了一定的自我认知偏差。'
        f'各维度具体的象限分布和差距详情，将在下一节的乔哈里视窗中展开。</p>'
    )

    return "\n".join(parts)


# ── 2.2 各评价来源评分对比 ──────────────────────────────────────

def narrative_22(ctx) -> str:
    """生成 2.2 节叙述：总体评分模式 → 维度级偏差 → 3视角递进推断。"""
    dims = ctx.get("dimensions", DIM_NAMES)
    self_scores = ctx.get("self_scores", [])

    src_config = {"上级": "superior_scores", "协同方": "peer_scores", "下级": "subordinate_scores"}
    matrix = {}
    for label, key in src_config.items():
        vals = ctx.get(key, [])
        matrix[label] = [_clean(vals[i]) if i < len(vals) else None for i in range(len(dims))]

    src_means = {}
    for label in src_config:
        valid = [v for v in matrix[label] if v is not None]
        if valid:
            src_means[label] = sum(valid) / len(valid)
    if not src_means:
        return ""

    means_sorted = sorted(src_means.items(), key=lambda x: x[1], reverse=True)
    max_src, max_v = means_sorted[0]
    min_src, min_v = means_sorted[-1]
    gap_between = max_v - min_v

    is_fault = False
    fault_pair = ("", "")
    src_pairs = [("上级", "下级"), ("上级", "协同方"), ("下级", "协同方")]
    for a_label, b_label in src_pairs:
        a_vals = matrix.get(a_label, [])
        b_vals = matrix.get(b_label, [])
        same_dir = 0
        total_valid = 0
        for i in range(len(dims)):
            a = a_vals[i] if i < len(a_vals) else None
            b = b_vals[i] if i < len(b_vals) else None
            if a is not None and b is not None:
                total_valid += 1
                cond = (a > b and src_means.get(a_label, 0) > src_means.get(b_label, 0))
                cond = cond or (a < b and src_means.get(a_label, 0) < src_means.get(b_label, 0))
                if cond:
                    same_dir += 1
        if total_valid >= 4 and same_dir >= total_valid * 0.7:
            is_fault = True
            fault_pair = (a_label, b_label)
            break

    parts = []
    mean_str = "\u3001".join(f"{k}\uff08{v:.2f} \u5206\uff09" for k, v in means_sorted)
    is_fault_label = "<strong>\u4e00\u5b9a\u7a0b\u5ea6\u7684\u65ad\u5c42</strong>" if is_fault else "\u8f83\u4e3a\u4e00\u81f4"
    parts.append(
        '<p><strong>\u603b\u4f53\u8bc4\u5206\u6a21\u5f0f</strong><br>'
        '\u5404\u8bc4\u4ef7\u6e90\u5bf9\u60a8\u7684\u8bc4\u5206\u5448\u73b0' + is_fault_label + '\uff1a'
        + mean_str + '\u3002</p>'
    )
    self_m = ctx.get("self_overall_mean", 0)
    if is_fault:
        close_text = f"\u4e0e\u60a8\u7684\u81ea\u8bc4\uff08{self_m:.2f} \u5206\uff09\u8f83\u4e3a\u63a5\u8fd1" if abs(max_v - self_m) < 0.2 else "\u4e0e\u81ea\u8bc4\u5b58\u5728\u4e00\u5b9a\u5dee\u8ddd"
        dir_text = "\u4f4e\u4e8e" if min_v < self_m else "\u9ad8\u4e8e"
        parts.append(
            f'<p>{max_src}\u4e0e{min_src}\u4e4b\u95f4\u7684\u8bc4\u5206\u5dee\u8ddd\u8fbe\u5230 {gap_between:.2f} \u5206\uff0c\u5b58\u5728\u4e00\u5b9a\u7a0b\u5ea6\u7684\u65ad\u5c42\u3002'
            f'{max_src}\u7684\u8bc4\u5206{close_text}\uff0c'
            f'\u800c{min_src}\u7684\u8bc4\u5206\u5219\u663e\u8457{dir_text}\u81ea\u8bc4\u3002</p>'
        )

    DEV_THRESHOLD = 0.30
    dim_findings = []
    for i, dim in enumerate(dims):
        self_v = self_scores[i] if i < len(self_scores) else None
        if self_v is None:
            continue
        for src_label in src_config:
            src_v = matrix[src_label][i]
            if src_v is None:
                continue
            gap = round(src_v - self_v, 2)
            if abs(gap) >= DEV_THRESHOLD:
                dim_findings.append({
                    "dim": dim, "source": src_label,
                    "src_score": src_v, "self_score": self_v,
                    "gap": gap,
                    "direction": "\u9ad8\u4e8e" if gap > 0 else "\u4f4e\u4e8e",
                })

    dim_spreads = []
    for i, dim in enumerate(dims):
        vals = []
        for src_label in src_config:
            v = matrix[src_label][i]
            if v is not None:
                vals.append(v)
        if len(vals) >= 2:
            spread = max(vals) - min(vals)
            dim_spreads.append({"dim": dim, "spread": spread,
                                "min_score": min(vals), "max_score": max(vals)})

    parts.append("<p><strong>\u5b83\u53ef\u80fd\u53cd\u6620&\u63d0\u793a\u4e86\u4ec0\u4e48\uff1f</strong></p>")
    has_interpretation = False

    low_findings = [f for f in dim_findings if f["gap"] < -DEV_THRESHOLD]
    if low_findings:
        low_findings.sort(key=lambda x: x["gap"])
        top_low = low_findings[:2]
        has_interpretation = True
        items = []
        for f in top_low:
            src_label = f["source"]
            if src_label == "\u4e0a\u7ea7":
                extra = "\u4e0e\u4e0a\u7ea7\u7684\u4e92\u52a8\u4e2d\uff0c\u60a8\u5728\u9762\u5411\u5f80\u4e0a\u7684\u6218\u7565\u6c47\u62a5\u3001\u76ee\u6807\u5bf9\u9f50\u6216\u5de5\u4f5c\u5c55\u793a\u7b49\u65b9\u9762\u53ef\u80fd\u8fd8\u4e0d\u591f\u5145\u5206\u6216\u6301\u7eed"
            elif src_label == "\u534f\u540c\u65b9":
                extra = "\u4e0e\u534f\u540c\u65b9\u7684\u8de8\u56e2\u961f\u534f\u4f5c\u4e2d\uff0c\u60a8\u5728\u6a2a\u5411\u6c9f\u901a\u3001\u8d44\u6e90\u534f\u8c03\u6216\u4fe1\u606f\u540c\u6b65\u7b49\u65b9\u9762\u7684\u9886\u5bfc\u884c\u4e3a\u53ef\u80fd\u672a\u80fd\u5145\u5206\u5c55\u73b0"
            else:
                extra = "\u5728\u9762\u5411\u4e0b\u7ea7\u7684\u56e2\u961f\u7ba1\u7406\u4e2d\uff0c\u76f8\u5173\u9886\u5bfc\u884c\u4e3a\u7684\u8868\u8fbe\u5bc6\u5ea6\u6216\u4e00\u81f4\u6027\u53ef\u80fd\u5c1a\u672a\u8fbe\u5230\u8ba9\u4e0b\u5c5e\u5145\u5206\u611f\u77e5\u7684\u7a0b\u5ea6"
            items.append(
                '<li>' + src_label + '\u5bf9\u60a8\u5728 <strong>' + f["dim"] + '</strong> \u65b9\u9762\u7684\u8bc4\u5206'
                + '\uff08' + f"{f['src_score']:.2f}" + ' \u5206\uff09\u4f4e\u4e8e\u81ea\u8bc4\uff08' + f"{f['self_score']:.2f}" + ' \u5206\uff09\u3002'
                + '\u8fd9\u53ef\u80fd\u53cd\u6620\u51fa\u5728\u65e5\u5e38\u5de5\u4f5c\u4e2d\uff0c' + extra + '\uff0c'
                + '\u56e0\u800c\u5728\u8be5\u89c6\u89d2\u4e0b' + src_label + '\u5bf9\u60a8\u7684\u76f8\u5173\u9886\u5bfc\u529b\u8868\u73b0\u6709\u66f4\u4e25\u683c\u7684\u8bc4\u5224\u3002</li>'
            )
        parts.append("<p><strong>\u5173\u4e8e\u4e92\u52a8\u9891\u6b21\u4e0e\u8d28\u91cf</strong></p>")
        parts.append("<ul>" + "".join(items) + "</ul>")

    src_systematic = {}
    for f in dim_findings:
        if abs(f["gap"]) < DEV_THRESHOLD:
            continue
        s = f["source"]
        if s not in src_systematic:
            src_systematic[s] = {"total_gap": 0, "dims": [], "below_count": 0, "above_count": 0}
        src_systematic[s]["total_gap"] += abs(f["gap"])
        src_systematic[s]["dims"].append(f)
        if f["gap"] < 0:
            src_systematic[s]["below_count"] += 1
        else:
            src_systematic[s]["above_count"] += 1

    systematic_candidates = [(s, data) for s, data in src_systematic.items()
                             if max(data["below_count"], data["above_count"]) >= 2]
    if systematic_candidates:
        systematic_candidates.sort(key=lambda x: x[1]["total_gap"], reverse=True)
        has_interpretation = True
        items = []
        for src_label, data in systematic_candidates[:2]:
            dominated_below = data["below_count"] >= data["above_count"]
            if dominated_below:
                sig_dims = [f for f in data["dims"] if f["gap"] < -DEV_THRESHOLD]
            else:
                sig_dims = [f for f in data["dims"] if f["gap"] > DEV_THRESHOLD]
            sig_dims.sort(key=lambda x: abs(x["gap"]), reverse=True)
            dim_list = "\u3001".join(f["dim"] for f in sig_dims[:3])

            if src_label == "\u4e0a\u7ea7":
                role_desc = "\u4e0a\u7ea7\u5bf9\u9886\u5bfc\u529b\u7684\u8bc4\u4ef7\u66f4\u591a\u805a\u7126\u4e8e\u6218\u7565\u627f\u63a5\u3001\u7ed3\u679c\u4ea4\u4ed8\u4e0e\u7ec4\u7ec7\u6548\u80fd"
            elif src_label == "\u534f\u540c\u65b9":
                role_desc = "\u534f\u540c\u65b9\u5bf9\u60a8\u7684\u8bc4\u4ef7\u66f4\u591a\u57fa\u4e8e\u8de8\u90e8\u95e8\u534f\u4f5c\u4e2d\u7684\u76f4\u89c2\u611f\u53d7\u548c\u914d\u5408\u4f53\u9a8c"
            else:
                role_desc = "\u4e0b\u7ea7\u5bf9\u60a8\u7684\u8bc4\u4ef7\u66f4\u591a\u6e90\u81ea\u65e5\u5e38\u56e2\u961f\u7ba1\u7406\u4e2d\u7684\u8fd1\u8ddd\u79bb\u89c2\u5bdf\u548c\u5207\u8eab\u611f\u53d7"

            gap_dir = "\u5747\u4f4e\u4e8e\u81ea\u8bc4" if dominated_below else "\u5747\u9ad8\u4e8e\u81ea\u8bc4"
            items.append(
                '<li>' + src_label + '\u5bf9\u60a8\u5728 ' + dim_list + ' \u7b49\u7ef4\u5ea6\u7684\u8bc4\u5206' + gap_dir + '\u3002'
                + role_desc + '\u3002\u8fd9\u53ef\u80fd\u610f\u5473\u7740' + src_label + '\u89c6\u89d2\u4e0b\u7684\u884c\u4e3a\u611f\u77e5\u4e0e\u60a8\u81ea\u8eab\u7684\u8861\u91cf\u5c3a\u5ea6\u5b58\u5728\u5dee\u5f02\u2014\u2014'
                + '\u8fd9\u4e00\u5dee\u5f02\u672c\u8eab\u4e5f\u662f\u6821\u51c6\u81ea\u6211\u8ba4\u77e5\u3001\u7406\u89e3\u4ed6\u4eba\u671f\u671b\u7684\u91cd\u8981\u4fe1\u606f\u3002</li>'
            )
        if items:
            parts.append("<p><strong>\u5173\u4e8e\u4e0d\u540c\u89d2\u8272\u7684\u671f\u671b\u5dee\u5f02</strong></p>")
            parts.append("<ul>" + "".join(items) + "</ul>")

    large_spreads = [s for s in dim_spreads if s["spread"] >= 0.50]
    if large_spreads:
        large_spreads.sort(key=lambda x: x["spread"], reverse=True)
        has_interpretation = True
        items = []
        for spread_info in large_spreads[:2]:
            items.append(
                '<li>\u5728 <strong>' + spread_info["dim"] + '</strong> \u7ef4\u5ea6\u4e0a\uff0c'
                + '\u4e0d\u540c\u8bc4\u4ef7\u6765\u6e90\u7684\u8bc4\u5206\u5dee\u5f02\u8f83\u5927'
                + '\uff08\u6700\u9ad8 ' + f"{spread_info['max_score']:.2f}" + ' \u5206 vs \u6700\u4f4e ' + f"{spread_info['min_score']:.2f}" + ' \u5206\uff09\uff0c'
                + '\u5dee\u5f02\u8fbe ' + f"{spread_info['spread']:.2f}" + ' \u5206\u3002'
                + '\u8fd9\u63d0\u793a\u60a8\u5728\u8be5\u7ef4\u5ea6\u4e0a\u7684\u9886\u5bfc\u884c\u4e3a\u53ef\u80fd\u5728\u4e0d\u540c\u573a\u666f\u6216\u9762\u5411\u4e0d\u540c\u5bf9\u8c61\u65f6\uff0c'
                + '\u8868\u73b0\u5f3a\u5ea6\u5b58\u5728\u4e00\u5b9a\u5dee\u5f02\u2014\u2014'
                + '\u5728\u90e8\u5206\u8bc4\u4ef7\u8005\u9762\u524d\u66f4\u4e3a\u5145\u5206\uff0c\u800c\u5728\u5176\u4ed6\u89c6\u89d2\u4e0b\u5219\u4e0d\u591f\u7a81\u51fa\u3002</li>'
            )
        parts.append("<p><strong>\u5173\u4e8e\u884c\u4e3a\u8868\u73b0\u5f3a\u5ea6\u7684\u53ef\u89c1\u6027</strong></p>")
        parts.append("<ul>" + "".join(items) + "</ul>")

    if not has_interpretation:
        parts.append(
            "<p>\u5404\u8bc4\u4ef7\u6e90\u7684\u8bc4\u5206\u6a21\u5f0f\u8f83\u4e3a\u5747\u8861\uff0c\u672a\u53d1\u73b0\u660e\u663e\u7684\u65ad\u5c42\u6216\u7cfb\u7edf\u6027\u504f\u5dee\u3002"
            "\u5404\u89d2\u8272\u89c6\u89d2\u4e0b\u7684\u8bc4\u5206\u5dee\u5f02\u5728\u4e00\u5b9a\u8303\u56f4\u4e4b\u5185\uff0c\u53cd\u6620\u4e86\u8de8\u89d2\u8272\u884c\u4e3a\u8868\u73b0\u7684\u4e00\u81f4\u6027\u3002</p>"
        )

    if is_fault:
        parts.append(
            f"<p>\u7efc\u5408\u6765\u770b\uff0c\u5404\u8bc4\u4ef7\u6e90\u4e4b\u95f4\u7684\u5dee\u5f02\u6307\u5411\u540c\u4e00\u79cd\u53ef\u80fd\u6027\uff1a"
            f"\u60a8\u5728{max_src}\u65b9\u9762\u6709\u8f83\u9ad8\u7684\u6295\u5165\uff0c\u4f46\u5728{min_src}\u7b49\u89c6\u89d2\u4e0b"
            f"\u4ecd\u6709\u4e00\u5b9a\u7684\u63d0\u5347\u7a7a\u95f4\u2014\u2014\u60a8\u7684\u52aa\u529b\u5728{max_src}\u9762\u524d\u6709\u66f4\u5145\u5206\u7684\u4f53\u73b0\uff0c"
            f"\u4f46\u5c1a\u672a\u4ee5\u540c\u6837\u6e05\u6670\u7684\u65b9\u5f0f\u5448\u73b0\u5728\u5176\u4ed6\u89c6\u89d2\u7684\u89c6\u91ce\u4e2d\u3002</p>"
        )

    return "\n".join(parts)
def narrative_23_opening(ctx) -> str:
    """生成乔哈里视窗开篇（阈值说明 + Q&A 引子）。"""
    return (
        '<p>图中横轴为自评评分，纵轴为他评评分。'
        '两条虚线分别为自评阈值（<strong>4.50 分</strong>）和他评阈值（<strong>4.40 分</strong>），'
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

