#!/bin/bash
# A股AI投资分析系统 - 基于uv的快速部署脚本
# 环境检查、虚拟环境设置、依赖安装和系统初始化功能

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 脚本配置
SCRIPT_VERSION="2.0.0"
PROJECT_NAME="A股AI投资分析系统"
DATABASE_FILE="ai_investment.db"
PYTHON_VERSION="3.10"

echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${BLUE}🚀 ${PROJECT_NAME} - uv版部署脚本 v${SCRIPT_VERSION}${NC}              ${CYAN}║${NC}"
echo -e "${CYAN}║${NC}  ${BLUE}OpenClaw投资智能解决方案 - 一键部署流程${NC}               ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# 错误处理函数
error_exit() {
    echo -e "${RED}✗ [错误] $1${NC}" >&2
    exit 1
}

success_msg() {
    echo -e "${GREEN}✓ $1${NC}"
}

info_msg() {
    echo -e "${BLUE}ℹ $1${NC}"
}

warn_msg() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 步骤指示器
step_num=1
print_step() {
    echo -e "\n${CYAN}━━━ 步骤 $step_num: $1 ━━━${NC}"
    ((step_num++))
}

# 检查是否为root用户
print_step "环境安全检查"
if [ "$EUID" -eq 0 ]; then
    error_exit "请勿使用root用户身份运行。建议切换至普通用户后重新执行。"
fi
success_msg "当前用户权限检查通过 ($(whoami))"

# 1. 安装 uv
print_step "安装 uv 包管理器"
if command -v uv &>/dev/null; then
    UV_VERSION=$(uv --version)
    success_msg "uv 已安装 (版本: ${UV_VERSION})"
else
    warn_msg "uv 未安装，正在尝试安装..."
    
    # 检测操作系统
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux 安装
        if command -v curl &>/dev/null; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.cargo/bin:$PATH"
        elif command -v wget &>/dev/null; then
            wget -qO- https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.cargo/bin:$PATH"
        else
            error_exit "需要 curl 或 wget 来安装 uv"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS 安装
        if command -v brew &>/dev/null; then
            brew install uv
        else
            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.cargo/bin:$PATH"
        fi
    else
        error_exit "不支持的操作系统: $OSTYPE"
    fi
    
    # 验证安装
    if ! command -v uv &>/dev/null; then
        error_exit "uv 安装失败，请手动安装后重试"
    fi
    UV_VERSION=$(uv --version)
    success_msg "uv 安装成功 (版本: ${UV_VERSION})"
fi

# 2. 检查 Python 环境
print_step "检查 Python 环境"
if ! command -v python3 &>/dev/null; then
    error_exit "Python3 未安装，请先安装 Python 3.10 或更高版本"
fi

PYTHON_FULL_VERSION=$(python3 --version 2>&1)
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 10 ]]; then
    error_exit "需要 Python 3.10 或更高版本，当前版本: ${PYTHON_FULL_VERSION}"
fi
success_msg "Python 版本检查通过 (${PYTHON_FULL_VERSION})"

# 3. 初始化或同步 uv 虚拟环境
print_step "初始化 uv 虚拟环境"
PROJECT_DIR=$(pwd)
VENV_DIR="${PROJECT_DIR}/.venv"

if [[ -d "$VENV_DIR" ]]; then
    info_msg "发现现有虚拟环境，正在同步依赖..."
    uv sync --frozen
    success_msg "依赖同步完成"
else
    info_msg "创建新的 uv 虚拟环境..."
    uv venv "$VENV_DIR" --python python3
    success_msg "虚拟环境创建成功"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
success_msg "虚拟环境已激活 ($(which python))"

# 4. 安装依赖
print_step "安装项目依赖"

# 创建 pyproject.toml（如果不存在）
if [[ ! -f "pyproject.toml" ]]; then
    info_msg "创建 pyproject.toml..."
    cat > pyproject.toml <<'EOF'
