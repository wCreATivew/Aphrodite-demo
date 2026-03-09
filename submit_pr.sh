#!/bin/bash
# 一键提交 PR 脚本
# 用法：./submit_pr.sh

set -e

echo "🚀 准备提交 PR..."

# 1. 添加所有新文件
echo "📦 添加文件..."
git add -A

# 2. 提交
echo "💾 提交更改..."
git commit -m "feat: 添加角色生成系统、声音系统和记忆系统

- 角色系统 (src/character/):
  - 角色生成器（联网搜索 + LLM 补全）
  - 人格特质数据结构（大五人格）
  - 人格 - 记忆联动配置
  - 声音、语法、环境、立场完整设定

- 声音系统 (src/voice/):
  - GPT-SoVITS 适配器
  - 声音克隆支持
  - 情感控制（7 种情感）

- 记忆系统 (src/memory/):
  - 三层记忆模型（工作/情景/语义）
  - SQLite + FAISS 存储
  - 遗忘曲线 + 强化机制
  - 话题熔断机制
  - 人格感知配置

- 测试:
  - 丰川祥子角色测试
  - 记忆系统测试（独立版本）
  - 完整交付报告

技术栈:
- LLM: Qwen3 / GPT-4
- 向量检索：Sentence Transformers + FAISS
- 声音克隆：GPT-SoVITS
- 数据库：SQLite

项目框架文档：
- FRAMEWORK.md: 整体架构
- DELIVERY_REPORT.md: 交付报告
- docs/memory_system_integration.md: 融合方案"

# 3. 显示状态
echo ""
echo "✅ 提交完成！"
echo ""
echo "📊 Git 状态:"
git status
echo ""
echo "📝 最近提交:"
git log --oneline -3
echo ""
echo "🎯 下一步："
echo "   git push origin main"
echo "   然后去 GitHub 创建 Pull Request"
