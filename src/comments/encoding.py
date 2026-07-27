"""
Phase 4: 主轴编码 + 管理者画像（LLM），含 fallback。
v2: build_user_message 新增 raw_data 参数，
    有 raw_data 时展示每个编码下所有命中的评语原文。
"""
from __future__ import annotations
import json
import logging
import re as _re
import time
import os

from pathlib import Path
from typing import Any
from src.comments.config import COMMENT_CACHE_DIR, KEYWORD_DICT
from openai import OpenAI
logger = logging.getLogger(__name__)

# ── DeepSeek API 配置 ──────────────────────────────────────────────
_ENCODING_DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
_ENCODING_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_ENCODING_DEEPSEEK_MODEL = "deepseek-v4-flash"

_ENCODING_REASONING_EFFORT = "high"

# 思考模式说明（详见 https://api-docs.deepseek.com/zh-cn/guides/thinking_mode）：
#   thinking 默认 enabled，通过 extra_body 可显式控制
#   reasoning_effort="high" 适用于结构化输出任务（主轴编码 + 画像）
#   思考模式下 temperature/top_p 等参数自动失效（传参不报错）

_ENCODING_SYSTEM_PROMPT = """你是一位经验丰富的领导力发展教练与人才评估专家。
你的任务是基于一位管理者在 360° 反馈中获得的开放式评语编码结果，完成两件事：

1. 主轴编码聚类：将关键词聚类为 3-5 个核心主题，供「优势项/待发展项总结」使用
2. 管理者画像：生成一段 4-6 句的画像式描述，供「管理者画像」使用

规则：
  - 严格基于给出的数据，不要补充编码结果之外的内容
  - 优势项按频次排序，报告 top3 主轴编码
  - 待发展项将 top2 主轴编码合并报告
  - 所有代表性评语引用必须 1:1 取自下方给出的原文
  - 语言风格：专业、教练式、娓娓道来

【管理者画像—核心要求】
画像必须像一位深入了解他的教练在与他娓娓道来，而不是一份数据列表。
(1) 以「在他人眼中，您可能是一位……」开头
(2) 将编码结果翻译为具体的管理行为，而不是停留于标签层面。
    错误示范：「您在工作投入与态度方面表现突出」
    正确示范：「凡事交代到您手上都能稳妥落地，您对细节的把控和认真负责的态度给周围同事留下了深刻印象」
(3) 画像应由以下层次构成：
    - 第一层：整体印象（一句话概括此人给周围人的核心印象）
    - 第二层：具体优势行为（基于下方列出的多条相关评语原文，用场景化句式展开）
    - 第三层：成长空间（以积极框架呈现，用「下一步可以……」的方式表达）
    - 第四层：收束（一句温暖而有启发的话）
(4) 全文 4-6 句，要有画面感和节奏感
(5) 语言像一位资深 HRBP 或高管教练在做坦诚而温暖的总结
(6) 严基于编码频次和下方给出的评语原文——画像中每个行为描述都要能在下方数据中找到具体出处

输出格式（严格 JSON，不要其他内容）：
{
  "axial_codes": {
    "strength": [
      {"name": "主轴编码名称", "count": 频次, "sub_codes": ["子编码1", "子编码2"],
       "source_distribution": "来源分布描述", "rep_quote": "代表性评语原文"}
    ],
    "development": [
      {"name": "主轴编码名称", "count": 频次, "sub_codes": [...],
       "source_distribution": "...", "rep_quote": "..."}
    ]
  },
  "profile_text": "在他人眼中，您可能是一位……（4-6句）"
}"""


