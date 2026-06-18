# 数学教学智能体 — Coze 插件部署与配置指南

你将把本项目的后端部署到云端服务器，然后作为 **Coze 插件** 接入你的 Coze Bot。

整体流程：

```
Coze Bot → Coze 插件 → 你的服务器 (FastAPI) → SQLite + Coze API
```

---

## 一、环境准备

### 1. 安装 Python 依赖

```bash
cd backend

# 推荐在虚拟环境安装
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

> **注意**：PaddleOCR 安装包较大（约 1GB），首次安装可能较慢。如果不想安装 PaddleOCR（用不到拍照识别功能），可以在 `requirements.txt` 中去掉 `paddlepaddle` 和 `paddleocr`，OCR 接口返回空字符串但不影响其他功能。

### 2. 配置环境变量

创建 `backend/.env` 文件：

```env
# === Coze API（必填）===
COZE_BOT_ID=你的CozeBotID
COZE_TOKEN=你的CozePersonalAccessToken

# === JWT 密钥 ===
SECRET_KEY=请修改为随机字符串

# === 服务器配置 ===
HOST=0.0.0.0
PORT=8000
```

---

## 二、部署方式（二选一）

### 方式 A：部署到 Railway（最简单，推荐快速验证）

[Railway](https://railway.com) 提供免费额度，支持自动 HTTPS。

#### 步骤

1. **把代码推到 GitHub**
   ```bash
   git init
   git add .
   git commit -m "init"
   # 在 GitHub 创建仓库后：
   git remote add origin https://github.com/你的用户名/math-teaching-agent.git
   git push -u origin main
   ```

2. **在 Railway 上创建项目**
   - 登录 [Railway](https://railway.com)
   - New Project → Deploy from GitHub repo → 选择你的仓库
   - 添加 Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Railway 会自动分配域名，比如 `https://math-agent.up.railway.app`

3. **添加环境变量**
   - 在 Railway Dashboard 的 Variables 中添加：
     - `COZE_BOT_ID` = 你的 Bot ID
     - `COZE_TOKEN` = 你的 Personal Access Token
     - `SECRET_KEY` = 随机字符串

4. **Root Directory 设置**
   - 如果仓库根目录就是 `backend/` 所在目录，在 Railway Service 设置中：Root Directory 留空
   - Procfile（在仓库根目录创建）：
     ```
     web: cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
     ```

5. **部署完成**，得到 URL 如 `https://math-agent.up.railway.app`

6. **验证插件接口可访问**：
   浏览器打开 `https://你的域名/plugin/health` → 应该看到 `{"status": "ok", "service": "..."}`

### 方式 B：部署到阿里云 ECS / 腾讯云（生产环境）

适合需要稳定运行、数据持久化的场景。

#### 步骤

1. **购买服务器**（最低配置：2核4G，Ubuntu 22.04）

2. **SSH 登录，安装依赖**
   ```bash
   # Python 3.10+
   sudo apt update
   sudo apt install python3-pip python3-venv nginx -y

   # 可选：安装 supervisor 管理进程
   sudo apt install supervisor -y
   ```

3. **克隆代码并配置**
   ```bash
   git clone https://github.com/你的用户名/math-teaching-agent.git
   cd math-teaching-agent/backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # 创建 .env 文件
   cat > .env << EOF
   COZE_BOT_ID=你的BotID
   COZE_TOKEN=你的Token
   SECRET_KEY=随机字符串
   EOF
   ```

