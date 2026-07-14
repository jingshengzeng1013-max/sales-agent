#!/bin/bash
# ============================================================
# 销售情报系统 - 对外发布部署脚本
# 
# 用途：在全新的服务器上一键部署系统，提供对外在线访问
# 
# 使用方法：
#   chmod +x deploy_public.sh
#   ./deploy_public.sh
# ============================================================

set -e

# --- 配置区（按实际环境修改）---
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-8103}"
HOST="${HOST:-0.0.0.0}"
WORKERS="${WORKERS:-1}"

echo "============================================================"
echo "  销售情报系统 - 对外发布部署"
echo "============================================================"
echo ""
echo "项目目录: $PROJECT_DIR"
echo "Python:   $PYTHON_BIN"
echo "监听端口: $PORT"
echo ""

# --- 1. 检查 Python 环境 ---
echo "[1/5] 检查 Python 环境..."
if ! command -v $PYTHON_BIN &> /dev/null; then
    echo "❌ 未找到 $PYTHON_BIN，请先安装 Python 3.8+"
    exit 1
fi
PY_VERSION=$($PYTHON_BIN --version 2>&1)
echo "   ✅ $PY_VERSION"

# --- 2. 安装依赖 ---
echo ""
echo "[2/5] 安装 Python 依赖..."
cd "$PROJECT_DIR/get_data"
$PYTHON_BIN -m pip install -r requirements.txt -q
echo "   ✅ 依赖安装完成"

# --- 3. 检查数据文件 ---
echo ""
echo "[3/5] 检查数据文件..."

DB_FILE="$PROJECT_DIR/get_data/data/ccgp_data.db"
PROFILE_FILE="$PROJECT_DIR/get_data/data/output/customer/customer_profiles.jsonl"
PRODUCT_FILE="$PROJECT_DIR/get_data/data/product.jsonl"

if [ ! -f "$DB_FILE" ]; then
    echo "   ⚠️  数据库文件不存在: $DB_FILE"
    echo "      系统将以空数据库启动，部分功能不可用"
else
    echo "   ✅ 数据库: $(du -h $DB_FILE | cut -f1)"
fi

if [ ! -f "$PROFILE_FILE" ]; then
    echo "   ⚠️  客户画像文件不存在: $PROFILE_FILE"
else
    echo "   ✅ 客户画像: $(wc -l < $PROFILE_FILE) 条"
fi

if [ ! -f "$PRODUCT_FILE" ]; then
    echo "   ⚠️  产品库文件不存在: $PRODUCT_FILE"
else
    echo "   ✅ 产品库: $(wc -l < $PRODUCT_FILE) 条"
fi

# --- 4. 检查 LLM 配置 ---
echo ""
echo "[4/5] 检查 LLM 配置..."
if [ -z "$LLM_PROVIDER" ]; then
    echo "   ℹ️  未设置 LLM_PROVIDER，默认使用 local"
    echo "      如需使用 DeepSeek，请设置环境变量："
    echo "      export LLM_PROVIDER=deepseek"
    echo "      export DEEPSEEK_API_KEY=your_api_key"
fi
if [ -z "$EMBEDDING_BASE_URL" ]; then
    echo "   ℹ️  未设置 EMBEDDING_BASE_URL，向量检索可能不可用"
    echo "      请设置 Embedding API 地址："
    echo "      export EMBEDDING_BASE_URL=http://your-embedding-server:8022/v1"
fi
echo "   ✅ LLM 配置检查完成"

# --- 5. 启动服务 ---
echo ""
echo "[5/5] 启动服务..."
echo ""
echo "============================================================"
echo "  🚀 服务启动中..."
echo ""
echo "  本地访问: http://127.0.0.1:$PORT/static/demo.html"
echo "  在线访问: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-server-ip'):$PORT/static/demo.html"
echo "  API 文档: http://127.0.0.1:$PORT/docs"
echo ""
echo "  按 Ctrl+C 停止服务"
echo "============================================================"
echo ""

exec $PYTHON_BIN webapp/server_fastapi.py
