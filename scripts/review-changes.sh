#!/bin/bash
# review-changes.sh - 审查 Agent 改动
# 用法：./scripts/review-changes.sh [worktree 目录]

set -e

WORKTREE_DIR="${1:-.}"
WORKSPACE_ROOT="/home/creative/.openclaw/workspace"

# 颜色 (支持 ANSI 的终端)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# 禁区文件（禁止修改/删除）
FORBIDDEN_FILES=(
    ".env"
    ".env.example"
    "requirements.txt"
    "setup.py"
    "pyproject.toml"
)

# 关键文件（修改需要警告）
CRITICAL_FILES=(
    "runtime_engine.py"
    "memory_store.py"
    "companion_rag.py"
    "schemas.py"
    "kernel.py"
    "worker.py"
)

# 测试目录
TEST_DIRS=("tests" "test_*.py")

echo "🔍 开始审查改动..."
echo "   目录：${WORKTREE_DIR}"
echo ""

cd "$WORKTREE_DIR"

# 1. 检查 git 状态
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 1. Git 状态"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ 不是 git 仓库${NC}"
    exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "   分支：${BRANCH}"

# 获取改动统计
ADDED=$(git diff HEAD --numstat | awk '{sum+=$1} END {print sum+0}')
DELETED=$(git diff HEAD --numstat | awk '{sum+=$2} END {print sum+0}')
FILES_CHANGED=$(git diff HEAD --name-only | wc -l | tr -d ' ')

echo "   改动：+${ADDED} -${DELETED} (${FILES_CHANGED} 个文件)"
echo ""

# 2. 检查禁区文件
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚫 2. 禁区文件检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FORBIDDEN_HIT=0
for file in "${FORBIDDEN_FILES[@]}"; do
    if git diff HEAD --name-only | grep -q "^${file}$"; then
        echo -e "${RED}❌ 触碰禁区：${file}${NC}"
        FORBIDDEN_HIT=1
    fi
done

if [ $FORBIDDEN_HIT -eq 0 ]; then
    echo -e "${GREEN}✅ 未触碰禁区${NC}"
fi
echo ""

# 3. 检查关键文件
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  3. 关键文件修改"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CRITICAL_HIT=0
for file in "${CRITICAL_FILES[@]}"; do
    if git diff HEAD --name-only | grep -q "${file}"; then
        echo -e "${YELLOW}⚠️  修改关键文件：${file}${NC}"
        CRITICAL_HIT=1
    fi
done

if [ $CRITICAL_HIT -eq 0 ]; then
    echo -e "${GREEN}✅ 未修改关键文件${NC}"
fi
echo ""

# 4. 检查删除的文件
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  4. 删除文件检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

DELETED_FILES=$(git diff HEAD --diff-filter=D --name-only)
if [ -n "$DELETED_FILES" ]; then
    echo -e "${YELLOW}⚠️  删除了以下文件：${NC}"
    echo "$DELETED_FILES" | while read -r file; do
        echo "   - ${file}"
    done
    
    # 检查是否删除了测试文件
    if echo "$DELETED_FILES" | grep -qE "^tests/|test_.*\.py$"; then
        echo -e "${RED}❌ 删除了测试文件！${NC}"
    fi
else
    echo -e "${GREEN}✅ 没有删除文件${NC}"
fi
echo ""

# 5. Diff 大小评估
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📏 5. Diff 大小评估"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_CHANGES=$((ADDED + DELETED))

if [ $TOTAL_CHANGES -gt 1000 ]; then
    echo -e "${RED}❌ Diff 过大：${TOTAL_CHANGES} 行 (建议 <1000)${NC}"
    echo "   建议：拆分成多个小 PR"
elif [ $TOTAL_CHANGES -gt 500 ]; then
    echo -e "${YELLOW}⚠️  Diff 较大：${TOTAL_CHANGES} 行 (建议 <500)${NC}"
elif [ $TOTAL_CHANGES -gt 200 ]; then
    echo -e "${BLUE}ℹ️  Diff 中等：${TOTAL_CHANGES} 行${NC}"
else
    echo -e "${GREEN}✅ Diff 合理：${TOTAL_CHANGES} 行${NC}"