def build_user_message(kw_data, raw_data=None):
    """构建 LLM 用户消息。
    有 raw_data 时：对每个主轴编码，展示所有命中的评语原文（最多8条）。
    """
    lines = []
    lines.append("以下是一位管理者在 360° 反馈中的开放式评语编码结果：\n")
    for label in ["优势评语", "发展建议"]:
        ct_data = kw_data.get(label, {})
        if not ct_data:
            continue
        lines.append("## %s" % label)
        sorted_axial = sorted(ct_data.items(), key=lambda x: -x[1].get('count', 0))
        for axial, axial_data in sorted_axial:
            count = axial_data.get('count', 0)
            persons = axial_data.get('persons', 0)
            sd_map = axial_data.get('source_dist', {})
            src_str = ", ".join("%s%d" % (s, n) for s, n in sorted(sd_map.items()))
            lines.append("")
            lines.append("[%s] %d次（%d人，来源: %s）" % (axial, count, persons, src_str))
            open_codes = axial_data.get('open_codes', {})
            sorted_sc = sorted(open_codes.items(), key=lambda x: -x[1].get('count', 0))
            sc_strs = ["%s(%d)" % (sc, scd["count"]) for sc, scd in sorted_sc]
            lines.append("  子编码: %s" % "、".join(sc_strs))
            if raw_data:
                triggers = []
                for sc_name in open_codes:
                    triggers.extend(KEYWORD_DICT.get(axial, {}).get(sc_name, []))
                matched = []
                for src, entries in raw_data.get(label, {}).items():
                    for entry in entries:
                        txt = entry.get("text", "")
                        for t in triggers:
                            if t in txt and txt not in [m[1] for m in matched]:
                                matched.append((src, txt))
                                break
                if matched:
                    lines.append("  相关评语原文（%d条）：" % len(matched))
                    for src, txt in matched[:8]:
                        dsp = txt[:120] + ("..." if len(txt) > 120 else "")
                        lines.append("    [%s] %s" % (src, dsp))
            else:
                sel = kw_data.get('selection', {}).get(label, {}).get(axial, {})
                if sel:
                    lines.append("  代表性评语：")
                    for sc_name, sc_sel in sorted(sel.items())[:2]:
                        for q in sc_sel.get('quotes', [])[:2]:
                            lines.append("    - %s" % q)
    return "\n".join(lines)


