# 数学教学智能体

基于 Agnes AI 的数学教学辅助系统，支持作业拍照批改、智能出题组卷、个性化诊断报告与学习计划。

## 功能特性

- 📸 **拍照批改** — 学生上传作业照片，AI 自动识别、批改、生成评语和错题讲解
- 📝 **智能出题** — 根据学生薄弱知识点自动生成试卷，支持难度和题量调节
- 📊 **诊断报告** — 考试后自动生成学习诊断报告，可视化呈现学习趋势
- 🗓️ **学习计划** — AI 制定个性化学习计划，帮助学生查漏补缺
- 👨‍🏫 **教师端** — 全班错题汇总、知识点薄弱热力图、学生问题排行
- ⚙️ **管理员端** — 系统总览、教师/班级/学生管理、AI 模型配置切换

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 14 + Tailwind CSS + Recharts |
| 后端 | Python FastAPI + SQLAlchemy |
| 数据库 | PostgreSQL（生产）/ SQLite（开发） |
| AI | Agnes AI / 兼容 OpenAI API 的任意模型 |
| OCR | EasyOCR（通过 MCP 服务器） |

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 在 backend/ 目录下创建 .env 文件
cp .env.example .env
```

`.env` 内容：
```env
# Agnes AI API（必填，或在管理后台配置）
AGNES_API_KEY=your_api_key_here

# JWT 密钥（生产环境务必修改）
SECRET_KEY=math-teaching-secret-key-change-in-production

# 其他保持默认即可
```

### 3. 启动后端

```bash
cd backend
uvicorn main:app --reload --port 8000
```

后端启动后访问 http://localhost:8000/docs 查看 API 文档。

### 4. 安装前端依赖

```bash
cd frontend
npm install
```

### 5. 启动前端

```bash
npm run dev
```

前端启动后访问 http://localhost:3000。

## 项目结构

```
math-teaching-agent/
├── frontend/                  # Next.js 前端
│   ├── src/app/
│   │   ├── page.tsx           # 登录页
│   │   ├── student/           # 学生端
│   │   │   ├── dashboard/     # 学生主页
│   │   │   ├── upload/        # 作业上传
│   │   │   ├── exam/          # 智能考试
│   │   │   ├── report/        # 诊断报告
│   │   │   └── plan/          # 学习计划
│   │   └── teacher/           # 教师端
│   │       ├── dashboard/     # 教师仪表盘
│   │       └── assignments/   # 作业发布
│   │   └── admin/             # 管理员端
│   │       └── dashboard/     # 管理后台
│   └── package.json
├── backend/                   # FastAPI 后端
│   ├── main.py                # 应用入口
│   ├── models.py              # 数据库模型
│   ├── schemas.py             # 请求/响应模型
│   ├── routers/               # API 路由
│   │   ├── auth.py            # 认证
│   │   ├── homework.py        # 作业批改
│   │   ├── exam.py            # 考试出题
│   │   ├── analysis.py        # 学习分析
│   │   ├── teacher.py         # 教师数据
│   │   ├── assignments.py     # 作业发布
│   │   ├── classes.py         # 班级管理
│   │   └── admin.py           # 系统管理
│   └── services/              # 业务服务
│       ├── agnes_service.py   # AI API 调用
│       ├── exam_service.py    # 出题服务
│       ├── grading_service.py # 批改流程编排（已弃用）
│       └── ocr_service.py     # OCR 文字提取
└── database/                  # SQLite 数据库（本地开发自动生成）
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 学生注册 |
| POST | `/api/auth/login` | 学生登录 |
| POST | `/api/auth/teacher/login` | 教师/管理员登录 |
| POST | `/api/auth/teacher/register` | 教师注册 |
| POST | `/api/homework/upload` | 上传作业（异步批改） |
| GET | `/api/homework/my` | 我的作业列表 |
| POST | `/api/exam/generate` | 生成试卷（异步） |
| POST | `/api/exam/:id/submit` | 提交答卷 |
| GET | `/api/exam/my` | 我的考试记录 |
| GET | `/api/exam/:id/status` | 考试批改状态轮询 |
| GET | `/api/exam/:id/report` | 诊断报告 |
| GET | `/api/analysis/student/:id` | 学生画像 |
| GET | `/api/teacher/dashboard` | 教师仪表盘 |
| GET | `/api/teacher/errors` | 错题汇总 |
| GET | `/api/teacher/students` | 学生列表 |
| POST | `/api/classes/` | 创建班级 |
| POST | `/api/classes/:id/invite-codes` | 生成邀请码 |
| POST | `/api/classes/join` | 学生加入班级 |
| GET | `/api/admin/dashboard` | 系统总览（管理员）|
| GET/POST | `/api/admin/ai-providers` | AI 模型配置管理 |

## AI 模型配置

在管理后台（admin/dashboard → AI 模型）可以添加和切换 AI 模型，支持任何兼容 OpenAI API 的服务：

- **Agnes AI** — `https://apihub.agnes-ai.com/v1`（默认）
- **DeepSeek** — `https://api.deepseek.com/v1`
- **OpenAI** — `https://api.openai.com/v1`

API Key 可在 .env 文件或管理后台配置。

## 注意事项

- 首次启动会自动创建数据库和所有数据表
- 生产环境（Railway）使用 PostgreSQL，本地开发默认 SQLite
- 管理员账号：`admin / admin123`（首次启动自动创建）
- AI 批改为异步处理，前端需轮询等待结果

