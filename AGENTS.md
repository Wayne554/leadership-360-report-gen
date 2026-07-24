---
title: AGENTS.md
tags: [project, system, rules]
date: 2026-07-20
version: 1.12
---

# AGENTS.md — 领导力360°反馈项目系统规则

> **参考文件**：`docs/` 系列设计文档 · `notes/` 工作记忆与决策日志

本文件是 Codex 在此项目工作区中的系统规则。任何 Codex 会话在操作本项目时应遵守以下约定。

---

## 项目全景速览

- **项目名称**：领导力360°反馈（Leadership 360° Feedback）
- **启动日期**：2026-07-20
- **数据来源**：2026年度面向基层管理者的360°领导力反馈真实问卷数据
- **核心产出**：
  1. 群体常模（norm）
  2. 个体乔哈里视窗可视化（自评 vs. 他评）
  3. 结构化个人 HTML 反馈报告（含常模比较、乔哈里视窗、开放式评语、发展建议）
  4. 可集成的 Codex Skill
- **关键外部依赖**：
  - RAGFlow 向量知识库（管理者手册、FYI、Career Architect Development Planner 等）
  - Coze 智能体（开放式评语处理已初步开发）
  - Obsidian Vault（知识管理、报告存档）

---

## Codex 工作流规则

### 规则 1：数据安全与版本控制

- 原始数据（`data/raw/`）**只读不写**，不做任何原地修改
- 所有数据清洗、变换步骤必须产生新文件至 `data/processed/` 或 `data/norms/`
- 处理脚本必须是可复现的（参数化、无硬编码路径）
- pandas pipeline 优先使用 `.pipe()` 链式调用，便于审计和调试

### 规则 2：文档先行

- 所有实现决策（算法选择、评分规则、可视化参数）**先记入 `docs/` 系列设计文档**，再开始编码
- 重大设计变更应同时在 `notes/关键决策日志.md` 中记录

### 规则 3：分析管线分段

分析代码遵循明确的分段结构：
```
data/raw/    →  data/processed/    →  data/norms/
  ① 数据清洗与校验    ② 聚合与常模计算    ③ 常模输出
                       ↓
              src/report/    →  output/individual/
              ④ 个体报告生成    ⑤ HTML 输出
```

### 规则 4：Python 工程规范

- 使用 `pyproject.toml` 而非 `setup.py` 管理项目元数据
- 依赖声明至 `requirements.txt` 和 `pyproject.toml`（可选）
- 类型注解优先，关键函数添加 docstring（Google style）
- 配置文件统一放在项目根目录的 `config/` 或使用环境变量
- 数据路径通过 `pathlib` 构建，不拼接字符串

### 规则 5：测试覆盖

- 数据清洗函数必须有单元测试
- 常模计算函数必须有边界条件测试（空组、单一样本、极端值）
- 报告模板渲染有快照测试或至少手动验证 checklist

### 规则 6：输出规范

- 个体 HTML 报告使用独立自包含文件（嵌入 CSS/JS，无外部依赖）
- 报告中文为主，关键术语保留英文括号注释
- 所有图表使用 Plotly（交互式）或 Matplotlib（出版级静态），优先 Plotly
- 数值保留两位小数，百分比保留一位小数

### 规则 7：报告模板管理

- HTML 报告模板存放于 `templates/reports/`，使用 Jinja2
- 模板与数据逻辑严格分离，不把数据处理逻辑写在模板中
- 模板版本管理跟随 git tag

### 规则 8：RAG 集成规范

- RAGFlow 检索封装为独立模块 `src/rag/retriever.py`，提供统一接口
- 检索结果缓存至 `data/processed/rag_cache/`，避免重复 API 调用
- 失败降级：RAGFlow 不可用时，应使用本地备选知识片段

### 规则 9：Skill 封装规范

- Skill 遵循 Codex 的 `SKILL.md` 格式
- 包含 `prompt`、`operations`、`dependencies` 三部分
- 可与 Obsidian Vault 的 AGENTS.md 规则协同

### 规则 10：严禁操作

- ❌ 删除或覆盖 `data/raw/` 下的原始数据文件
- ❌ 在代码中硬编码文件路径（使用 `pathlib` + 配置）
- ❌ 修改他人评语原文（匿名化除外）
- ❌ 将原始数据上传至任何外部服务
- ❌ 在报告模板中嵌入未经过滤的用户身份信息

---

## 项目目录结构