def call_llm(prompt):
    """发送完整编码Prompt到DeepSeek API，返回JSON字符串。"""
    messages = [
        {"role": "system", "content": _ENCODING_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    resp = _call_llm_api(messages)
    if not resp:
        logger.warning("LLM returned empty response, falling back")
        return None
    result = _extract_json(resp)
    if not result:
        logger.warning("Failed to parse LLM response as JSON, falling back")
        return None
    return json.dumps(result, ensure_ascii=False)


def _extract_json(text: str) -> dict | None:
    """从LLM回复中提取JSON，处理markdown fence格式。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _call_llm_api(messages: list, temperature: float = 0.3) -> str | None:
    """调用 DeepSeek API，含自动重试（最多3次）。"""
    client = OpenAI(api_key=_ENCODING_DEEPSEEK_API_KEY, base_url=_ENCODING_DEEPSEEK_BASE_URL)
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=_ENCODING_DEEPSEEK_MODEL,
                messages=messages,
                max_tokens=4096,
                reasoning_effort=_ENCODING_REASONING_EFFORT,
                extra_body={"thinking": {"type": "enabled"}},
                # temperature is ignored in thinking mode; kept for non-thinking fallback
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            if content and content.strip():
                return content
            logger.warning("DeepSeek encoding attempt %d/3 returned empty content, retrying...", attempt + 1)
        except Exception as e:
            logger.warning("DeepSeek encoding attempt %d/3 failed: %s", attempt + 1, e)
        if attempt < 2:
            time.sleep(2 ** attempt)
    return None


def fallback_encoding(kw_data):
    result = {"method": "fallback_rule", "axial_codes": {"strength": [], "development": []}, "profile_text": ""}
    for label, key in [("优势评语", "strength"), ("发展建议", "development")]:
        ct_data = kw_data.get(label, {})
        if not ct_data:
            continue
        sorted_axial = sorted(ct_data.items(), key=lambda x: -x[1].get('count', 0))
        if key == "strength":
            for axial, axial_data in sorted_axial[:3]:
                sorted_sc = sorted(axial_data.get('open_codes', {}).items(), key=lambda x: -x[1].get('count', 0))
                sd = axial_data.get('source_dist', {})
                src_str = ", ".join("%s%d人" % (s, n) for s, n in sorted(sd.items()))
                rep = "、".join([sc for sc, _ in sorted_sc[:3]])
                result["axial_codes"]["strength"].append({"name": axial, "count": axial_data["count"], "sub_codes": [sc for sc, _ in sorted_sc], "source_distribution": src_str, "rep_quote": rep})
        else:
            top2 = sorted_axial[:2]
            if not top2:
                continue
            total = sum(ad['count'] for _, ad in top2)
            subs = []
            for _, ad in top2:
                oc = ad.get('open_codes', {})
                subs.extend([sc for sc, _ in sorted(oc.items(), key=lambda x: -x[1].get('count', 0))])
            name = "%s与%s" % (top2[0][0], top2[1][0]) if len(top2) > 1 else top2[0][0]
            sm = []
            for _, ad in top2:
                for s, n in sorted(ad.get('source_dist', {}).items()):
                    sm.append("%s%d人" % (s, n))
            result["axial_codes"]["development"].append({"name": name, "count": total, "sub_codes": subs[:5], "source_distribution": "、".join(sorted(set(sm))), "rep_quote": subs[0] if subs else ""})
    s = result['axial_codes']['strength']
    d = result['axial_codes']['development']
    parts = ["在他人眼中，" if s or d else "评语信息有限。"]
    if s:
        parts.append("您是一位%s方面表现突出的管理者，" % "、".join(x["name"] for x in s[:2]))
        parts.append("%s是您最受认可的优势，主要体现在%s等方面。" % (s[0]["name"], s[0]["rep_quote"]))
    if d:
        parts.append("同时，%s是您可以关注的发展方向。" % d[0]["name"])
    result["profile_text"] = "".join(parts)
    return result


def run_encoding(person_id, input_dir=None, use_llm=True):
    if input_dir is None:
        input_dir = Path(COMMENT_CACHE_DIR)
    kw_path = input_dir / ("%s_keywords.json" % person_id)
    if not kw_path.exists():
        raise FileNotFoundError("Keywords not found: %s" % kw_path)
    with open(kw_path, "r", encoding="utf-8") as f:
        kw_data = json.load(f)
    raw_data = None
    raw_path = input_dir / ("%s.json" % person_id)
    if raw_path.exists():
        with open(raw_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    if use_llm:
        user_msg = build_user_message(kw_data, raw_data)
        full_prompt = _ENCODING_SYSTEM_PROMPT + "\n\n---\n\n" + user_msg + "\n\n---\n\n请输出 JSON。"
        resp = call_llm(full_prompt)
        if resp:
            try:
                result = json.loads(resp)
                result["method"] = "llm"
            except json.JSONDecodeError:
                result = fallback_encoding(kw_data)
        else:
            result = fallback_encoding(kw_data)
    else:
        result = fallback_encoding(kw_data)
    out_path = input_dir / ("%s_encoded.json" % person_id)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def run_encoding_all(level="L4", input_dir=None, max_persons=None, use_llm=False, delay=0.5):
    """批量运行 Phase 4 编码。

    Args:
        level: 层级 L3/L4
        input_dir: 评语缓存目录
        max_persons: 最多处理人数（默认全部）
        use_llm: 是否使用 LLM（False 则走 fallback 规则）
        delay: API 调用间隔秒数（仅 use_llm=True 时生效）
    """
    if input_dir is None:
        input_dir = Path(COMMENT_CACHE_DIR)
    kw_files = sorted(input_dir.glob('*_keywords.json'))
    if max_persons:
        kw_files = kw_files[:max_persons]
    success = failed = skipped = 0
    t_start = time.time()
    for kw_path in kw_files:
        pid = kw_path.stem.replace('_keywords', '')
        out = input_dir / ("%s_encoded.json" % pid)
        if out.exists():
            skipped += 1
            continue
        try:
            run_encoding(pid, input_dir, use_llm=use_llm)
            success += 1
            if use_llm and delay > 0:
                time.sleep(delay)
            if success % 20 == 0:
                elapsed = time.time() - t_start
                rate = success / elapsed if elapsed > 0 else 0
                logger.info("Encoding progress: %d success, %d failed, %d skipped (%.1f/s, %ds elapsed)",
                            success, failed, skipped, rate, int(elapsed))
        except Exception as e:
            logger.warning("Encoding failed for %s: %s", pid, e)
            failed += 1
    elapsed = time.time() - t_start
    logger.info("Encoding done: %d success, %d failed, %d skipped (LLM=%s, %ds)",
                success, failed, skipped, use_llm, int(elapsed))
    return success, failed, skipped

