#!/bin/bash
# ============================================================
# Railway 启动脚本
# 
# 功能：
#   1. 检查持久卷中是否已有数据，若无则从镜像内置数据初始化
#   2. 启动 FastAPI 服务
# ============================================================

set -e

DATA_DIR="/app/data"
SEED_DIR="/app/data_seed"

# --- 1. 数据初始化（首次启动） ---
if [ ! -f "$DATA_DIR/ccgp_data.db" ]; then
    echo "[Railway] 首次启动，正在初始化数据..."
    
    # 如果有种子数据，复制到持久卷
    if [ -d "$SEED_DIR" ]; then
        cp -r "$SEED_DIR"/* "$DATA_DIR/"
        echo "[Railway] 数据初始化完成"
    else
        echo "[Railway] ⚠️  无种子数据，将以空数据库启动"
    fi
else
    echo "[Railway] 数据已存在，跳过初始化"
fi

# --- 2. 启动服务 ---
echo "[Railway] 启动 FastAPI 服务..."
cd /app
exec python webapp/server_fastapi.py
