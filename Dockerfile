# ===== Stage 1: 构建前端 =====
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --legacy-peer-deps && rm -rf /root/.npm
COPY frontend/ .
RUN rm -rf out .next && NEXT_TELEMETRY_DISABLED=1 npm run build && rm -rf node_modules .next

# ===== Stage 2: Python 最小生产镜像 =====
FROM python:3.11-alpine
WORKDIR /app

# 最小运行时依赖
RUN apk add --no-cache libpq postgresql-client && \
    addgroup -S app && adduser -S app -G app

# 安装 Python 依赖（编译依赖装完即删）
COPY requirements.txt .
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn && \
    apk del .build-deps && \
    rm -rf /root/.cache/pip

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物
COPY --from=frontend /frontend/out /app/backend/frontend

WORKDIR /app/backend
RUN mkdir -p /app/database /app/backend/uploads

EXPOSE 8000

# 用非 root 用户运行
USER app

# API 版本号（环境变量控制）
ENV API_PREFIX=/api/v1

# 多 worker 启动
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4 --limit-concurrency 128
