# 数学教学智能体

基于 AI 的数学教学辅助系统，专为初中数学老师设计。支持作业拍照批改、智能出题组卷、诊断报告与个性化学习计划。

## 功能特性

- 📸 **拍照批改** — 学生上传作业照片，AI 自动识别并批改，生成评语和错题讲解
- 📝 **智能出题** — 根据学生薄弱知识点自动生成试卷，支持调整难度和题量
- 📊 **诊断报告** — 考试后自动生成学习诊断，可视化呈现学习趋势
- 🗓️ **学习计划** — AI 制定两周个性化学习计划，帮助学生查漏补缺
- 👨‍🏫 **教师端** — 全班错题汇总、知识点薄弱热力图、学生问题排行
- ⚙️ **管理员端** — 系统总览、教师/班级/学生管理、AI 模型配置切换

## 快速部署（Railway）

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template)

### 1. 部署步骤

1. 将代码推送到 GitHub 仓库
2. 在 [Railway.app](https://railway.app) 新建项目，连接 GitHub 仓库
3. Railway 自动检测 Dockerfile 并构建
4. 在 Railway → **Variables** 添加环境变量：

| 变量 | 必填 | 说明 |
|------|------|------|
| `AGNES_API_KEY` | ✅ | Agnes AI API Key（[获取](https://apihub.agnes-ai.com)） |
| `DATABASE_URL` | 自动 | Railway PostgreSQL 自动注入 |

5. 部署完成后打开生成的域名即可使用

### 2. 本地开发

```bash
# 后端
cd backend
cp .env.example .env  # 编辑 .env 填入 AGNES_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 前端（可选，后端已内嵌静态页面）
cd frontend
npm install
npm run dev
```

### 3. 管理员账号

首次启动自动创建：
- 用户名：`admin`
- 密码：`admin123`

登录后请先在 **AI 模型** 页面配置 API Key。

## 项目结构

```
backend/                     # FastAPI 后端
├── main.py                  # 应用入口 + 静态文件托管
├── models.py                # 数据库模型（15 个 ORM 类）
├── schemas.py               # 请求/响应模型
├── database.py              # 异步数据库连接（asyncpg/aiosqlite）
├── routers/                 # API 路由（8 个模块）
│   ├── auth.py              # 认证（注册/登录/密码重置）
│   ├── homework.py          # 作业异步批改
│   ├── exam.py              # 考试异步出题/批改
│   ├── analysis.py          # 学习画像/趋势
│   ├── teacher.py           # 教师仪表盘/错题统计
│   ├── assignments.py       # 教师发布作业
│   ├── classes.py           # 班级管理/邀请码
│   └── admin.py             # 系统管理
├── services/                # 业务服务
│   ├── open_model_service.py # AI 多模型调用（降级/回退）
│   ├── exam_service.py      # 出题/批改逻辑
│   ├── image_service.py     # 配图生成
│   └── ocr_service.py      # OCR 文字提取（可选）
└── utils/
    ├── auth.py              # JWT 认证依赖
    └── knowledge_mapper.py  # 知识点规范化
```

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 14 + Tailwind CSS + Recharts |
| 后端 | Python FastAPI + 异步 SQLAlchemy |
| 数据库 | PostgreSQL（生产）/ SQLite（开发） |
| AI 接口 | OpenAI 兼容 API（Agnes / DeepSeek / GPT 等） |
| 测试 | pytest（24 单元测试）+ E2E 全链路测试（71 项） |

## 测试覆盖

```bash
cd backend
python -m pytest test_api.py test_comprehensive.py -v
# 输出：24 passed

# 全链路 E2E 测试（需要运行中的服务）
python ../e2e_test.py --url http://localhost:8000
# 输出：71 passed
```

### 测试覆盖范围

| 模块 | 测试项数 | 覆盖内容 |
|------|---------|---------|
| 健康检查 | 2 | 状态、数据库类型 |
| 学生 | 10 | 注册/重复/短密码/登录/密码重置 |
| 考试系统 | 8 | 出题/轮询/提交/批改/重复提交/报告 |
| 作业 | 5 | 上传/列表/状态/结果/404 |
| 学生分析 | 3 | 画像/趋势/权限 |
| 教师端 | 9 | 注册/班级/邀请码 |
| 班级 | 7 | 创建/邀请码/加入/重复/无效码 |
| 作业发布 | 6 | 发布/查看/提交/重复 |
| 教师管理 | 5 | 学生列表/信息/错题/汇总 |
| 管理员 | 8 | 登录/仪表盘/CRUD/AI模型 |
| 安全 | 4 | 未登录/跨角色/伪造token |
| 边界 | 4 | 不存在ID/跨学生/长学号/删除 |

## 常见问题

**Q: 为什么出题很慢？**
A: 出题需要调用 AI API，通常 3-5 秒完成。如果勾选了"高清配图"，每题额外加 5-10 秒。默认的 SVG 配图是免费的。

**Q: 学生删了再注册，旧数据还在吗？**
A: 不再。删除学生时会清空所有关联数据（考试、作业、错题等），重新注册后是完全新的开始。

**Q: 可以换别的 AI 模型吗？**
A: 可以。管理员登录后，在 AI 模型管理页面添加任意兼容 OpenAI API 的模型（DeepSeek、GPT 等），保存后立即生效，无需重启。

**Q: 部署后登录不上？**
A: 确保在 Railway 环境变量中设置了 `AGNES_API_KEY`，否则 AI 功能不可用但登录应正常。管理员密码为 `admin123`。

## License

MIT
