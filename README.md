# AI 智能作业批改系统

基于 AI 的多学科作业批改系统，支持数学、语文、英语三科作业的自动批改，提供个性化评语、步骤级过程分、知识点薄弱分析和学情报告。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 📐 **数学批改** | 拍照识别数学题，支持步骤级过程分，自动判对错并生成讲解 |
| 📝 **语文批改** | 作文多维度评分（结构/内容/语言），病句识别 |
| 🔤 **英语批改** | 语法/词汇/连贯性三维度评估，时态纠错 |
| 🧩 **步骤级评分** | 拆解解题步骤，逐步骤判断，部分正确给过程分 |
| 💬 **个性化评语** | 根据学生画像和成绩趋势，生成因人而异的评语 |
| 📊 **学情看板** | 班级知识点热力图、个人学习趋势、薄弱点TOP5 |
| 🗺️ **知识图谱** | 跨学科知识点关联分析，定位薄弱环节 |
| 🗓️ **学习计划** | AI 制定个性化学习计划，针对性查漏补缺 |
| 📷 **拍照批改** | 拍照上传作业，AI 自动识别并批改 |
| 👨‍🏫 **教师端** | 全班错题汇总、知识点统计、学生管理、班级管理 |
| ⚙️ **管理员端** | 系统总览、用户管理、AI 模型热切换 |

## 🚀 5 分钟部署

### Railway（推荐）

1. **Fork** 本仓库
2. 访问 [Railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
3. 添加环境变量 `AGNES_API_KEY`（[免费获取](https://apihub.agnes-ai.com)）
4. 完成！自动生成域名可访问

### Docker（自部署）

```bash
git clone https://github.com/yan06-yin/math-teaching-agent.git
cd math-teaching-agent
cp backend/.env.example backend/.env  # 编辑填入 AGNES_API_KEY
docker-compose up -d
# 访问 http://localhost:8080
```

### 本地开发

```bash
pip install -r requirements.txt
cp backend/.env.example backend/.env
cd frontend && npm install && npm run build && cp -r out ../backend/frontend && cd ..
cd backend && python main.py
# 访问 http://localhost:8080
```

> 📖 完整部署指南（含 Render / Fly.io / docker-compose）：[DEPLOYMENT.md](DEPLOYMENT.md)

## 🔑 默认账号

| 角色 | 账号 | 密码 |
|------|------|------|
| 管理员 | `admin` | `admin123` |

首次部署后请立即修改密码。学生和教师通过页面注册。

## 🏗️ 项目结构

```
math-teaching-agent/
├── Dockerfile                    # 多阶段构建（前端+后端）
├── docker-compose.yml            # 一键自部署
├── requirements.txt              # Python 依赖
│
├── backend/                      # FastAPI 后端
│   ├── main.py                   # 应用入口 + 静态文件托管
│   ├── models.py                 # 数据库模型（15 个 ORM 类）
│   ├── schemas.py                # 请求/响应模型
│   ├── database.py               # 异步数据库（asyncpg/aiosqlite）
│   ├── config.py                 # 环境变量配置
│   ├── seed_admin.py             # 自动创建管理员
│   ├── migrate_db.py             # 数据库迁移脚本
│   ├── routers/                  # API 路由
│   │   ├── auth.py               # 认证（注册/登录/密码重置）
│   │   ├── homework.py           # 作业拍照批改（支持多学科）
│   │   ├── exam.py               # 考试出题/批改（支持多学科）
│   │   ├── analysis.py           # 学习画像/趋势/跨学科报告
│   │   ├── teacher.py            # 教师仪表盘/错题统计/学科筛选
│   │   ├── assignments.py        # 教师发布作业
│   │   ├── classes.py            # 班级管理/邀请码
│   │   └── admin.py              # 系统管理
│   ├── services/                 # 业务服务
│   │   ├── open_model_service.py # AI 多模型调用（自动降级）
│   │   ├── grading_engine.py     # 学科自适应评分引擎
│   │   ├── step_grader.py        # 步骤级过程分评分
│   │   ├── comment_generator.py  # 个性化评语生成
│   │   ├── knowledge_graph_service.py  # 跨学科知识图谱
│   │   ├── exam_service.py       # 出题/批改逻辑
│   │   ├── image_service.py      # 配图生成
│   │   ├── ocr_service.py        # OCR 多学科管线
│   │   └── subject_prompts/      # 各学科评分提示词
│   │       ├── math_prompts.py
│   │       ├── chinese_prompts.py
│   │       └── english_prompts.py
│   └── utils/
│       ├── auth.py               # JWT 认证
│       ├── knowledge_mapper.py   # 多学科知识点映射
│       ├── student_portrait.py   # 学生画像构建
│       └── learning_path.py      # 自适应学习路径
│
└── frontend/                     # Next.js 前端
    └── src/app/
        ├── page.tsx              # 登录/注册页
        ├── student/              # 学生端（6 个页面）
        ├── teacher/              # 教师端（2 个页面）
        └── admin/                # 管理员（1 个页面）
```

## 🧪 测试

```bash
# 单元测试
cd backend && python -m pytest test_multisubject.py -v

# 全链路 E2E 测试（需先启动服务）
python e2e_test.py --url http://localhost:8080
```

## 🛠️ 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 14 + Tailwind CSS + Recharts |
| 后端 | Python FastAPI + 异步 SQLAlchemy 2.0 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） |
| AI | OpenAI 兼容 API（Agnes AI / DeepSeek / GPT 等） |
| OCR | PaddleOCR（支持数学/中文/英文手写识别） |
| 认证 | JWT（python-jose）+ bcrypt |
| 速率限制 | slowapi |
| 部署 | Docker + Railway / Render / Fly.io |

## 📝 常见问题

**Q: 支持哪些学科？** 数学、语文、英语三科。上传时选择对应学科即可。

**Q: AI 批改报错？** 检查 `AGNES_API_KEY` 是否设置。管理后台可切换其他 AI 模型。

**Q: 可以换 AI 模型吗？** 可以！管理后台 → AI 模型，添加任意 OpenAI 兼容 API 即可。

**Q: 数据会丢失吗？** SQLite 在重新部署时会丢失，建议挂载 Volume 或使用 PostgreSQL。详见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## License

MIT