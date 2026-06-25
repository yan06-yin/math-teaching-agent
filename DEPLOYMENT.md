# 🚀 部署指南

> 本项目支持多种免费部署方式，5 分钟即可上线。

---

## 方案一：Railway（推荐 ⭐）

**免费额度**：$5/月信用额度，足够小型项目运行

### 一键部署

1. Fork 本仓库到你的 GitHub
2. 访问 [Railway](https://railway.app) 并用 GitHub 登录
3. 点击 **New Project → Deploy from GitHub repo**
4. 选择你 fork 的仓库
5. Railway 会自动检测 `Dockerfile` 并构建

### 配置环境变量

在 Railway 项目的 **Variables** 页面添加：

| 变量 | 必填 | 说明 |
|------|------|------|
| `AGNES_API_KEY` | ✅ | AI API Key，从 [apihub.agnes-ai.com](https://apihub.agnes-ai.com) 注册获取 |
| `AGNES_BASE_URL` | | 默认 `https://apihub.agnes-ai.com/v1` |
| `AGNES_MODEL` | | 默认 `agnes-2.0-flash` |
| `SECRET_KEY` | | JWT 密钥，留空自动生成（生产建议设置固定值） |
| `DATABASE_URL` | | 留空默认 SQLite；如需 PostgreSQL 见下方 |

### 配置域名

1. 在 Railway 项目 → **Settings** → **Networking**
2. 点击 **Generate Domain** 获得免费的 `*.up.railway.app` 域名
3. 也可绑定自定义域名

### 数据持久化

SQLite 数据库存储在容器内，重新部署会丢失数据。建议：

**方案 A**：添加 Railway Volume（免费 1GB）
1. 项目 → **Settings** → **Volumes** → **New Volume**
2. Mount Path: `/app/database`

**方案 B**：使用免费 PostgreSQL
1. 在 Railway 项目中 **New → Database → PostgreSQL**
2. 复制连接字符串，设为 `DATABASE_URL` 环境变量

---

## 方案二：Render（免费）

**免费额度**：750 小时/月，有冷启动（首次访问需等 30 秒）

### 部署步骤

1. Fork 本仓库
2. 访问 [render.com](https://render.com) 并用 GitHub 登录
3. **New → Web Service** → 选择你的仓库
4. 配置：
   - **Environment**: Docker
   - **Plan**: Free
   - **Environment Variables**: 同上表
5. 点击 **Create Web Service**

> ⚠️ Render 免费版 15 分钟无请求后会休眠，首次访问需等 30 秒冷启动。

---

## 方案三：Fly.io（免费）

**免费额度**：3 个共享 CPU VM + 3GB 持久存储

```bash
# 安装 flyctl
curl -L https://fly.io/install.sh | sh

# 登录
fly auth login

# 初始化（会自动检测 Dockerfile）
fly launch

# 设置环境变量
fly secrets set AGNES_API_KEY=your_key_here

# 部署
fly deploy
```

---

## 方案四：Docker 自部署

适用于有自己的服务器（VPS、NAS、校园服务器等）

```bash
# 克隆仓库
git clone https://github.com/yan06-yin/math-teaching-agent.git
cd math-teaching-agent

# 创建 .env 文件
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 AGNES_API_KEY

# Docker 构建 + 运行
docker build -t math-agent .
docker run -d \
  --name math-agent \
  -p 8080:8000 \
  -v math-agent-data:/app/database \
  -v math-agent-uploads:/app/uploads \
  --env-file backend/.env \
  math-agent

# 访问 http://localhost:8080
```

### docker-compose（更简单）

```yaml
version: "3.8"
services:
  app:
    build: .
    ports:
      - "8080:8000"
    volumes:
      - app-data:/app/database
      - app-uploads:/app/uploads
    env_file:
      - backend/.env
    restart: unless-stopped

volumes:
  app-data:
  app-uploads:
```

```bash
docker-compose up -d
```

---

## 方案五：本地直接运行（开发/演示）

不需要 Docker，直接用 Python 运行：

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env

# 构建前端
cd frontend && npm install && npm run build && cp -r out ../backend/frontend && cd ..

# 启动
cd backend && python main.py

# 访问 http://localhost:8080
```

---

## 免费 AI API 获取

本项目使用 [Agnes AI](https://apihub.agnes-ai.com) 提供的免费 API：

1. 访问 https://apihub.agnes-ai.com
2. 注册账号（支持 GitHub 登录）
3. 进入 **API Keys** 页面，生成一个 Key
4. 将 Key 填入环境变量 `AGNES_API_KEY`

> 也支持 DeepSeek、OpenAI 等其他 OpenAI 兼容 API，在管理后台 → AI 模型中切换。

---

## 默认账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员 | admin | admin123 |

> ⚠️ 首次部署后请立即在管理后台修改密码！

---

## 常见问题

### Q: 部署后页面空白？
A: 确认 Dockerfile 中前端构建成功。检查 `backend/frontend/` 目录是否存在 `index.html`。

### Q: AI 批改报错？
A: 检查 `AGNES_API_KEY` 是否正确设置。在管理后台 → AI 模型中可以测试连接。

### Q: 数据会丢失吗？
A: 使用 SQLite 时，如果没挂载 Volume，重新部署会丢失数据。建议使用 PostgreSQL 或挂载 Volume。

### Q: 如何更新版本？
A: Railway/Render 会自动拉取最新代码重新部署。Docker 用户执行 `docker-compose pull && docker-compose up -d`。
