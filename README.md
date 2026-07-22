---
title: README
date: 2026-07-20
version: 1.0
---

# 领导力360°反馈项目

## 项目定位

基于2026年度面向基层管理者的真实360°评估数据，构建从数据聚合、群体常模、个体可视化到结构化反馈报告的全链路分析工具，最终封装为可复用的 Codex Skill。

## 核心产出

| 产出 | 说明 | 交付形式 |
|------|------|----------|
| 群体常模 | 各领导力维度的群体统计基准（M, SD, 百分位数） | `data/norms/` + 可视化 |
| 乔哈里视窗 | 自评 vs. 他评的四象限对比可视化 | HTML/Plotly 交互图 |
| 个体反馈报告 | 含常模对比、乔哈里视窗、评语汇集、发展建议 | 自包含 HTML |
| Codex Skill | 可集成至管理者门户的标准化 skill | `src/skill/` + SKILL.md |

## 技术栈

- **数据处理**：Python 3.11+ · pandas · numpy · scipy
- **可视化**：Plotly（交互式） · Matplotlib（静态）
- **报告**：Jinja2 · HTML/CSS（自包含）
- **知识检索**：RAGFlow API
- **评语分析**：Coze 智能体（已有初步开发）
- **项目管理**：Codex + Obsidian Vault

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 数据预处理
python src/aggregation/01_clean_data.py

# 常模计算
python src/aggregation/02_compute_norms.py

# 生成个体报告
python src/report/generate_report.py --user_id <ID>
```

## 项目结构

参见 [AGENTS.md](AGENTS.md) 中的目录结构章节。

## 关联资源

- [Obsidian Vault 项目页](obsidian://open?vault=MyDocs&file=30-Projects%2FActive%2Fleadership-360-feedback)
- [项目设计文档](/docs/01-项目概述.md)
