# 🚀 一键部署指南

## 架构说明

本项目采用**单容器架构**，一个部署包含所有组件：

```
┌──────────────────────────────────────────┐
│              Railway / Docker             │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  前端     │  │  后端     │  │ 数据库  │ │
│  │ Next.js  │→ │ FastAPI  │→ │ SQLite │ │
│  │ 静态页面  │  │ Python   │  │  文件   │ │
│  └──────────┘  └──────────┘  └────────┘ │
│       ↑              ↑            ↑      │
│       │              │            │      │
│   浏览器访问     AI API调用    自动创建   │
│                                          │
│  端口：一个端口对外，同时提供页面和 API    │
└──────────────────────────────────────────┘
```

**部署一个容器 = 前端 + 后端 + 数据库全部就绪**

---

## 方案一：Railway 部署（推荐）

### 前置准备

1. GitHub 账号（免费注册：https://github.com）
2. Railway 账号（用 GitHub 登录：https://railway.app）
3. Agnes AI API Key（免费注册：https://apihub.agnes-ai.com）

### 部署步骤（共 5 步，约 5 分钟）

#### 第 1 步：Fork 代码仓库

打开 https://github.com/yan06-yin/math-teaching-agent

点击右上角 **Fork** 按钮 → 选择你的账号 → 点击 **Create fork**

> Fork = 把代码复制到你自己的 GitHub 账号下

#### 第 2 步：创建 Railway 项目

1. 打开 https://railway.app
2. 点击 **Login** → 选择 **Login with GitHub**
3. 点击 **New Project** → **Deploy from GitHub Repo**
4. 在列表中选择你刚 Fork 的仓库 `你的用户名/math-teaching-agent`
5. Railway 会自动开始构建（检测到 Dockerfile）

> Railway = 云服务器平台，免费提供服务器帮你跑代码

#### 第 3 步：添加环境变量

构建开始后，点击项目进入详情页：

1. 点击顶部的 **Variables** 标签
2. 点击 **New Variable**
3. 添加以下变量：

| Variable（变量名） | Value（值） | 说明 |
|-------------------|------------|------|
| `AGNES_API_KEY` | 你的 API Key | **必填**，AI 批改功能需要 |

> 环境变量 = 给程序传配置的方式，类似软件的注册码

#### 第 4 步：获取访问域名

1. 点击顶部的 **Settings** 标签
2. 找到 **Networking** 部分
3. 点击 **Generate Domain**
4. 获得一个免费域名，类似：`math-agent-production-xxxx.up.railway.app`

> 域名 = 你系统的访问地址，别人打开这个网址就能用

#### 第 5 步：完成！

打开域名，使用默认管理员账号登录：

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员 | `admin` | `admin123` |

登录后建议：
1. 在 **AI 模型** 页面确认 API Key 配置正确
2. 修改管理员密码
3. 注册教师账号，创建班级
4. 学生通过邀请码注册加入

---

## 方案二：Docker 自部署

适用于有自己的服务器（VPS、NAS、校园服务器等）。

### 一行命令启动

```bash
# 克隆代码
git clone https://github.com/yan06-yin/math-teaching-agent.git
cd math-teaching-agent

# 创建配置文件
cp backend/.env.example backend/.env
# 用编辑器打开 backend/.env，填入 AGNES_API_KEY=你的key

# 一键启动（自动构建 + 启动）
docker-compose up -d
```

启动后访问 **http://你的服务器IP:8080**

### docker-compose.yml 说明

```yaml
services:
  app:                          # 一个服务包含所有组件
    build: .                    # 根据 Dockerfile 构建
    ports:
      - "8080:8000"             # 对外端口 8080
    volumes:
      - app-data:/app/database  # 数据库持久化（重启不丢数据）
      - app-uploads:/app/uploads # 上传的图片持久化
    env_file:
      - backend/.env            # 读取配置文件
```

### 常用命令

```bash
docker-compose up -d      # 启动（后台运行）
docker-compose down        # 停止
docker-compose logs -f     # 查看日志
docker-compose restart     # 重启
```

---

## 方案三：本地开发运行

不需要 Docker，直接用 Python 运行（适合开发调试或课堂演示）。

```bash
# 1. 克隆代码
git clone https://github.com/yan06-yin/math-teaching-agent.git
cd math-teaching-agent

# 2. 安装后端依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 AGNES_API_KEY

# 4. 构建前端（需要 Node.js）
cd frontend
npm install
npm run build
cp -r out ../backend/frontend
cd ..

# 5. 启动
cd backend
python main.py
```

启动后访问 **http://localhost:8080**

---

## 获取免费 AI API Key

本项目的 AI 批改、出题功能需要调用 AI 服务。

### Agnes AI（推荐，免费）

1. 打开 https://apihub.agnes-ai.com
2. 点击 **Sign Up** 注册（支持 GitHub 登录）
3. 登录后进入 **API Keys** 页面
4. 点击 **Create API Key**，复制生成的 Key
5. 将 Key 填入环境变量 `AGNES_API_KEY`

> 也可以在系统管理后台 → AI 模型中切换为 DeepSeek、GPT 等其他模型。

---

## 数据持久化说明

| 组件 | 存储方式 | 重启是否丢失 |
|------|---------|-------------|
| 数据库 | SQLite 文件 `/app/database/` | ⚠️ 容器重建会丢失 |
| 上传的图片 | `/app/uploads/` | ⚠️ 容器重建会丢失 |
| 代码 | Docker 镜像内 | 不丢失 |

### 防止数据丢失

**Railway 用户**：添加 Volume
1. 项目 → Settings → Volumes → New Volume
2. Mount Path: `/app/database`

**Docker 用户**：docker-compose.yml 已配置 volume，数据自动持久化。

**进阶**：使用 PostgreSQL（Railway 一键添加 Database 服务）。

---

## 常见问题

### Q: 部署要花钱吗？
A: 不花钱。Railway 免费 $5/月额度，够小型项目用。Agnes AI API 免费注册。

### Q: 前端和后端是分开部署的吗？
A: 不是。前端打包成静态文件，由后端一起提供服务。只需部署一个容器。

### Q: 数据库需要单独安装吗？
A: 不需要。默认用 SQLite（一个文件），自动创建。如需更强性能可加 PostgreSQL。

### Q: 支持哪些 AI 模型？
A: 支持所有兼容 OpenAI API 的模型：Agnes AI（默认）、DeepSeek、GPT-4、Claude 等。在管理后台切换。

### Q: 怎么更新版本？
A: Railway 用户：push 代码到 GitHub，自动重新部署。Docker 用户：`git pull && docker-compose up -d --build`。
