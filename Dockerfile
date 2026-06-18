FROM python:3.11-slim

WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ ./backend/

# 复制 .env 忽略（在 Railway 用环境变量）
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
