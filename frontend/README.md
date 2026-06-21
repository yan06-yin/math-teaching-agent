# 数学教学智能体 - 前端

基于 Next.js 14 的数学教学辅助系统前端。

## 启动

```bash
npm install
npm run dev
```

访问 http://localhost:3000

## 构建

```bash
npm run build
```

构建产物自动复制到 `backend/frontend/` 由 FastAPI 托管。

## 页面

| 路径 | 说明 |
|------|------|
| `/` | 登录/注册 |
| `/student/dashboard` | 学生主页 |
| `/student/exam` | 智能考试 |
| `/student/upload` | 拍照批改 |
| `/student/report` | 诊断报告 |
| `/student/plan` | 学习计划 |
| `/student/assignments` | 教师布置的作业 |
| `/teacher/dashboard` | 教师仪表盘 |
| `/teacher/assignments` | 作业发布 |
| `/admin/dashboard` | 系统管理后台 |