[project]
name = "ai-investment-analysis"
version = "1.0.0"
description = "A股AI投资分析系统"
requires-python = ">=3.10"
dependencies = [
    "akshare>=1.16.72",
    "pandas>=2.0.0",
    "apscheduler>=3.10.0",
    "tqdm>=4.60.0",
    "sqlalchemy>=2.0.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
EOF
    success_msg "pyproject.toml 创建完成"
else
    info_msg "使用现有的 pyproject.toml"
fi

# 安装依赖（使用 uv，添加国内镜像源加速）
info_msg "正在安装依赖..."
UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
uv pip install --python "$VENV_DIR/bin/python" \
    -r requirements.txt \
    --index-url "$UV_INDEX_URL" \
    --no-deps 2>/dev/null || uv pip install \
    -r requirements.txt \
    --index-url "$UV_INDEX_URL"

success_msg "所有依赖安装成功"
uv pip list

# 5. 数据库初始化
print_step "初始化数据库"
DATABASE_FILE="${PROJECT_DIR}/ai_investment.db"

if [[ ! -f "$DATABASE_FILE" ]]; then
    warn_msg "数据库文件不存在，正在初始化..."
    
    if [[ ! -f "db_schema.sql" ]]; then
        error_exit "db_schema.sql 文件不存在，无法初始化数据库"
    fi
    
    info_msg "执行数据库初始化..."
    if python scheduler.py --init; then
        success_msg "数据库初始化成功"
    else
        error_exit "数据库初始化失败"
    fi
else
    success_msg "数据库已存在，无需初始化"
fi

# 6. 系统验证
print_step "系统健康检查"
FAILED_CHECKS=0

# 验证 Python 脚本语法
info_msg "检查 Python 脚本语法..."
if python3 -m py_compile scheduler.py 2>/dev/null; then
    success_msg "scheduler.py 语法正确"
else
    warn_msg "scheduler.py 存在语法问题"
    ((FAILED_CHECKS++))
fi

# 验证关键模块导入
info_msg "验证核心模块..."
python3 -c "
import akshare
import pandas
import sqlalchemy
import apscheduler
from datetime import datetime
print(f'  - akshare: {akshare.__version__}')
print(f'  - pandas: {pandas.__version__}')
print(f'  - sqlalchemy: {sqlalchemy.__version__}')
print(f'  - apscheduler: {apscheduler.__version__}')
" 2>/dev/null && success_msg "所有核心模块验证通过" || {
    warn_msg "部分模块验证失败"
    ((FAILED_CHECKS++))
}

if [[ $FAILED_CHECKS -gt 0 ]]; then
    warn_msg "部分检查未通过，建议查看日志"
else
    success_msg "系统健康检查全部通过"
fi

# 7. 可选测试运行
print_step "测试运行（可选）"
echo -e "${YELLOW}是否要立即执行一次测试运行? (y/N): ${NC}"
read -r TEST_NOW

if [[ "$TEST_NOW" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    info_msg "开始测试运行..."
    if python scheduler.py --now; then
        success_msg "测试运行成功完成"
        echo -e "\n${GREEN}报告已生成，可以查看：${NC}"
        echo -e "  ${YELLOW}ls -la *.md${NC}"
        echo -e "  ${YELLOW}ls -la ~/.openclaw/workspace/${NC}"
    else
        warn_msg "测试运行遇到问题，建议检查日志"
    fi
else
    info_msg "跳过测试运行"
fi

# 完成
echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${GREEN}✅ 部署完成！${NC}                                          ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "${YELLOW}📖 常用命令：${NC}"
echo -e "  ${CYAN}source .venv/bin/activate${NC}        # 激活虚拟环境"
echo -e "  ${CYAN}uv run python scheduler.py --now${NC}  # 立即执行分析"
echo -e "  ${CYAN}uv run python scheduler.py --cron${NC} # 启动定时调度器"
echo -e "  ${CYAN}uv add <package>${NC}                  # 添加新依赖"
echo -e "  ${CYAN}uv pip list${NC}                       # 查看已安装包"
echo -e "  ${CYAN}uv pip install --upgrade <package>${NC} # 更新依赖"
echo
echo -e "${BLUE}📁 项目文件：${NC}"
echo -e "  ${YELLOW}pyproject.toml${NC}   # 项目配置和依赖定义"
echo -e "  ${YELLOW}requirements.txt${NC} # 依赖清单（备用）"
echo -e "  ${YELLOW}uv.lock${NC}          # 依赖锁定文件（确保可复现环境）"
echo -e "  ${YELLOW}.venv/${NC}           # 虚拟环境目录"