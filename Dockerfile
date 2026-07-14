# ============================================================
# Railway 部署 Dockerfile
# ============================================================

FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（精简，排除爬虫/streamlit 等不需要的包）
# 分步安装：先装编译依赖重的包，再装其余的
RUN pip install --no-cache-dir numpy==1.26.4
RUN pip install --no-cache-dir faiss-cpu==1.9.0
RUN pip install --no-cache-dir \
    openai==1.72.0 \
    fastapi==0.135.2 \
    uvicorn==0.42.0 \
    pydantic==2.11.0 \
    jieba==0.42.1 \
    rank-bm25==0.2.2 \
    pandas==2.2.3 \
    openpyxl==3.2.0 \
    beautifulsoup4==4.13.3 \
    requests==2.33.1 \
    httpx==0.30.0 \
    python-multipart==0.0.22 \
    tqdm==4.67.3

# 复制项目代码
COPY get_data/ /app/

# 复制脱敏 CRM 数据
COPY docs/ /app/docs/

# 将数据文件复制到种子目录（首次启动时复制到持久卷）
RUN cp -r /app/data /app/data_seed

# 复制启动脚本
COPY start_railway.sh /app/start_railway.sh
RUN chmod +x /app/start_railway.sh

# 环境变量
ENV PORT=8103
ENV SALES_AGENT_BASE_DIR=/app
ENV LLM_PROVIDER=minimax

EXPOSE ${PORT}

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

# 启动
CMD ["/app/start_railway.sh"]
