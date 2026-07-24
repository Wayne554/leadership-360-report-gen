"""Phase B: LLM synthesis of personalized development suggestions.

Takes rag_context_{uid}.json (Phase A output) and uses DeepSeek API
to generate personalized insight + quote for each dimension.

Output: rag_suggestions_{uid}.json (with method="deepseek_llm")

Usage:
  python src/rag/llm_synthesizer.py --user_id 10016759    # single person
  python src/rag/llm_synthesizer.py --max 10               # batch (first 10)
  python src/rag/llm_synthesizer.py                         # all available
"""
from __future__ import annotations
import json
import logging
import os

import re
import time
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SUGGESTIONS_DIR = PROJECT_ROOT / "data" / "processed" / "rag_cache"

_SYSTEM_PROMPT = """你是一位资深领导力发展专家与高管教练。你的任务是基于一位管理者在360°反馈中暴露出的待发展维度、他人的开放式评语、评语编码关键词，以及从权威领导力发展手册中检索到的相关参考内容，为该管理者撰写个性化的发展洞察和行为化举措。

请针对以下每个待发展维度，生成：
1. insight（发展洞察）：一段3-5句的教练式引导文字，结合参考内容和评语关键词进行有温度的启发
2. actions（行为化举措）：基于参考内容和评语关键词，为该管理者生成5条个性化的行为化发展举措，每条以一个具体行动描述，用"你"字开头，避免空洞套话
3. quote（引语）：从参考内容中选取一句最相关的原文作为引语，注明出处

要求：
- 洞察要结合该管理者的具体反馈情景和评语编码关键词，避免通用套话
- 行为化举措要个性化，紧扣评语中暴露的具体发展机会
- 语言风格：专业、温暖、教练式，像一位资深HRBP在娓娓道来
- 严格基于给出的参考内容，不要虚构或补充外部信息

重要：输出 JSON 的维度名必须严格与上文「待发展维度与参考内容」中列出的 ### 标题完全一致，不可修改、缩写或替换为其他名称。

输出格式（严格JSON，不要其他内容）：
{
  "dimensions": {
    "维度名": {
      "insight": "...（3-5句的发展洞察）",
      "actions": ["举措1", "举措2", "举措3"],
      "quote": "——《来源书名》"
    }
  }
}"""
def _build_user_message(person_id: str, context: dict) -> str:
    lines = [f"## 管理者信息\n工号：{person_id}"]
    cp = context.get("comment_profile", {})
    if cp.get("profile"):
        lines.append(f"管理者画像：{cp['profile']}")
    if cp.get("top_strengths"):
        lines.append(f"核心优势：{'、'.join(cp['top_strengths'])}")
    if cp.get("development_areas"):
        lines.append(f"待发展领域：{'、'.join(cp['development_areas'])}")
    lines.append("")
    lines.append("## 待发展维度与参考内容")
    # Keyword context from comment coding (Phase 0.2)
    axial = cp.get("axial_codes", {})
    sc = axial.get("strength", []) or []
    dc = axial.get("development", []) or []
    if sc or dc:
        kw_parts = []
        for codes, label in [(sc, "优势"), (dc, "待发展")]:
            for code in codes:
                name = code.get("name", "")
                count = code.get("count", 0)
                subs = code.get("sub_codes", [])
                if subs:
                    kw_parts.append(f"{name}({count}次, 含{"、".join(subs)})")
                else:
                    kw_parts.append(f"{name}({count}次)")
        lines.append(f"评语编码：{'；'.join(kw_parts)}")

    for dim_name, dim_data in context.get("dimensions", {}).items():
        lines.append("")
        lines.append(f"### {dim_name}")
        for i, chunk in enumerate(dim_data.get("chunks", []), 1):
            content = chunk.get("content", "")
            source = chunk.get("source", "unknown")
            if len(content) > 800:
                content = content[:800] + "…"
            lines.append(f"[参考{i}] 来源《{source}》：{content}")
    return "\n".join(lines)


def _call_deepseek(messages: list, temperature: float = 0.3) -> str | None:
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.warning("DeepSeek attempt %d/3 failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt)
    return None


def synthesize_suggestions(person_id: str, context: dict | None = None) -> dict | None:
    """Generate personalized development suggestions using DeepSeek API."""
    if context is None:
        ctx_path = SUGGESTIONS_DIR / f"rag_context_{person_id}.json"
        if not ctx_path.exists():
            logger.warning("No rag_context for %s", person_id)
            return None
        with open(ctx_path, "r", encoding="utf-8") as f:
            context = json.load(f)
    dims = context.get("dimensions", {})
    if not dims:
        logger.warning("rag_context for %s has no dimension data", person_id)
        return None
    user_msg = _build_user_message(person_id, context)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    logger.info("Synthesizing for %s (%d dims)...", person_id, len(dims))
    resp = _call_deepseek(messages)
    if not resp:
        logger.warning("DeepSeek API failed for %s", person_id)
        return None
    try:
        result = json.loads(resp)
        # Map shortened dimension keys back to full names
        ctx_dims = context.get("dimensions", {})
        if ctx_dims and isinstance(result.get("dimensions"), dict):
            expected = list(ctx_dims.keys())
            mapped = {}
            for short_key, val in result["dimensions"].items():
                # 1) Prefix match (most common: LLM drops subtitle after dash)
                matched = [k for k in expected if k.startswith(short_key)]
                if not matched:
                    # 2) Word-level match: if every word in short_key appears in a context key
                    words = short_key.replace("-", " ").replace("&", " ").split()
                    matched = [k for k in expected if all(w in k for w in words)]
                if matched:
                    mapped[matched[0]] = val
                else:
                    mapped[short_key] = val
            result["dimensions"] = mapped

    except json.JSONDecodeError:
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', resp)
        if m:
            try:
                result = json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
        else:
            return None
    if "dimensions" not in result:
        logger.warning("DeepSeek response missing 'dimensions' for %s", person_id)
        return None
    result["method"] = "deepseek_llm"
    result["model"] = DEEPSEEK_MODEL
    out_path = SUGGESTIONS_DIR / f"rag_suggestions_{person_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info("Saved suggestions for %s", person_id)
    return result


def synthesize_batch(level: str = "L4", max_persons: int | None = None, delay: float = 0.5):
    ctx_files = sorted(SUGGESTIONS_DIR.glob(f"rag_context_*.json"))
    if max_persons:
        ctx_files = ctx_files[:max_persons]
    success = failed = skipped = 0
    for ctx_path in ctx_files:
        pid = ctx_path.stem.replace("rag_context_", "")
        sug_path = SUGGESTIONS_DIR / f"rag_suggestions_{pid}.json"
        if sug_path.exists():
            skipped += 1
            continue
        try:
            if synthesize_suggestions(pid):
                success += 1
            else:
                failed += 1
            time.sleep(delay)
        except Exception as e:
            logger.error("Failed for %s: %s", pid, e)
            failed += 1
    logger.info("Batch done: %d success, %d failed, %d skipped", success, failed, skipped)
    return success, failed, skipped


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--user_id", type=str, help="Single person ID")
    parser.add_argument("--max", type=int, default=None, help="Max persons for batch")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls")
    args = parser.parse_args()
    if args.user_id:
        synthesize_suggestions(args.user_id)
    else:
        synthesize_batch(max_persons=args.max, delay=args.delay)