fi
echo ""

# 6. 测试检查
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 6. 测试检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 检查是否有测试文件
HAS_TESTS=0
for test_pattern in "${TEST_DIRS[@]}"; do
    if [ -d "$test_pattern" ] || ls $test_pattern 2>/dev/null | head -1 > /dev/null; then
        HAS_TESTS=1
        break
    fi
done

if [ $HAS_TESTS -eq 1 ]; then
    echo "   发现测试文件，运行测试..."
    
    # 检查 pytest 是否存在
    if command -v pytest &> /dev/null; then
        # 运行测试（带超时）
        if timeout 60 pytest -x -q 2>&1 | tail -20; then
            echo -e "${GREEN}✅ 测试通过${NC}"
        else
            echo -e "${RED}❌ 测试失败${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  pytest 未安装，跳过测试${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  未发现测试文件${NC}"
    echo "   建议：添加测试覆盖改动"
fi
echo ""

# 7. 新增文件检查
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📁 7. 新增文件"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

NEW_FILES=$(git diff HEAD --diff-filter=A --name-only)
if [ -n "$NEW_FILES" ]; then
    echo "   新增文件："
    echo "$NEW_FILES" | while read -r file; do
        echo "   + ${file}"
    done
else
    echo "   没有新增文件"
fi
echo ""

# 8. 提交信息检查
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 8. 提交信息检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

UNCOMMITTED=$(git status --porcelain | wc -l | tr -d ' ')
if [ $UNCOMMITTED -gt 0 ]; then
    echo -e "${YELLOW}⚠️  有 ${UNCOMMITTED} 个未提交的文件${NC}"
    echo "   建议：提交后再开 PR"
else
    echo -e "${GREEN}✅ 所有文件已提交${NC}"
    
    # 检查最近提交信息
    LAST_COMMIT_MSG=$(git log -1 --pretty=%s)
    echo "   最近提交：${LAST_COMMIT_MSG}"
    
    # 检查提交信息格式
    if echo "$LAST_COMMIT_MSG" | grep -qE "^(feat|fix|docs|chore|refactor|test):"; then
        echo -e "${GREEN}✅ 提交信息格式规范${NC}"
    else
        echo -e "${YELLOW}⚠️  提交信息建议使用约定式格式 (feat:/fix:/docs:等)${NC}"
    fi
fi
echo ""

# 9. 综合评估
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 9. PR 适合度评估"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SCORE=100
ISSUES=()

if [ $FORBIDDEN_HIT -eq 1 ]; then
    SCORE=$((SCORE - 50))
    ISSUES+=("触碰禁区文件")
fi

if [ $TOTAL_CHANGES -gt 1000 ]; then
    SCORE=$((SCORE - 30))
    ISSUES+=("Diff 过大")
elif [ $TOTAL_CHANGES -gt 500 ]; then
    SCORE=$((SCORE - 15))
    ISSUES+=("Diff 较大")
fi

if [ -n "$DELETED_FILES" ]; then
    SCORE=$((SCORE - 10))
    ISSUES+=("有删除文件")
fi

if [ $UNCOMMITTED -gt 0 ]; then
    SCORE=$((SCORE - 20))
    ISSUES+=("有未提交文件")
fi

echo "   得分：${SCORE}/100"

if [ ${#ISSUES[@]} -gt 0 ]; then
    echo "   问题："
    for issue in "${ISSUES[@]}"; do
        echo "   - ${issue}"
    done
fi

echo ""
if [ $SCORE -ge 80 ]; then
    echo -e "${GREEN}✅ 适合开 PR (得分：${SCORE})${NC}"
    echo "   可以提交 PR 了！"
elif [ $SCORE -ge 60 ]; then
    echo -e "${YELLOW}⚠️  可以开 PR 但有改进空间 (得分：${SCORE})${NC}"
    echo "   建议先解决上述问题"
else
    echo -e "${RED}❌ 不适合开 PR (得分：${SCORE})${NC}"
    echo "   请先解决上述问题"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 审查完成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 返回码
if [ $SCORE -ge 60 ]; then
    exit 0
else
    exit 1
fi
