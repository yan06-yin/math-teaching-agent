# ===== Stage 1: 构建前端 =====
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --legacy-peer-deps && rm -rf /root/.npm
COPY frontend/ .
RUN rm -rf out .next && NEXT_TELEMETRY_DISABLED=1 npm run build && rm -rf node_modules .next

# ===== Stage 2: Python 生产镜像 =====
# 使用 slim (Debian) 而非 alpine，避免 bcrypt/python-jose C 依赖编译问题
FROM python:3.11-slim
WORKDIR /app

# 最小运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --system app && adduser --system --group app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物
COPY --from=frontend /frontend/out /app/backend/frontend

WORKDIR /app/backend
RUN mkdir -p /app/database /app/uploads && chown -R app:app /app/database /app/uploads /app/backend

EXPOSE 8000

# 用非 root 用户运行
USER app

# 多 worker 启动
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4 --limit-concurrency 128
