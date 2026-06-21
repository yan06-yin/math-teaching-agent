# ===== Stage 1: 构建前端 =====
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --legacy-peer-deps
COPY frontend/ .
RUN rm -rf out .next && NEXT_TELEMETRY_DISABLED=1 npm run build

# ===== Stage 2: Python 后端 =====
FROM python:3.11-slim
WORKDIR /app

# 安装后端依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 复制前端构建产物
COPY --from=frontend /frontend/out /app/backend/frontend

# 切换到 backend 目录
WORKDIR /app/backend

# 创建必要目录（数据库、上传文件）
RUN mkdir -p /app/database /app/backend/uploads

EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
