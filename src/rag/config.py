# -*- coding: utf-8 -*-
"""RAGFlow 连接配置与维度-搜索词映射。"""
from __future__ import annotations
from pathlib import Path

RAGFLOW_API_URL = "https://ragflow.aihr-lab.org"
RAGFLOW_API_KEY = "ragflow-G4VpxJz4hQRtBaMbByv9OMbHsKxD_KwdSJeU6DxwvQ4"

DATASET_TALENT_DEV = "bdc4a99a731911f18782a7f5afb3e03f"
DATASET_LEADERSHIP_DEV = "347f2d5e731911f18782a7f5afb3e03f"
ALL_DATASETS = [DATASET_TALENT_DEV]

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAG_CACHE_DIR = PROJECT_ROOT / "data" / "processed" / "rag_cache"

TOP_K = 5
SIMILARITY_THRESHOLD = 0.5

DIMENSION_QUERIES = {
    "战略思维-科学决策": [
        "strategic thinking decision making development suggestions for managers",
        "make sound decisions strategic planning leadership development",
        "提高战略思维和科学决策能力 管理者发展建议",
        "inspire a shared vision communicate future direction strategic leadership",  # LC
        "leadership pipeline strategic thinking business manager level transition",  # LP
    ],
    "创新引领-持续精进": [
        "leverage innovation creative thinking continuous improvement managers",
        "stimulate innovation in teams foster creative thinking development",
        "创新引领持续改进 管理者创新力提升建议",
        "challenge the process experiment risk taking innovation leadership practices",  # LC
    ],
    "全球视野-管理复杂情况": [
        "global perspective managing complexity ambiguity leadership",
        "manage complex situations cross-cultural development for managers",
        "全球视野 管理复杂情况 复杂问题解决能力发展",
        "challenge the process seek opportunities change complex ambiguous environment",  # LC
    ],
    "客户导向-珍视客户": [
        "customer focus value customers build customer relationships",
        "customer orientation service excellence for managers",
        "客户导向 珍视客户 客户关系管理发展建议",
        "customer focus build relationships enable others to act foster collaboration",  # LC
    ],
    "数智变革-加强数字应用": [
        "digital transformation technology change for managers",
        "leading technology adoption data-driven leadership",
        "数智变革 数字应用 数字化转型管理者发展建议",
        "challenge the process experiment new technology digital adoption innovation",  # LC
    ],
    "发展组织-带兵打仗": [
        "developing others talent development coaching mentoring",
        "build team capability develop subordinates leadership",
        "发展组织 培养下属 团队能力建设管理者发展建议",
        "develop subordinates strengthen others enable others to act leadership capabilities",  # LC
        "encourage the heart recognize contributions celebrate wins team culture",  # LC
        "leadership pipeline different levels transitions develop managers time application",  # LP
    ],
    "追求卓越-高效执行": [
        "execution excellence drive results performance management",
        "achieve goals accountability follow-through managers",
        "高效执行 追求卓越 执行力提升发展建议",
        "model the way clarify values set example execution accountability leadership",  # LC
        "leadership pipeline time management skill development different level priorities",  # LP
    ],
}

FALLBACK_ADVICE = {}
FALLBACK_ADVICE["战略思维-科学决策"] = '建议阅读 Korn Ferry FYI for Your Improvement 中 “Strategic Decision Making” 章节，以及 Successful Manager’s Handbook 中 “Make Sound Decisions” 章节。可结合实际工作项目，练习在信息不完全情况下做出决策，并定期复盘决策质量。'
FALLBACK_ADVICE["创新引领-持续精进"] = '建议参考 FYI 中 “Innovation Management” 及 SMH 中 “Leverage Innovation” 章节。鼓励团队定期开展头脑风暴，建立创新提案机制，在部门内营造允许试错的氛围。'
FALLBACK_ADVICE["全球视野-管理复杂情况"] = ('建议阅读 FYI 中 “Global Perspective” 相关章节，主动参与跨部门/跨区域项目，扩展对组织全局和外部环境的理解。')
FALLBACK_ADVICE["客户导向-珍视客户"] = ('建议参考 FYI 中 “Customer Focus” 及 SMH 中 “Value Customers” 章节。定期与客户直接交流，将客户反馈转化为具体的产品和流程改进。')
FALLBACK_ADVICE["数智变革-加强数字应用"] = ('建议参考组织的数字化转型培训资源，关注 FYI 中相关技术变革章节。主动了解行业数字技术趋势，在团队中推广数字工具的应用。')
FALLBACK_ADVICE["发展组织-带兵打仗"] = ('建议参考 SMH 中 “Develop Others” 章节。为下属制定个性化发展计划，定期进行发展型反馈，适当授权让下属承担更具挑战性的任务。')
FALLBACK_ADVICE["追求卓越-高效执行"] = ('建议参考 SMH 中 “Drive for Results” 章节。建立明确的目标跟踪机制，定期检视进度，培养团队的执行文化。')