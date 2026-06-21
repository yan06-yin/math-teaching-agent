# ===== Stage 1: 构建前端 =====
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --legacy-peer-deps --only=production
COPY frontend/ .
RUN rm -rf out .next && NEXT_TELEMETRY_DISABLED=1 npm run build

# ===== Stage 2: Python 生产镜像 =====
FROM python:3.11-slim AS production
WORKDIR /app

# 最小运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物
COPY --from=frontend /frontend/out /app/backend/frontend

WORKDIR /app/backend

# 创建必要目录
RUN mkdir -p /app/database /app/backend/uploads

EXPOSE 8000

# API 版本号（通过环境变量控制，默认 v1）
ENV API_PREFIX=/api/v1
CMD sh -c "uvicorn main:app --host 0.0.0.0 --port \${PORT:-8000} --workers 4 --limit-concurrency 128"