4. **启动服务（使用 supervisor）**
   ```bash
   sudo nano /etc/supervisor/conf.d/math-agent.conf
   ```

   文件内容：
   ```ini
   [program:math-agent]
   command=/root/math-teaching-agent/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
   directory=/root/math-teaching-agent/backend
   autostart=true
   autorestart=true
   user=root
   ```

   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start math-agent
   ```

5. **配置 Nginx 反代 + HTTPS（推荐用 acme.sh 或 certbot）**
   ```bash
   sudo nano /etc/nginx/sites-available/math-agent
   ```

   文件内容：
   ```nginx
   server {
       listen 80;
       server_name 你的域名.com;  # 如果有域名
       
       client_max_body_size 20M;
       
       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

   ```bash
   sudo ln -s /etc/nginx/sites-available/math-agent /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

---

## 三、Coze 插件配置（核心步骤）

你的服务器部署好之后，在 Coze 平台把它注册为插件。

### 第 1 步：登录 Coze 开发者平台

打开 [https://www.coze.cn/open](https://www.coze.cn/open) → **插件** → **创建插件**

### 第 2 步：填写插件基本信息

| 字段 | 值 |
|------|------|
| 插件名称 | `数学教学智能体` |
| 插件描述 | `数学作业批改、智能出题、学习诊断、OCR 识别` |
| 插件图标 | 可以上传一个数学图标 |
| API 接入方式 | 选择 **OpenAPI** 模式 |

### 第 3 步：配置 API

在 **API 配置** 页面：

- **服务器地址**：填写你的服务器根 URL
  - Railway 示例：`https://math-agent.up.railway.app`
  - 阿里云示例：`http://你的公网IP:8000` 或 `https://你的域名.com`

- **鉴权方式**：选择 **无鉴权（No Auth）**
  > 插件接口已通过 Coze 自己的鉴权保护，不需要额外鉴权

### 第 4 步：逐个添加 API 接口

点击 **添加 API**，依次添加以下 6 个接口：

#### 接口 1：OCR 图片文字识别

| 字段 | 值 |
|------|------|
| 名称 | `OCR 识别` |
| 描述 | `从图片中提取文字，支持中文和数学公式` |
| URL | `/plugin/ocr` |
| 方法 | `POST` |
| 请求参数 | `image_url`（string, form-data）— 图片 URL |
| 返回示例 | `{"success": true, "text": "1. x+2=5\n2. 3y=9", "text_length": 18}` |

#### 接口 2：AI 批改作业

| 字段 | 值 |
|------|------|
| 名称 | `批改作业` |
| 描述 | `AI 自动批改数学作业，返回评分和每道题的批改详情` |
| URL | `/plugin/grade` |
| 方法 | `POST` |
| 请求参数 | `student_name`（string）, `school_level`（string）, `questions_and_answers`（string） |
| 返回示例 | `{"success": true, "data": {"score": 85, "comments": "...", "details": [...]}}` |

#### 接口 3：智能出题

| 字段 | 值 |
|------|------|
| 名称 | `智能出题` |
| 描述 | `根据薄弱知识点和难度自动生成数学试卷` |
| URL | `/plugin/generate-exam` |
| 方法 | `POST` |
| 请求参数 | `school_level`（string）, `knowledge_points`（string, 逗号分隔）, `difficulty`（int 1-5）, `question_count`（int 1-50） |
| 返回示例 | `{"success": true, "data": {"title": "...", "questions": [...]}}` |

#### 接口 4：学习诊断

| 字段 | 值 |
|------|------|
| 名称 | `学习诊断` |
| 描述 | `根据学生近期考试或作业表现生成诊断报告，包含优劣势分析` |
| URL | `/plugin/diagnose` |
| 方法 | `POST` |
| 请求参数 | `student_name`（string）, `school_level`（string）, `performance_data`（string） |
| 返回示例 | `{"success": true, "data": {"strengths": [...], "weaknesses": [...], "trend": "...", "recommendation": "..."}}` |

#### 接口 5：学习计划

| 字段 | 值 |
|------|------|
| 名称 | `学习计划` |
| 描述 | `根据薄弱知识点生成两周个性化学习计划` |
| URL | `/plugin/learning-plan` |
| 方法 | `POST` |
| 请求参数 | `student_name`（string）, `school_level`（string）, `weak_points`（string, 逗号分隔） |
| 返回示例 | `{"success": true, "data": {"plan": [...], "milestones": [...]}}` |

#### 接口 6：知识点查询

| 字段 | 值 |
|------|------|
| 名称 | `知识点查询` |
| 描述 | `将文本归类到标准初中/高中数学知识点` |
| URL | `/plugin/knowledge-point` |
| 方法 | `GET` |
| 请求参数 | `text`（string, query）, `level`（string, query） |
| 返回示例 | `{"success": true, "original": "二次方程", "standard": "一元二次方程", "info": {...}}` |

### 第 5 步：测试每个接口

在 Coze 插件配置页面，每个接口右侧都有 **测试** 按钮。

示例测试：
- **OCR 识别**：传入一张数学题图片的 URL → 应该返回识别出的文本
- **批改作业**：传入 `school_level=初中`，`questions_and_answers=解方程 2x+3=7，答案：x=2` → 返回批改结果
- **智能出题**：传入 `school_level=高中`，`knowledge_points=导数` → 生成导数相关题目

### 第 6 步：发布插件

- 确认 6 个接口全部测试通过
- 点击 **发布**
- 发布后你的 Coze Bot 就可以通过 **工作流（Workflow）** 调用插件了

---

## 四、在 Coze Bot 中使用插件

### 方式 A：在 Prompt 中引用（最简单）

在 Coze Bot 的 **系统提示词（Persona & Prompt）** 中加入：

```
# 能力说明
你是一个数学教学助手，具备以下能力（通过插件实现）：
1. OCR 识别：当用户上传图片时，调用 OCR 识别插件提取文字
2. 作业批改：批改数学作业，给出评分和解析
3. 智能出题：针对薄弱知识点生成试卷
4. 学习诊断：分析学生表现，生成学习诊断报告
5. 学习计划：生成个性化学习计划
```

然后在 Bot 的 **插件** 设置中关联你的插件。Coze Bot 会自动根据用户请求选择合适的插件调用。

### 方式 B：通过工作流（Workflow）编排（推荐）

创建 Bot 的时间添加 **工作流（Workflow）**：

1. 在 Bot 编辑页面 → **工作流** → **新建工作流**
2. 在画布上拖入 **代码节点** 和 **插件节点**
3. 示例工作流：**拍照批改流程**
   ```
   用户输入（图片URL）→ OCR识别插件 → 判断是否有文字
       ├─ 有文字 → 批改作业插件 → 返回结果给用户
       └─ 无文字 → 提醒用户重新拍摄或手动输入
   ```

4. 示例工作流：**智能出题+诊断流程**
   ```
   用户要求"出题" → 查询学生薄弱知识点（如有）
       → 智能出题插件 → 显示题目给用户
       → 用户提交答案 → 批改作业插件
       → 评分<70分 → 学习诊断插件 → 学习计划插件
   ```

---

## 五、插件 API 接口速查表

| 接口 | 方法 | URL | 主要参数 | 用途 |
|------|------|-----|----------|------|
| 健康检查 | GET | `/plugin/health` | 无 | 确认插件可访问 |
| OCR 识别 | POST | `/plugin/ocr` | `image_url` | 图片→文字 |
| 批改作业 | POST | `/plugin/grade` | `student_name`, `school_level`, `questions_and_answers` | AI 批改 |
| 智能出题 | POST | `/plugin/generate-exam` | `school_level`, `knowledge_points`, `difficulty`, `question_count` | 生成试卷 |
| 学习诊断 | POST | `/plugin/diagnose` | `student_name`, `school_level`, `performance_data` | 诊断报告 |
| 学习计划 | POST | `/plugin/learning-plan` | `student_name`, `school_level`, `weak_points` | 学习计划 |
| 知识点查询 | GET | `/plugin/knowledge-point` | `text`, `level` | 知识点映射 |

---

## 六、常见问题

### Q1：部署后插件调用失败，返回 502 / 超时

可能原因：
- 服务器防火墙没开放 8000 端口 → 检查云服务商安全组规则
- Coze API 调用超时 → 后端设置了 120 秒超时，Coze 插件本身也有超时限制
- OCR 首次调用加载模型较慢（PaddleOCR 首次需要加载模型文件）

### Q2：OCR 识别不了中文/数学公式

PaddleOCR 对印刷体中文效果好，对手写体效果一般。如果图片中的文字是手写的：
- 建议让用户拍照时尽量清晰、光线均匀
- 可以在 Coze Bot 的 Prompt 中加一句："如果 OCR 结果看起来不完整，请提示用户重新拍照或手动输入题目"

### Q3：我不想装 PaddleOCR（太大了）

完全可以。去掉 PaddleOCR 依赖后，OCR 接口返回空字符串，其他功能（出题、批改、诊断、学习计划）不受影响。

修改方法：
1. 从 `requirements.txt` 中去掉 `paddlepaddle` 和 `paddleocr`
2. 用户可以通过手动输入题目的方式使用批改功能

### Q4：如何测试服务器是否正常工作？

```bash
# 健康检查
curl https://你的域名/plugin/health

# 测试批改接口
curl -X POST https://你的域名/plugin/grade \
  -d "student_name=小明" \
  -d "school_level=初中" \
  -d "questions_and_answers=解方程 2x+3=7，答案：x=2"
```

### Q5：Coze 插件免费吗？

- Coze 平台目前对插件数量没有限制
- Railway 免费套餐每月有 500 小时运行时间和 1GB 带宽，足够个人使用
- 如果需要 PaddleOCR，建议用阿里云最低配服务器（约 50元/月）

---

## 七、项目维护

```bash
# 更新代码并重启
git pull origin main
cd backend
source venv/bin/activate
pip install -r requirements.txt  # 如果有新依赖
# Railway 会自动重新部署
# 阿里云：sudo supervisorctl restart math-agent
```

---

**准备好后，你可以先在本地测试插件 API 是否可用：**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

浏览器打开 `http://localhost:8000/docs` 查看所有 API（包括插件接口的文档）。
或直接访问 `http://localhost:8000/plugin/health` 确认服务正常。
