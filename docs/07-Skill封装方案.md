---
title: 07-Skill封装方案
tags: [design, skill]
date: 2026-07-20
version: 1.0
---

# Skill 封装方案

## 目标

将领导力360°反馈的分析管线封装为标准化的 Codex Skill，使其可通过简单的触发词启动完整流程，并最终集成至管理者门户。

## Skill 接口设计

### 触发词

- 中文：`360反馈` · `领导力报告` · `生成反馈报告` · `乔哈里视窗`
- English: `360 feedback` · `leadership report` · `johari window`

### 输入参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| user_id | str | N | 指定生成单个报告；为空则批量全部 |
| group_by | str | N | 常模分组字段（department / level / none） |
| include_rag | bool | N | 是否包含 RAG 发展建议（默认 true） |
| output_dir | str | N | 输出目录（默认 output/individual/） |
| lang | str | N | 报告语言（zh / en，默认 zh） |

### 输出

- 常模数据 → `data/norms/`
- 个体报告 → `output/individual/{user_id}/`
- 日志 → `output/logs/`

## SKILL.md 结构

```markdown
---
name: leadership-360-feedback
description: 领导力360°反馈分析与报告生成
version: 1.0.0
author: OD/TD Team
trigger:
  - 360反馈
  - 领导力报告
  - 生成反馈报告
---

# 领导力360°反馈 Skill

## Prompt

你是一名组织与人才发展领域的专家，负责基于360°领导力反馈数据生成分析报告。

## Operations

### step_1: explore_data
读取 data/raw/ 下的原始 Excel 文件，探查数据结构并更新工作记忆。

### step_2: compute_norms
执行数据清洗、聚合、常模计算，输出至 data/norms/。

### step_3: visualize
基于常模数据生成个体乔哈里视窗和差距分析图表。

### step_4: generate_reports
渲染 HTML 报告模板，输出自包含报告文件。

### step_5: retrieve_rag_feedback
调用 RAGFlow 检索发展性反馈内容并注入报告。

## Dependencies

- Python 3.11+
- pandas, numpy, scipy, plotly, jinja2
- RAGFlow API access
- Coze API access (for comment processing)
```

## 封装层级

```
src/skill/
├── SKILL.md                    # Skill 元描述（Codex 主入口）
├── skill_runner.py             # 统一入口：解析参数→编排流程
├── handlers/
│   ├── norm_handler.py         # 常模计算处理
│   ├── report_handler.py       # 报告生成处理
│   └── rag_handler.py          # RAG 检索处理
└── templates/
    └── report.html             # 报告模板
```

## 集成方案

### 方案一：Codex Skill（首选）

- 通过 SKILL.md + Python 工具直接运行
- 适用于本地分析、调试和小规模批量生成

### 方案二：管理者门户嵌入（远期）

- 将核心逻辑暴露为 FastAPI 端点
- 门户通过 HTTP 请求触发，接收回调通知
- API 鉴权通过内部 Token

## 可复用性设计

- 所有配置参数外部化到 `config.yaml`
- 维度映射通过 JSON 配置，支持不同领导力模型的切换
- 报告模板通过 Jinja2 支持多品牌/多语言模板
- 常模版本管理：每次常模计算生成新版本号，保留历史