```
leadership-360-feedback/
├── AGENTS.md                 ← 本文件：项目系统规则
├── README.md                 ← 项目概述
├── config/                   ← 配置文件（预留）
├── docs/                     ← 设计文档
│   ├── 01-项目概述.md
│   ├── 02-数据架构与聚合逻辑.md
│   ├── 03-常模构建方案.md
│   ├── 04-乔哈里视窗可视化方案.md
│   ├── 05-个体报告生成方案.md
│   ├── 06-RAG知识库集成方案.md
│   ├── 07-Skill封装方案.md
│   ├── 08-数据分析规范与方法论.md
│   ├── 09-评语编码方案与管线设计.md
│   ├── 10-评语编码LLM系统Prompt.md
│   ├── 11-L3L4乔哈里阈值选择分析.md
│   ├── 12-群体报告图表规格说明书.md
│   └── 13-发展建议管线增强方案.md
├── notes/                    ← 工作记忆与运营笔记
│   ├── 工作记忆.md
│   ├── 关键决策日志.md
│   └── Pitfalls与经验教训.md
├── data/
│   ├── raw/                  ← 原始数据（只读）
│   ├── processed/            ← 清洗/变换后数据
│   └── norms/                ← 常模数据输出
├── src/
│   ├── aggregation/          ← 数据聚合与常模计算
│   ├── analysis/             ← 统计分析
│   ├── visualization/        ← 乔哈里视窗等图表
│   ├── report/               ← HTML 报告生成
│   ├── rag/                  ← RAGFlow 知识库集成
│   └── skill/                ← Skill 封装逻辑
├── output/
│   ├── norms/                ← 常模导出
│   ├── individual/           ← 个体报告
│   └── dashboards/           ← 仪表盘输出
├── templates/
│   ├── reports/              ← HTML 报告 Jinja2 模板
│   └── norms/                ← 常模输出模板
└── tests/                    ← 测试套件
```

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-07-20 | 初始版本：项目初始化，完整目录结构建立 |
| 1.1 | 2026-07-20 | 新增 docs/08 数据分析规范与方法论（数据溯源/处理规则/维度映射/分析方法/质控标准）；新增 describe_level3/4 分析脚本 |
| 1.2 | 2026-07-20 | 新增src/comments/评语编码管线（Phase 1-4）：关键词词典、开放编码、代表性评语选取、主轴编码+画像 |
| 1.3 | 2026-07-20 | 新增RAGFlow检索集成（src/rag/retriever.py）；新增欧氏距离排序算法与派生数据预计算；新增dev_suggestions.py发展建议生成模块（6维度×5条行为化举措+3种引导语变体） |

| 1.4 | 2026-07-21 | 新增 docs/09 评语编码方案与管线设计 + docs/10 评语编码LLM系统Prompt |
| 1.5 | 2026-07-21 | AGENTS.md v1.5: 新增规则8(RAG集成规范)+规则9(Skill封装规范)+规则10(严禁操作); 新增src/rag/模块结构 |
| 1.6 | 2026-07-21 | narrative_22 重构（维度级偏差扫描+3视角递进推断）; 引用清洗（模板+_sanitize_quote）; 评价人数统计bug修复（preprocess.py）; QA新增2项检查（总分15→17）; 10份完整管线报告验证通过 |
| 1.7 | 2026-07-22 | 新增L3全面统计分析脚本与报告（generate_l3_analysis.py）；新增L3阈值分析脚本与报告（threshold_analysis_l3.py）；L3常模计算；encoding.py Phase 4 LLM接入（call_llm→DeepSeek API）；_call_llm_api空内容重试；max_tokens 2048→4096；L3+L4距离数据合并 |
| 1.8 | 2026-07-22 | 新增 docs/11 L3/L4乔哈里阈值选择分析专题文档；AGENTS.md目录树同步更新 docs/08-11 |
| 1.11 | 2026-07-23 | 群体报告可视化全集(10张定稿图表); 新增docs/12图表规格说明书; 文档&图表嵌入draft; 乔哈里阈值调整为4.40(待确认)
| 1.9 | 2026-07-22 | Phase A: 阈值层级感知化 - _get_other_threshold() 函数；narrative.py动态阈值；dimension_distances.json重算(L3=4.30/L4=4.40)；precompute_distances.py；Phase B: L3评语编码Phase 1-4全量196人完成(DeepSeek LLM成功率100%) |
