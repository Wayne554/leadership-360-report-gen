---
title: 06-RAG知识库集成方案
tags: [design, rag]
date: 2026-07-20
version: 1.0
---

# RAG 知识库集成方案

## 概述

个体报告中的发展性反馈部分，通过检索 RAGFlow 已有向量化知识库获取权威参考内容，包括：

- **Successful Manager's Handbook**（成功管理者手册）
- **Korn Ferry FYI for Your Improvement**（领导力发展指南）
- **Career Architect Development Planner**（发展计划工具）
- 其他OD知识资产

## 检索流程

```
用户ID + 待发展维度 → 构建检索 query → RAGFlow API → 结果重排序 → 注入报告
```

## Query 构建策略

对于每个需要发展建议的维度，构建检索 query：

```
模板示例：
  "为提升 {维度名称} 能力，有哪些具体的行动建议、阅读资源或发展项目？"
  "Development suggestions for improving {维度名称}，针对基层管理者"
```

每个维度发送 2-3 个不同角度的 query（中英文混合，提高语义覆盖）。

## RAGFlow 接口对接

```python
class RagflowClient:
    def __init__(self, base_url: str, api_key: str):
        ...

    def search(self, query: str, dataset_ids: list[str], top_k: int = 3) -> list[dict]:
        """检索向量知识库，返回片段列表"""
        ...

    def search_with_dimension(self, dimension: str, user_context: dict) -> list[dict]:
        """基于领导力维度和用户上下文，组合 query 并检索"""
        ...
```

## 结果后处理

1. **去重**：多个 query 的返回结果按内容相似度去重
2. **重排序**：按与维度的相关性排序
3. **格式化**：片段裁剪至 200-300 字，保留完整语义
4. **降级策略**：
   - RAGFlow 不可用 → 使用本地缓存的备选建议片段
   - 检索结果为空 → 使用预设的通用发展模板

## 缓存策略

- 缓存文件：`data/processed/rag_cache/{dimension}_{query_hash}.json`
- 缓存有效期：7 天（知识库内容更新时清空）
- 每次批量生成前可通过 flag 跳过缓存

## 建议分类

检索结果按以下类别组织到报告中：

| 类别 | 说明 | 示例 |
|------|------|------|
| 阅读资源 | 书籍、文章、白皮书 | FYI 对应章节、HBR 文章 |
| 实践项目 | 可安排的工作实践 | 跨部门项目、导师计划 |
| 培训课程 | 正式培训或在线课程 | 内部领导力培训、Coursera |
| 日常习惯 | 可立即开始的微行动 | 每日反思、反馈请求 |
| 导师/教练 | 人际关系资源 | 寻找导师、参加社群 |


## 当前实现（2026-07-20）

### 模块架构

```
src/rag/
├── __init__.py          # 模块入口
├── config.py            # 连接配置、维度-搜索词映射
├── dev_config.json      # 引导语变体、行为化举措、排除维度
├── dev_suggestions.py   # 发展建议生成器（核心逻辑）
├── retriever.py         # RAGFlow API 客户端（检索 + 缓存）
└── gen_config.py        # 配置生成脚本
```

### 检索策略：概念映射法

不再使用简单的"维度名 → query"映射，而是采用三层概念映射：

```
Query = SMH_章节术语 + 评语概念映射 + 维度标准词

例：创新引领-持续精进
  评语关键词: "打破固有思维"、"持续改进"
  → 概念映射: "challenge outdated processes"、"continuous improvement"  
  → SMH 章节: "Leverage Innovation"
  → 最终 query: "Leverage Innovation challenge outdated processes continuous improvement"
```

### 维度优先级：欧氏距离法

```
distance = √(自评² + 他评²)
排除: 数智变革（全员共性）
排序: 升序取 Bottom 3
```

预计算 882 人全量距离数据并存储于 `data/processed/dimension_distances.json`。

### 引导语变体

| 变体 | 触发条件 | 人数 | 示例 |
|------|---------|------|------|
| standard | 有维度在盲区/待发展区 | 574 | "基于您领导力7大维度上的评分，乔哈里视窗中所提示的以待发展区&盲区为主..." |
| mostly_positive | 1-2维度在盲区/待发展区 | 213 | "绝大多数领导力维度都处于您的潜能区与优势区..." |
| positive | 全部在优势区/潜能区 | 95 | "尽管基于评分，全部领导力维度都处于您的潜能区与优势区..." |

### 行为化举措库

6 个领导力维度（排除数智变革）各预编写 5 条行为化发展建议：

- 前 4 条：可立即执行的具体行为（如"在每项工作中追问'这对客户意味着什么'"）
- 第 5 条：统一引用 SMH 对应章节作为持续学习资源
- 存储于 `src/rag/dev_config.json`

### Phase B: LLM 合成（已实现）

三阶段管线的 Phase B 现已通过 DeepSeek API 实现自动化：

```
rag_context_{uid}.json (Phase A 输出)
  |
  v
llm_synthesizer.synthesize_suggestions()  <- DeepSeek API (deepseek-v4-flash)
  |  Prompt: 该人管理者画像 + Bottom-3 维度 + 知识库 chunks
  |
  v
rag_suggestions_{uid}.json (method: "deepseek_llm")
```

**降级链：**
1. rag_suggestions 有 deepseek_llm 标记 -> 直接加载
2. DeepSeek API 合成（新建）-> 保存并返回
3. auto_generate_from_context（规则版）-> 返回
4. 无 rag_context -> None（走静态预编写举措）

**质量对比：**

| 模式 | 个性化程度 |
|------|-----------|
| static | 同一维度所有人相同 |
| auto_generate | 同一维度所有人相似 |
| deepseek_llm | 因人而异，引用具体反馈语境 |

**批量生成工作量：** ~60分钟（882人 x 4s），仅客户导向需3次RAGFlow API预热。

### 架构示意

```
原始评分数据 → 宽表
    ↓
data/processed/dimension_distances.json (预计算欧氏距离)
    ↓ 排除数智变革 → 6维度 → 排序取 Bottom 3
dev_suggestions.get_development_section(person_id)
    → {preamble: "...", dimensions: [{name, actions}]}
    ↓
Jinja2 模板渲染 → 个体 HTML 报告 Section 4
```

### LLM 通道（已就绪）

Phase B 已使用 DeepSeek API 实现。如需替换为其他 API，修改 src/rag/llm_synthesizer.py 中的配置即可。



当前 RAGFlow 统一 API key 无 LLM chat 权限（Cloudflare 穿透路由限制）。LLM 加工需预留以下接入点：

1. **RAGFlow Chat API**: 需要在 Cloudflare Tunnel 中开放 LLM 端点路由，或生成支持 chat 的 API key
2. **Ollama 直连**: 若 Ollama 端口（11434）可通过穿透访问，可直接调用 qwen2.5:14b
3. **替代 LLM**: 提供 OpenAI 或其他兼容 API key

