# 数学教学智能体

基于 Coze AI 的数学教学辅助系统，支持作业拍照批改、智能出题组卷、个性化诊断报告与学习计划。

## 功能特性

- 📸 **拍照批改** — 学生上传作业照片，AI 自动识别、批改、生成评语和错题讲解
- 📝 **智能出题** — 根据学生薄弱知识点自动生成试卷，支持难度和题量调节
- 📊 **诊断报告** — 考试后自动生成学习诊断报告，可视化呈现学习趋势
- 🗓️ **学习计划** — AI 制定个性化学习计划，帮助学生查漏补缺
- 👨‍🏫 **教师端** — 全班错题汇总、知识点薄弱热力图、学生问题排行

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 14 + Tailwind CSS + Recharts |
| 后端 | Python FastAPI + SQLAlchemy |
| 数据库 | SQLite |
| AI | Coze API |
| OCR | PaddleOCR |

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
# 在 backend/ 目录下创建 .env 文件
cp .env.example .env  # 如果没有示例，手动创建
```

`.env` 内容：
```env
# Coze API（必填）
COZE_BOT_ID=your_bot_id_here
COZE_TOKEN=your_coze_personal_access_token_here

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
│   │   ├── page.js            # 登录页
│   │   ├── student/           # 学生端
│   │   │   ├── dashboard/     # 学生主页
│   │   │   ├── upload/        # 作业上传
│   │   │   ├── exam/          # 智能考试
│   │   │   ├── report/        # 诊断报告
│   │   │   └── plan/          # 学习计划
│   │   └── teacher/           # 教师端
│   │       └── dashboard/     # 教师仪表盘
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
│   │   └── teacher.py         # 教师数据
│   └── services/              # 业务服务
│       ├── coze_service.py    # Coze API 调用
│       ├── ocr_service.py     # OCR 文字提取
│       ├── grading_service.py # 批改流程编排
│       └── exam_service.py    # 出题服务
└── database/                  # SQLite 数据库（自动生成）
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 学生注册 |
| POST | `/api/auth/login` | 学生登录 |
| POST | `/api/auth/teacher/login` | 教师登录 |
| POST | `/api/homework/upload` | 上传作业（触发批改） |
| GET | `/api/homework/my` | 我的作业列表 |
| POST | `/api/exam/generate` | 生成试卷 |
| POST | `/api/exam/:id/submit` | 提交答卷 |
| GET | `/api/exam/my` | 我的考试记录 |
| GET | `/api/analysis/student/:id` | 学生画像 |
| GET | `/api/teacher/dashboard` | 教师仪表盘 |
| GET | `/api/teacher/errors` | 错题汇总 |

## Coze Bot 配置

1. 在 [Coze 平台](https://www.coze.cn) 创建一个 Bot
2. 设置系统提示词（参考 `backend/services/coze_service.py` 中的四个 Prompt 模板）
3. 获取 Bot ID 和个人访问令牌（Personal Access Token）
4. 填入后端的 `.env` 配置文件

## 注意事项

- PaddleOCR 需要 Python 3.8-3.11，安装可能需要较长时间
- Coze API 调用需要有效的 Personal Access Token
- 首次启动会自动创建 SQLite 数据库和所有数据表
- 生产环境建议使用 PostgreSQL/MySQL 替换 SQLite
# Build timestamp: 20260621082522
