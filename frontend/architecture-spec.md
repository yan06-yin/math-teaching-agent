# Math Teaching AI Agent — System Architecture Specification

> **Version**: 1.0
> **Date**: 2026-06-18
> **Platform**: Coze AI Agent + Independent Web Application + SQLite Backend

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Tech Stack Recommendations](#2-tech-stack-recommendations)
3. [Module Design](#3-module-design)
4. [Database Schema (SQLite)](#4-database-schema-sqlite)
5. [API Design](#5-api-design)
6. [Coze Bot Design](#6-coze-bot-design)
7. [Frontend Page Design](#7-frontend-page-design)
8. [Deployment & Operations](#8-deployment--operations)
9. [Security Considerations](#9-security-considerations)

---

## 1. System Architecture Overview

### 1.1 Component Diagram

```
+-----------------------------------------------------------------------+
|                        CLIENT LAYER                                     |
|                                                                        |
|  +------------------+   +------------------+   +----------------+      |
|  |  Student Web App  |   | Teacher Web App  |   |  Mobile (PWA) |      |
|  |  (React/Next.js) |   |  (React/Next.js) |   |  (Optional)   |      |
|  +--------+---------+   +--------+---------+   +-------+--------+      |
|           |                      |                      |              |
+-----------+----------------------|----------------------|--------------+
            |                      |                      |
            v                      v                      v
+-----------------------------------------------------------------------+
|                       API GATEWAY / BACKEND                              |
|                                                                        |
|  +--------------------------------------------------------------+     |
|  |              FastAPI (Python) / Express (Node.js)             |     |
|  |                                                              |     |
|  |  +----------+ +----------+ +----------+ +---------------+   |     |
|  |  |  Auth    | | Homework | |   Exam   | |   Analysis    |   |     |
|  |  | Service  | | Service  | | Service  | |   Service     |   |     |
|  |  +----------+ +----------+ +----------+ +---------------+   |     |
|  |                                                              |     |
|  |  +----------+ +----------+ +-------------------------------+ |     |
|  |  |  OCR     | |  Coze    | |         Teacher               | |     |
|  |  | Engine   | | Adapter  | |       Dashboard Svc           | |     |
|  |  +----------+ +----------+ +-------------------------------+ |     |
|  +--------------------------------------------------------------+     |
|                              |                                         |
+------------------------------|-----------------------------------------+
                               |
              +----------------+----------------+
              v                v                v
   +-------------------+ +--------------+  +------------------+
   |   SQLite DB       | |  Coze Cloud  |  |  Object Storage  |
   |   (Local File)    | |   API        |  |  (Image Uploads) |
   +-------------------+ +--------------+  +------------------+
```

### 1.2 Data Flow (Grading Pipeline)

```
Student takes photo
       |
       v
[Frontend] -> POST /api/homework/upload (multipart/form-data)
       |
       v
[Backend]  -> Save photo to local storage / object storage
       |
       v
[Backend]  -> Trigger OCR (EasyOCR / Tesseract) to extract text
       |
       v
[Backend]  -> Format extracted text + original image -> Coze API
       |
       v
[Coze API] -> LLM grades homework, generates comments, identifies errors
       |
       v
[Backend]  -> Parse Coze response -> Store in SQLite
       |
       v
[Frontend] -> Display graded result + personalized feedback
```

### 1.3 What Runs Where

| Component                   | Platform       | Rationale                                         |
| --------------------------- | -------------- | ------------------------------------------------- |
| Student Web App             | Independent    | Full control over UX, branding, and data flow     |
| Teacher Dashboard           | Independent    | Admin-facing, needs tight integration with DB     |
| API Server (FastAPI)        | Independent    | Lightweight, great async support, easy SQLite     |
| SQLite Database             | Independent    | Zero-config, file-based, perfect for mid-scale    |
| Image Storage               | Local disk     | Simplest initial approach; swap for S3 later      |
| Coze AI Bot                 | Coze Cloud     | LLM reasoning, grading logic, explanation gen     |
| OCR Engine                  | Backend (local)| EasyOCR or PaddleOCR runs locally, no API cost    |

**Why Coze and not direct LLM?** Coze provides a managed orchestration layer with built-in plugins, conversation memory, and a conversational interface. Your backend delegates the *reasoning* (grading, explanation generation, report writing) to Coze, while retaining full control over data persistence, user management, and the UI.

---

## 2. Tech Stack Recommendations

### 2.1 Backend

| Layer          | Recommendation                              | Alternative          | Why                                              |
| -------------- | ------------------------------------------- | -------------------- | ------------------------------------------------ |
| Framework      | **FastAPI** (Python 3.11+)                  | Express + TypeScript | Native async, Pydantic validation, auto Swagger  |
| ORM            | **SQLAlchemy 2.0** (async)                  | Prisma               | Mature, supports SQLite natively                 |
| Auth           | **JWT** (access + refresh tokens)           | NextAuth             | Stateless, works across any frontend             |
| File Upload    | **python-multipart** + local disk storage   | Multer (Node)        | Simple, no external dependency                   |
| OCR            | **EasyOCR** or **PaddleOCR**                | Tesseract            | Better Chinese math recognition                  |
| Task Queue     | **Celery + Redis** (for async grading)      | asyncio background   | Grading is slow; don't block HTTP responses      |
| Validation     | **Pydantic v2**                             | Zod (Node)           | Request/response schemas auto-documented         |
| Testing        | **pytest + httpx**                          | Jest                 | Async-friendly, mock Coze API easily             |

### 2.2 Frontend

| Layer          | Recommendation                              | Alternative          | Why                                              |
| -------------- | ------------------------------------------- | -------------------- | ------------------------------------------------ |
| Framework      | **Next.js 14+** (App Router)                | React SPA            | SSR for SEO, API routes for BFF pattern          |
| Styling        | **Tailwind CSS** + **shadcn/ui**            | Material UI          | Rapid development, accessible components         |
| State          | **TanStack Query** (React Query)            | Zustand              | Server-state caching, automatic revalidation     |
| Forms          | **React Hook Form** + **Zod**               | Formik               | Type-safe validation, great DX                   |
| Charts         | **Recharts**                                | Chart.js             | React-native, composable                         |
| Image Upload   | **react-dropzone**                          | Uppy                 | Drag-and-drop, preview, compression              |
| PWA            | **next-pwa**                                | Workbox              | Offline access for students on weak networks     |

### 2.3 Infrastructure

| Layer          | Recommendation                              |
| -------------- | ------------------------------------------- |
| Container      | Docker + docker-compose                     |
| Reverse Proxy  | Nginx (or Caddy for auto TLS)               |
| Process Manager| PM2 (Node) / Gunicorn + uvicorn (Python)    |
| Monitoring     | Prometheus + Grafana (optional)             |
| CI/CD          | GitHub Actions                              |

---

## 3. Module Design

### 3.1 Auth Module

**Responsibilities**: Student registration, login, session management, role-based access (student / teacher).

#### Flow

```
Registration:
  1. Student enters name + student ID + selects school level (elementary/middle/high)
  2. Backend validates uniqueness of student ID
  3. Backend creates student record in SQLite
  4. Backend returns JWT access token + refresh token
  5. Frontend stores tokens in httpOnly cookies (not localStorage for security)

Login:
  1. Student enters student ID + password (or OTP for simplicity)
  2. Backend verifies credentials
  3. Backend issues new JWT pair
  4. Frontend updates cookies

Session Management:
  - Access token: 15-minute expiry (short-lived)
  - Refresh token: 7-day expiry, stored in httpOnly cookie
  - Token rotation on each refresh
  - Automatic logout after 30 minutes of inactivity
```

#### Data Model (in-memory / DB)

```python
class Student(Base):
    id: int (PK, autoincrement)
    student_id: str (UNIQUE, indexed)    # e.g., "2024001"
    name: str                              # display name
    password_hash: str                     # bcrypt
    school_level: enum                     # elementary / middle / high
    role: enum                             # student / teacher
    created_at: datetime
    last_login: datetime
```

#### Security Measures

- Passwords hashed with bcrypt (cost factor 12)
- Rate limiting on login endpoint (5 attempts per 5 minutes)
- JWT signed with HMAC-SHA256 using env-var secret
- CSRF protection via SameSite cookie attribute
- Student IDs validated against a configurable format (e.g., 6-10 digits)

---

### 3.2 Homework Module

**Responsibilities**: Photo upload, OCR extraction, sending to Coze for grading, storing results.

#### Flow

```
Upload:
  1. Student snaps photo or uploads image via drag-and-drop
  2. Frontend compresses image (max 2MB, JPEG quality 85%)
  3. Frontend POSTs multipart/form-data to /api/homework/upload
  4. Backend saves image to ./uploads/homework/{student_id}/{timestamp}.jpg
  5. Backend creates homework_submission record with status="pending"
  6. Backend enqueues async grading task (Celery / asyncio)

Async Grading Pipeline:
  1. OCR engine extracts text from image (Chinese + math symbols)
  2. Backend constructs a prompt payload for Coze:
     - Extracted text
     - Student's school level
     - Subject context (if provided)
     - Student's historical error patterns (from error_records)
  3. Coze processes and returns structured JSON:
     {
       "score": 85,
       "answers_evaluated": [...],
       "comments": "你在这道题的计算步骤很清晰...",
       "error_analysis": [...],
       "knowledge_gaps": ["分数运算", "通分"]
     }
  4. Backend parses response, updates submission record with grade + comments
  5. Backend updates error_records table
  6. Frontend polls or receives WebSocket notification of completion

Result Display:
  - Original photo with annotations (if Coze returns bounding boxes)
  - Score badge (color-coded: green >=80, yellow 60-79, red <60)
  - Personalized comment block
  - Error list with expandable explanations
  - "Review with AI" button -> opens Coze chat for this specific homework
```

#### Coze Prompt Template (Grading)

```
你是{{teacher_name}}老师，一位经验丰富的{{subject}}教师。
请批改以下{{school_level}}学生的数学作业。

学生姓名：{{student_name}}
当前学习进度：{{school_level}}
历史薄弱知识点：{{error_prone_topics}}

【学生作答内容】
{{extracted_text}}

【批改要求】
1. 逐题判断对错，给出每道题的得分
2. 对错题给出详细的解题步骤和正确答案
3. 用鼓励性的语言写一段个性化评语（50-100字）
4. 指出学生知识掌握上的薄弱环节
5. 推荐2-3道针对性练习题

请以JSON格式返回：
{
  "score": 总分,
  "questions": [
    {
      "question_num": 1,
      "correct": true/false,
      "student_answer": "...",
      "correct_answer": "...",
      "steps": ["步骤1", "步骤2"],
      "points_earned": 5,
      "points_possible": 5
    }
  ],
  "comment": "评语内容",
  "knowledge_gaps": ["薄弱知识点1", "薄弱知识点2"],
  "recommended_practice": [
    {"topic": "知识点", "difficulty": "easy/medium/hard", "count": 3}
  ]
}
```

---

### 3.3 Exam Module

**Responsibilities**: Problem bank management, adaptive test generation, exam taking, auto-grading, diagnostic reports.

#### Problem Bank Structure

```python
class ProblemBank(Base):
    id: int (PK)
    subject: enum                    # math_algebra / geometry / calculus / ...
    chapter: str                     # e.g., "二次函数"
    difficulty: enum                 # easy / medium / hard
    knowledge_points: list[str]      # ["配方法", "求根公式"]
    question_type: enum              # multiple_choice / fill_blank / short_answer / essay
    question_text: str               # LaTeX-formatted question
    answer: str                      # correct answer
    solution: str                    # step-by-step solution
    explanation: str                 # why this answer is correct
    tags: list[str]                  # ["中考高频", "易错"]
    created_by: str                  # teacher name or "system"
    created_at: datetime
    usage_count: int                 # how many times this question has been used
```

#### Adaptive Test Generation Algorithm

```
Input: student_id, duration_minutes, target_difficulty_distribution
Output: exam_questions (JSON)

Algorithm:
  1. Fetch student's error_records -> identify weak knowledge points
  2. Fetch student's exam history -> determine current ability level
  3. Query problem_bank:
     - 30% questions from weak areas (medium difficulty)
     - 40% questions from mastered areas (easy-medium)
     - 20% questions from adjacent topics (medium-hard, for stretch)
     - 10% challenge questions (hard, for advanced students)
  4. Ensure coverage: each major knowledge area represented
  5. Shuffle questions, assign point values
  6. Return exam configuration to frontend
```

#### Exam Taking Flow

```
1. Student clicks "Start Exam" on dashboard
2. Backend generates exam via Coze or rule-based algorithm
3. Frontend renders exam interface:
   - Timer countdown (visible)
   - Question navigation sidebar
   - LaTeX-rendered math equations (KaTeX)
   - Input methods: text input, multiple-choice radio buttons, formula editor
4. Student answers questions (auto-save every 30 seconds)
5. Student submits OR timer expires
6. Backend sends answers + questions to Coze for grading
7. Coze returns score + diagnostic report
8. Frontend displays results + detailed breakdown
```

#### Diagnostic Report Structure

```json
{
  "student_id": 123,
  "exam_id": 456,
  "overall_score": 78,
  "total_questions": 20,
  "answered_correctly": 16,
  "time_spent_minutes": 42,
  "section_breakdown": [
    {
      "knowledge_area": "代数运算",
      "score": 85,
      "max_score": 100,
      "trend": "+5 from last exam"
    },
    {
      "knowledge_area": "几何证明",
      "score": 60,
      "max_score": 100,
      "trend": "-3 from last exam"
    }
  ],
  "strengths": ["方程求解", "不等式"],
  "weaknesses": ["辅助线构造", "相似三角形判定"],
  "learning_plan": [
    {
      "priority": "high",
      "topic": "相似三角形判定",
      "reason": "连续两次考试表现不佳",
      "recommended_study_time_minutes": 30,
      "practice_questions_count": 5,
      "resources": ["视频讲解", "基础概念复习"]
    }
  ],
  "generated_at": "2026-06-18T10:30:00Z"
}
```

---

### 3.4 Analysis Module

**Responsibilities**: Performance tracking over time, trend visualization, learning plan generation.

#### Student Performance Tracking

```
Metrics tracked per student:
- Overall score trend (line chart, last 10 exams)
- Knowledge-point mastery heatmap (bar chart)
- Homework completion rate (pie chart)
- Average grading time improvement
- Error recurrence rate (how often same知识点 reappears in errors)

Data aggregation:
- Daily: recalculate rolling averages
- Weekly: generate micro-report for teacher
- Monthly: generate comprehensive diagnostic
```

#### Learning Plan Generator (Coze-powered)

```
Input: student_id, last_n_exams, error_records, homework_history
Prompt to Coze:
  "Based on the following student data, generate a personalized
   learning plan for the next 2 weeks. Consider:
   - Recent performance trends
   - Recurring error patterns
   - School level and curriculum requirements
   - Time available (assume 30 min/day practice)"

Output (structured JSON):
  {
    "weekly_plan": [
      {
        "day": "Monday",
        "focus_topic": "二次函数的图像与性质",
        "activities": [
          {"type": "review", "duration_min": 10, "resource": "..."},
          {"type": "practice", "duration_min": 15, "question_count": 5},
          {"type": "review", "duration_min": 5, "resource": "..."}
        ]
      }
    ],
    "key_recommendations": ["建议优先巩固..."],
    "estimated_improvement": "预计2周后正确率提升10-15%"
  }
```

---

### 3.5 Teacher Dashboard Module

**Responsibilities**: Class-wide statistics, error knowledge point aggregation, individual student insights, report generation.

#### Dashboard Views

**View 1: Class Overview**
```
- Total students enrolled
- Today's homework submissions (count + pending)
- Average class score (last exam)
- Top 3 common errors across the class
- Students needing attention (bottom 20% by score)
```

**View 2: Error Knowledge Point Matrix**
```
Rows = knowledge points (e.g., "配方法", "勾股定理")
Columns = students
Cell color intensity = error count for that知识点 by that student

Example:
              配方法  通分  勾股定理  相似三角形
张同学          ████   ██    █        ████
李同学          ██     ████  █        █
王同学          █      ██    ████     ███
```

**View 3: Individual Student Drill-down**
```
Click any student -> see:
- Full performance timeline
- All homework submissions with grades
- Exam history with score trends
- Detailed error log with knowledge point tags
- Generated learning plan
- "Send reminder" button (trigger Coze message to student)
```

**View 4: Report Generation**
```
- Select date range
- Choose report type: daily / weekly / monthly / custom
- Coze generates narrative summary from aggregated data
- Export as PDF or HTML
- Email to parents (optional)
```

---

### 3.6 Coze Integration Module

**Responsibilities**: Bridge between backend and Coze API, manage conversations, handle prompts, parse responses.

#### Integration Architecture

```
+------------------------------------------------------+
|                   Your Backend                          |
|                                                        |
|  +----------------------------------------------+      |
|  |           CozeAdapter Service                |      |
|  |                                             |      |
|  |  +-------------+  +-------------+  +------+ |      |
|  |  | Prompt      |  | Response    |  | Cache| |      |
|  |  | Builder     |  | Parser      |  | Layer| |      |
|  |  +-------------+  +-------------+  +------+ |      |
|  +----------------------------------------------+      |
|                           |                              |
+---------------------------|------------------------------+
                            |  HTTP POST
                            v
              +-----------------------------+
              |     Coze API Endpoint        |
              |                             |
              |  Bot ID: math_tutor_bot     |
              |  API Key: env variable      |
              |                             |
              |  Conversation Memory:       |
              |  enabled (per student)      |
              +-----------------------------+
```

#### Communication Method

**Recommended: Direct API calls (not webhooks)**

- Backend calls Coze API directly via REST (POST to conversation endpoint)
- Synchronous for simple queries (grading, explanations)
- Asynchronous (with polling or callback) for complex tasks (full diagnostic reports)
- Webhook alternative: Coze pushes to your backend when long-running tasks complete

**Why direct API?** Simpler architecture, no need to manage webhook endpoints, full control over request/response lifecycle, easier to cache and retry.

#### Coze Bot Configuration

```yaml
bot_name: 数学辅导老师
description: 专业的数学教学AI助手，提供作业批改、错题解析、个性化学习方案
persona: |
  你是一位耐心、严谨的数学教师，擅长用鼓励的方式帮助学生理解数学概念。
  你的语言风格亲切但不失专业性，会根据学生的年龄调整表达深度。
  面对错误时，先肯定学生的思考过程，再指出问题所在。

language: zh-CN
temperature: 0.7
max_tokens: 2048

plugins_enabled:
  - calculator          # for verifying numerical answers
  - latex_renderer      # for formatting math expressions
  - knowledge_graph     # for linking related concepts

memory:
  enabled: true
  scope: per_student    # each student has their own conversation context
  max_turns: 50         # retain last 50 turns of conversation
  summary_threshold: 30 # summarize earlier turns to save context window
```

#### Tool Definitions for Coze Bot

```python
# Tools exposed to the Coze bot via function calling

TOOLS = [
    {
        "name": "get_student_profile",
        "description": "获取学生的学习档案，包括学校年级、历史成绩、薄弱知识点",
        "parameters": {
            "student_id": {"type": "string", "description": "学生ID"}
        }
    },
    {
        "name": "lookup_problem",
        "description": "根据知识点或章节查找题库中的题目",
        "parameters": {
            "knowledge_point": {"type": "string"},
            "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
            "count": {"type": "integer", "default": 3}
        }
    },
    {
        "name": "record_error",
        "description": "记录学生的错题到数据库",
        "parameters": {
            "student_id": {"type": "string"},
            "knowledge_point": {"type": "string"},
            "question_id": {"type": "integer"},
            "error_description": {"type": "string"}
        }
    },
    {
        "name": "generate_practice_set",
        "description": "根据薄弱知识点生成一组练习题",
        "parameters": {
            "student_id": {"type": "string"},
            "topics": {"type": "array", "items": {"type": "string"}},
            "count_per_topic": {"type": "integer", "default": 3}
        }
    },
    {
        "name": "get_class_statistics",
        "description": "获取班级整体统计数据",
        "parameters": {
            "date_range": {"type": "string", "description": "日期范围，如 'last_7_days'"}
        }
    }
]
```

#### Caching Strategy

```python
# Cache Coze responses to reduce API costs and latency

CACHE_KEY_FORMAT = "coze:{module}:{student_id}:{hash_of_input}"

CACHE_TTL = {
    "grading": 3600,           # same homework won't be regraded within 1 hour
    "explanation": 86400,      # explanation for a specific problem lasts 1 day
    "diagnostic_report": 604800,  # diagnostic report valid for 1 week
    "learning_plan": 1209600,  # learning plan valid for 2 weeks
}

# Cache layer: Redis (production) or in-memory dict (development)
```

---

## 4. Database Schema (SQLite)

### 4.1 ERD Overview

```
students --+-- homework_submissions
           |-- exams
           |       |-- exam_results
           |       +-- exam_questions
           |-- error_records
           |       +-- problem_bank (FK)
           +-- teacher_reports (via class aggregation)
```

### 4.2 Table Definitions

#### students

```sql
CREATE TABLE students (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT    NOT NULL UNIQUE,   -- e.g., "2024001"
    name            TEXT    NOT NULL,           -- display name
    password_hash   TEXT    NOT NULL,           -- bcrypt hash
    school_level    TEXT    NOT NULL CHECK (school_level IN ('elementary', 'middle', 'high')),
    role            TEXT    NOT NULL DEFAULT 'student'
                                    CHECK (role IN ('student', 'teacher')),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login      DATETIME,
    is_active       BOOLEAN NOT NULL DEFAULT 1,

    INDEX idx_students_student_id (student_id),
    INDEX idx_students_school_level (school_level)
);
```

#### homework_submissions

```sql
CREATE TABLE homework_submissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    photo_url       TEXT    NOT NULL,           -- relative path to uploaded image
    original_filename TEXT,                     -- original filename for reference
    extracted_text  TEXT,                       -- OCR result (nullable if OCR fails)
    subject         TEXT,                       -- e.g., "algebra", "geometry"
    status          TEXT    NOT NULL DEFAULT 'pending'
                                    CHECK (status IN ('pending', 'processing', 'graded', 'failed')),
    score           REAL,                       -- overall score (nullable until graded)
    total_points    REAL DEFAULT 100,           -- total possible points
    answers_evaluated TEXT,                     -- JSON array of question evaluations
    comments        TEXT,                       -- personalized comment from Coze
    error_analysis  TEXT,                       -- JSON array of error details
    knowledge_gaps  TEXT,                       -- JSON array of identified gaps
    coze_response   TEXT,                       -- raw Coze API response (for debugging)
    grading_started_at DATETIME,
    graded_at       DATETIME,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_hw_student_id (student_id),
    INDEX idx_hw_status (status),
    INDEX idx_hw_created_at (created_at)
);
```

#### exams

```sql
CREATE TABLE exams (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    title               TEXT NOT NULL DEFAULT '自适应测试',
    questions_json      TEXT NOT NULL,          -- JSON array of exam questions
    student_answers     TEXT,                   -- JSON: student's answers per question
    score               REAL,
    total_points        REAL DEFAULT 100,
    time_spent_seconds  INTEGER,
    diagnostic_report   TEXT,                   -- JSON: full diagnostic report from Coze
    status              TEXT NOT NULL DEFAULT 'in_progress'
                                    CHECK (status IN ('in_progress', 'submitted', 'graded', 'failed')),
    exam_config_json    TEXT,                   -- JSON: difficulty distribution, duration, etc.
    started_at          DATETIME,
    submitted_at        DATETIME,
    graded_at           DATETIME,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_exam_student_id (student_id),
    INDEX idx_exam_status (status),
    INDEX idx_exam_created_at (created_at)
);
```

#### problem_bank

```sql
CREATE TABLE problem_bank (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject         TEXT    NOT NULL,           -- e.g., "algebra", "geometry"
    chapter         TEXT,                       -- e.g., "二次函数"
    difficulty      TEXT    NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
    knowledge_points TEXT NOT NULL,             -- JSON array: ["配方法", "求根公式"]
    question_type   TEXT    NOT NULL DEFAULT 'short_answer'
                                    CHECK (question_type IN ('multiple_choice', 'fill_blank', 'short_answer', 'essay')),
    question_text   TEXT    NOT NULL,           -- LaTeX-formatted question
    answer          TEXT    NOT NULL,           -- correct answer
    solution        TEXT,                       -- step-by-step solution
    explanation     TEXT,                       -- conceptual explanation
    tags            TEXT,                       -- JSON array: ["中考高频", "易错"]
    created_by      TEXT    DEFAULT 'system',   -- teacher name or "system"
    usage_count     INTEGER NOT NULL DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_pb_subject (subject),
    INDEX idx_pb_difficulty (difficulty),
    INDEX idx_pb_knowledge_points (knowledge_points),
    INDEX idx_pb_tags (tags)
);
```

#### error_records

```sql
CREATE TABLE error_records (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    question_id         INTEGER REFERENCES problem_bank(id),
    knowledge_point     TEXT NOT NULL,          -- denormalized for fast querying
    error_count         INTEGER NOT NULL DEFAULT 1,
    last_error_date     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    first_error_date    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved            BOOLEAN NOT NULL DEFAULT 0,
    context             TEXT,                   -- JSON: additional context about the error

    UNIQUE(student_id, knowledge_point, question_id),
    INDEX idx_er_student_id (student_id),
    INDEX idx_er_knowledge_point (knowledge_point),
    INDEX idx_er_resolved (resolved)
);
```

#### teacher_reports

```sql
CREATE TABLE teacher_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date_start      DATETIME NOT NULL,
    date_end        DATETIME NOT NULL,
    summary_json    TEXT NOT NULL,              -- JSON: full report data
    report_type     TEXT NOT NULL DEFAULT 'custom'
                                    CHECK (report_type IN ('daily', 'weekly', 'monthly', 'custom')),
    generated_by    TEXT DEFAULT 'system',      -- teacher name or "coze"
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_tr_date_range (date_start, date_end),
    INDEX idx_tr_type (report_type)
);
```

#### Additional supporting tables

```sql
-- Sessions / tokens for auth
CREATE TABLE sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    refresh_token   TEXT    NOT NULL UNIQUE,
    expires_at      DATETIME NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at      DATETIME,

    INDEX idx_sessions_token (refresh_token),
    INDEX idx_sessions_student_id (student_id)
);

-- Notification / activity log
CREATE TABLE activities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      INTEGER REFERENCES students(id) ON DELETE SET NULL,
    activity_type   TEXT NOT NULL,              -- 'homework_submitted', 'exam_completed', etc.
    activity_data   TEXT,                       -- JSON: additional data
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_act_student_id (student_id),
    INDEX idx_act_type (activity_type)
);
```

### 4.3 Index Strategy Summary

| Table              | Indexes                                        | Purpose                          |
| ------------------ | ---------------------------------------------- | -------------------------------- |
| students           | student_id (UNIQUE), school_level              | Fast login, level filtering      |
| homework_submissions | student_id, status, created_at               | Query recent homework, pending   |
| exams              | student_id, status, created_at                 | Exam history, active exams       |
| problem_bank       | subject, difficulty, knowledge_points, tags    | Adaptive selection queries       |
| error_records      | student_id, knowledge_point, resolved          | Error pattern analysis           |
| sessions           | refresh_token (UNIQUE), student_id             | Token lookup, session mgmt       |
| teacher_reports    | date_start+date_end, report_type               | Date-range queries               |

---

## 5. API Design

### 5.1 Base Configuration

```
Base URL: https://api.mathagent.example.com/api/v1
Content-Type: application/json
Authentication: Bearer <access_token> (in Authorization header)
Response format:
{
  "success": true,
  "data": { ... },
  "message": "Optional message",
  "pagination": { "page": 1, "per_page": 20, "total": 100 }  // if applicable
}
```

### 5.2 Auth Endpoints

```
POST /api/v1/auth/register
  Request body:
  {
    "student_id": "2024001",
    "name": "张三",
    "password": "securePassword123",
    "school_level": "middle"
  }
  Response 201:
  {
    "success": true,
    "data": {
      "student": { "id": 1, "student_id": "2024001", "name": "张三", ... },
      "tokens": { "access_token": "...", "refresh_token": "...", "expires_in": 900 }
    }
  }

POST /api/v1/auth/login
  Request body:
  {
    "student_id": "2024001",
    "password": "securePassword123"
  }
  Response 200: same as register

POST /api/v1/auth/refresh
  Request body:
  { "refresh_token": "..." }
  Response 200: new token pair

POST /api/v1/auth/logout
  Headers: Authorization: Bearer <token>
  Response 200: { "success": true, "message": "Logged out" }

GET /api/v1/auth/me
  Headers: Authorization: Bearer <token>
  Response 200: current user profile
```

### 5.3 Homework Endpoints

```
POST /api/v1/homework/upload
  Headers: Authorization: Bearer <token>
  Content-Type: multipart/form-data
  Body:
    photo: <binary image file>
    subject: "algebra"          (optional)
    notes: "Chapter 3 homework"  (optional)
  Response 202:
  {
    "success": true,
    "data": {
      "submission_id": 101,
      "status": "pending",
      "estimated_wait_seconds": 30
    },
    "message": "Homework uploaded. Grading in progress."
  }

GET /api/v1/homework/:id
  Headers: Authorization: Bearer <token>
  Response 200:
  {
    "success": true,
    "data": {
      "id": 101,
      "student_id": 1,
      "photo_url": "/uploads/homework/1/20260618_103000.jpg",
      "status": "graded",
      "score": 85,
      "total_points": 100,
      "answers_evaluated": [...],
      "comments": "计算步骤清晰...",
      "error_analysis": [...],
      "knowledge_gaps": ["分数运算"],
      "created_at": "2026-06-18T10:30:00Z",
      "graded_at": "2026-06-18T10:30:32Z"
    }
  }

GET /api/v1/homework?status=pending&limit=10&page=1
  Headers: Authorization: Bearer <token>
  Response 200: paginated list of homework submissions

POST /api/v1/homework/:id/grade
  Headers: Authorization: Bearer <token>
  Description: Manually trigger re-grading (for failed submissions)
  Response 202: { "success": true, "message": "Re-grading initiated" }

GET /api/v1/homework/:id/explain
  Headers: Authorization: Bearer <token>
  Query params: ?question_num=2
  Description: Get detailed explanation for a specific question from Coze
  Response 200:
  {
    "success": true,
    "data": {
      "question_num": 2,
      "explanation": "这道题的关键是...",
      "related_concepts": ["分数加减法", "通分"],
      "similar_practice": [...]
    }
  }

GET /api/v1/homework/stats/overview
  Headers: Authorization: Bearer <token>
  Response 200:
  {
    "success": true,
    "data": {
      "total_submissions": 15,
      "average_score": 82.3,
      "pending_count": 2,
      "this_week_count": 5,
      "score_trend": [78, 80, 82, 79, 85]
    }
  }
```

### 5.4 Exam Endpoints

```
POST /api/v1/exams/generate
  Headers: Authorization: Bearer <token>
  Request body:
  {
    "duration_minutes": 45,
    "target_areas": ["algebra", "geometry"],  // optional, defaults to adaptive
    "difficulty_preference": "balanced"        // balanced / challenging / foundational
  }
  Response 200:
  {
    "success": true,
    "data": {
      "exam_id": 201,
      "title": "自适应测试 - 代数与几何",
      "questions": [...],
      "total_points": 100,
      "duration_minutes": 45
    }
  }

POST /api/v1/exams/:id/submit
  Headers: Authorization: Bearer <token>
  Request body:
  {
    "answers": {
      "q1": "x=3",
      "q2": "A",
      "q3": "sqrt(2)"
    },
    "time_spent_seconds": 2400
  }
  Response 200:
  {
    "success": true,
    "data": {
      "exam_id": 201,
      "status": "submitted",
      "message": "Exam submitted. Grading in progress."
    }
  }

GET /api/v1/exams/:id/report
  Headers: Authorization: Bearer <token>
  Response 200:
  {
    "success": true,
    "data": {
      "exam_id": 201,
      "score": 78,
      "total_points": 100,
      "section_breakdown": [...],
      "strengths": ["方程求解"],
      "weaknesses": ["辅助线构造"],
      "diagnostic_report": {...},
      "learning_plan": [...],
      "created_at": "2026-06-18T14:00:00Z"
    }
  }

GET /api/v1/exams/history?limit=10
  Headers: Authorization: Bearer <token>
  Response 200: paginated exam history with scores

POST /api/v1/exams/:id/retry
  Headers: Authorization: Bearer <token>
  Description: Generate a new exam based on previous performance
  Response 200: new exam configuration
```

### 5.5 Analysis Endpoints

```
GET /api/v1/analysis/student/:id
  Headers: Authorization: Bearer <token>
  Query params: ?period=30d  (7d, 30d, 90d, all)
  Response 200:
  {
    "success": true,
    "data": {
      "student": { "id": 1, "name": "张三", "school_level": "middle" },
      "overview": {
        "total_homework": 15,
        "total_exams": 8,
        "average_homework_score": 82.3,
        "average_exam_score": 78.5,
        "homework_completion_rate": 0.92,
        "error_recurrence_rate": 0.15
      },
      "score_trend": {
        "homework_scores": [75, 78, 80, 82, 79, 85, 83, 86],
        "exam_scores": [70, 72, 75, 78, 80, 78, 82, 85]
      },
      "knowledge_mastery": [
        { "point": "方程求解", "mastery": 0.92, "trend": "up" },
        { "point": "几何证明", "mastery": 0.55, "trend": "down" },
        { "point": "分数运算", "mastery": 0.78, "trend": "stable" }
      ],
      "recent_errors": [...],
      "current_learning_plan": {...}
    }
  }

GET /api/v1/analysis/class
  Headers: Authorization: Bearer <token>  (teacher role required)
  Query params: ?date_from=2026-06-01&date_to=2026-06-18
  Response 200:
  {
    "success": true,
    "data": {
      "class_size": 32,
      "average_score": 76.8,
      "score_distribution": { "A": 8, "B": 12, "C": 8, "D": 3, "F": 1 },
      "top_errors": [
        { "knowledge_point": "配方法", "error_count": 18, "affected_students": 12 },
        { "knowledge_point": "通分", "error_count": 14, "affected_students": 9 }
      ],
      "students_needing_attention": [
        { "id": 5, "name": "李同学", "average_score": 52, "reason": "连续三次低于60分" }
      ],
      "homework_completion_rate": 0.87
    }
  }

GET /api/v1/analysis/knowledge-map
  Headers: Authorization: Bearer <token>
  Response 200:
  {
    "success": true,
    "data": {
      "knowledge_graph": [
        { "id": "kp1", "label": "二次函数", "connections": ["kp2", "kp3"] },
        { "id": "kp2", "label": "配方法", "connections": ["kp1"] }
      ],
      "mastery_levels": { "kp1": 0.85, "kp2": 0.45, "kp3": 0.72 }
    }
  }
```

### 5.6 Teacher Endpoints

```
GET /api/v1/teacher/errors
  Headers: Authorization: Bearer <token>  (teacher role required)
  Query params: ?knowledge_point=all&date_from=2026-06-01&sort=count&order=desc
  Response 200:
  {
    "success": true,
    "data": {
      "errors_by_knowledge_point": [
        {
          "knowledge_point": "配方法",
          "total_errors": 18,
          "affected_students": 12,
          "severity": "high",
          "trend": "increasing",
          "student_list": [
            { "id": 3, "name": "王同学", "error_count": 4, "last_error": "2026-06-17" },
            { "id": 7, "name": "赵同学", "error_count": 3, "last_error": "2026-06-16" }
          ]
        }
      ],
      "error_matrix": { /* student x knowledge_point grid */ }
    }
  }

GET /api/v1/teacher/dashboard
  Headers: Authorization: Bearer <token>  (teacher role required)
  Response 200:
  {
    "success": true,
    "data": {
      "today": {
        "submissions_received": 5,
        "submissions_pending": 2,
        "exams_completed": 3
      },
      "this_week": {
        "total_submissions": 28,
        "average_score": 76.8,
        "completion_rate": 0.87
      },
      "alerts": [
        { "type": "warning", "message": "3 students scored below 50 this week", "student_ids": [5, 12, 18] },
        { "type": "info", "message": "配方法 errors increased 20% this week" }
      ],
      "recent_activity": [
        { "student": "张同学", "activity": "submitted homework", "time": "2 hours ago" }
      ]
    }
  }

GET /api/v1/teacher/student/:id/detail
  Headers: Authorization: Bearer <token>  (teacher role required)
  Response 200: full student profile with all metrics

POST /api/v1/teacher/report/generate
  Headers: Authorization: Bearer <token>  (teacher role required)
  Request body:
  {
    "date_from": "2026-06-01",
    "date_to": "2026-06-18",
    "report_type": "weekly",
    "include_individual": true
  }
  Response 202:
  {
    "success": true,
    "data": {
      "report_id": 301,
      "status": "generating",
      "estimated_completion": "2026-06-18T15:00:00Z"
    }
  }

GET /api/v1/teacher/report/:id
  Headers: Authorization: Bearer <token>
  Response 200:
  {
    "success": true,
    "data": {
      "report": { /* full report data */ },
      "download_url": "/reports/301.pdf"
    }
  }

POST /api/v1/teacher/student/:id/remind
  Headers: Authorization: Bearer <token>  (teacher role required)
  Request body:
  {
    "message_type": "homework_reminder",  // homework_reminder, exam_reminder, encouragement
    "custom_message": "..."               // optional
  }
  Response 200:
  {
    "success": true,
    "data": { "message": "Reminder sent via Coze" }
  }
```

### 5.7 Error Handling Convention

```json
// 400 Bad Request
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid student_id format",
    "details": [{ "field": "student_id", "issue": "Must be 6-10 digits" }]
  }
}

// 401 Unauthorized
{
  "success": false,
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or expired token"
  }
}

// 403 Forbidden
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "Teacher access required"
  }
}

// 404 Not Found
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Homework submission not found"
  }
}

// 429 Too Many Requests
{
  "success": false,
  "error": {
    "code": "RATE_LIMITED",
    "message": "Too many requests. Please try again in 60 seconds."
  }
}

// 500 Internal Server Error
{
  "success": false,
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred",
    "request_id": "req_abc123"
  }
}
```

---

## 6. Coze Bot Design

### 6.1 Bot Persona

```
Name: 数学辅导老师 (Math Tutor)
Avatar: Friendly cartoon teacher character
Tone: Encouraging, patient, professional
Language: Chinese (primary), English (for bilingual schools)

Persona Definition:
  你是一位有10年教学经验的中高级数学教师，熟悉中国大陆各学段的数学课程标准。
  你善于用生活化的比喻解释抽象概念，鼓励学生独立思考而非直接给答案。
  面对错误时，你先肯定学生已经做对的部分，再温和地指出问题所在。
  你的回复结构总是：肯定 -> 分析 -> 建议 -> 鼓励。

Communication Style:
  - Elementary: Use simple language, emojis (stars), analogies from daily life
  - Middle school: Moderate depth, introduce formal terminology gradually
  - High school: Full mathematical rigor, connect to exam strategies
```

### 6.2 Conversation Flow

```
+---------------------------------------------------------------+
|                    Coze Conversation Flow                       |
|                                                                 |
|  1. Student submits homework/photo                              |
|         |                                                       |
|         v                                                       |
|  2. Backend sends:                                              |
|     - Extracted text                                            |
|     - Student profile (level, history)                          |
|     - Grading prompt template                                   |
|         |                                                       |
|         v                                                       |
|  3. Coze returns structured JSON (graded via function calling)  |
|         |                                                       |
|         v                                                       |
|  4. Backend stores results                                      |
|         |                                                       |
|         v                                                       |
|  5. Student views results in frontend                           |
|         |                                                       |
|         v                                                       |
|  6. Student clicks "Ask AI about this error"                    |
|         |                                                       |
|         v                                                       |
|  7. Backend opens Coze conversation with context                |
|     - Previous homework data                                    |
|     - Specific question number                                  |
|     - Student's learning history                                |
|         |                                                       |
|         v                                                       |
|  8. Coze provides interactive explanation                       |
|     - Step-by-step solution                                     |
|     - Similar practice problems                                 |
|     - Concept video recommendation                              |
+---------------------------------------------------------------+
```

### 6.3 Prompt Templates

#### Template 1: Homework Grading

See Section 3.2 above -- the full grading prompt template.

#### Template 2: Error Explanation

```
你正在为一位{{school_level}}学生解释一道错题。

学生姓名：{{student_name}}
题目编号：{{question_num}}
知识点：{{knowledge_point}}
学生作答：{{student_answer}}
正确答案：{{correct_answer}}

请按照以下步骤帮助学生理解：
1. 先肯定学生已经做出的正确尝试
2. 分析错误原因（计算错误？概念混淆？审题不清？）
3. 给出完整的正确解法，每一步都要解释为什么这样做
4. 总结这类题的通用解题思路
5. 出1道同类题目让学生巩固（不要直接给答案，引导学生自己思考）

注意：根据学生的年级调整讲解深度。{{school_level}}的学生不需要过于复杂的术语。
```

#### Template 3: Diagnostic Report Generation

```
基于以下学生数据，生成一份学习诊断报告：

学生信息：
- 姓名：{{student_name}}
- 年级：{{school_level}}
- 近期作业平均分：{{avg_homework_score}}
- 近期考试平均分：{{avg_exam_score}}

最近5次考试成绩：{{exam_scores}}
最近10次作业成绩：{{homework_scores}}

薄弱知识点及错误次数：{{error_summary}}

已知强项：{{strengths}}
已知弱项：{{weaknesses}}

请生成：
1. 总体评价（100字以内，鼓励为主）
2. 各知识点掌握情况详细分析
3. 进步趋势或退步预警
4. 接下来两周的具体学习计划（按天安排）
5. 给家长的学习建议（如有）

以JSON格式返回。
```

#### Template 4: Learning Plan Generation

```
根据以下数据，为这位学生制定一个为期2周的学习计划：

学生：{{student_name}}，{{school_level}}
每天可用练习时间：30分钟

知识掌握度：
{{mastery_data}}

近期错题分布：
{{error_distribution}}

考试趋势：
{{trend_analysis}}

要求：
1. 每天安排具体的学习内容和练习量
2. 薄弱知识点优先，但保持一定比例的复习
3. 包含休息日和轻度复习日
4. 每周末安排一次小测验
5. 标注每个知识点的推荐学习资源类型
```

### 6.4 Coze API Integration Details

```python
# Pseudocode for CozeAdapter service

import httpx
import json
import hashlib
from functools import lru_cache

COZE_BASE_URL = "https://api.coze.com/open_api/v2"
BOT_ID = "math_tutor_bot_12345"

class CozeAdapter:
    def __init__(self, api_key: str, cache=None):
        self.api_key = api_key
        self.cache = cache  # Redis or in-memory

    async def grade_homework(self, student_id: str, image_text: str,
                              metadata: dict) -> dict:
        """Grade homework and return structured result."""

        # Check cache first
        cache_key = f"grade:{student_id}:{hashlib.sha256(image_text.encode()).hexdigest()[:16]}"
        cached = await self.cache.get(cache_key)
        if cached:
            return json.loads(cached)

        # Build prompt
        prompt = GRADE_PROMPT_TEMPLATE.format(
            student_name=metadata["name"],
            school_level=metadata["school_level"],
            error_prone_topics=json.dumps(metadata.get("error_prone_topics", [])),
            extracted_text=image_text
        )

        # Call Coze API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{COZE_BASE_URL}/chat",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "bot_id": BOT_ID,
                    "user": student_id,
                    "query": prompt,
                    "stream": False,
                    "extra": {
                        "functions": [TOOL_DEFINITIONS]
                    }
                }
            )
            response.raise_for_status()
            result = response.json()

        # Parse Coze response (extract JSON from markdown code block)
        parsed = self._parse_coze_response(result["assistant_content"])

        # Cache for 1 hour
        await self.cache.set(cache_key, json.dumps(parsed), ttl=3600)

        return parsed

    async def generate_diagnostic(self, student_id: str, exam_data: dict) -> dict:
        """Generate diagnostic report for an exam."""
        prompt = DIAGNOSTIC_PROMPT_TEMPLATE.format(**exam_data)
        # ... similar to grade_homework
        return parsed

    async def get_explanation(self, student_id: str, question_context: dict) -> dict:
        """Get detailed explanation for a specific question."""
        prompt = EXPLANATION_PROMPT_TEMPLATE.format(**question_context)
        # ... similar pattern
        return parsed

    def _parse_coze_response(self, raw_content: str) -> dict:
        """Extract JSON from Coze's markdown-formatted response."""
        # Coze wraps JSON in ```json ... ``` blocks
        import re
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Fallback: try parsing the whole content
        return json.loads(raw_content)
```

---

## 7. Frontend Page Design

### 7.1 Technology Decisions

- **Framework**: Next.js 14+ with App Router (SSR for initial load, CSR for interactive pages)
- **Styling**: Tailwind CSS with custom theme
- **Component Library**: shadcn/ui (accessible, customizable Radix primitives)
- **Math Rendering**: KaTeX (fast, server-side compatible) + react-katex
- **Charts**: Recharts (built on D3, React-friendly)
- **State**: TanStack Query for server state, Zustand for client state
- **Forms**: React Hook Form + Zod validation
- **File Upload**: react-dropzone with image preview and compression
- **Notifications**: sonner (toast notifications)
- **Routing**: Next.js App Router with route groups for student/teacher layouts

### 7.2 Page Specifications

#### Page 1: Login Page

```
URL: /login
Layout: Centered card on gradient background

Components:
  - Logo (math-themed icon + "数学辅导老师")
  - Tab switcher: [Student Login] [Teacher Login]

Student Login Form:
  +-----------------------------------------+
  |  学生登录                                |
  |                                         |
  |  学号:  [___________________]           |
  |  密码:  [___________________]           |
  |                                         |
  |  [ 忘记密码? ]                           |
  |                                         |
  |  [        登  录        ]               |
  |                                         |
  |  还没有账号? 立即注册 ->                |
  +-----------------------------------------+

Validation:
  - Student ID: 6-10 digits, required
  - Password: required, min 6 characters
  - Real-time validation with inline error messages

Registration Modal (slide-in from right):
  +-----------------------------------------+
  |  学生注册                                |
  |                                         |
  |  姓名:    [___________________]         |
  |  学号:    [___________________]         |
  |  密码:    [___________________]         |
  |  确认密码:[___________________]         |
  |  年级:    [v 初中 v]                   |
  |                                         |
  |  [        注  册        ]               |
  +-----------------------------------------+

Post-login redirect: /dashboard
```

#### Page 2: Student Dashboard

```
URL: /dashboard
Layout: Sidebar navigation + main content area

Sidebar:
  +------------------+
  |  [active] 学习仪表盘  |
  |  我的作业          |
  |  考试中心          |
  |  学习分析          |
  |  AI辅导            |
  |  个人中心          |
  +------------------+

Main Content - Dashboard Overview:

  +------------------------------------------------------------+
  |  Welcome back, Zhang!                                       |
  |  Today's to-do: 2 homeworks pending                          |
  +------------------------------------------------------------+

  +--------------+ +--------------+ +--------------+
  |  Weekly Avg  | | Completion   | | Streak       |
  |   85.3       | |    92%       | |   7 days     |
  |  + 3.2       | |  + 5%        | |  Personal best|
  +--------------+ +--------------+ +--------------+

  +-----------------------------+ +---------------------+
  | Score Trend (line chart)    | | Knowledge Mastery   |
  | y-axis: score (0-100)       | | Eq: 92% [====]     |
  | x-axis: last 8 assessments  | | Geo: 65% [===]     |
  |                             | | Frac: 80% [====]   |
  |  ---                        | | Trig: 55% [==]     |
  | ^  ^  ^    ^^  ^            | | Stat: 95% [=====]  |
  | Jun 1 ... Jun 18            | |                     |
  +-----------------------------+ +---------------------+

  +------------------------------------------------------------+
  |  Learning Suggestions                                        |
  |  Focus on "Trigonometric Functions" - accuracy below 60%    |
  |  Complete today's homework to maintain streak bonus          |
  |  [ View Learning Plan -> ]                                  |
  +------------------------------------------------------------+

  +------------------------------------------------------------+
  |  Quick Actions                                             |
  |  [ Upload HW ] [ Start Exam ] [ Ask AI Teacher ]           |
  +------------------------------------------------------------+
```

#### Page 3: Homework Upload & Result

```
URL: /homework/upload
Layout: Full-width upload area

Upload State:
  +------------------------------------------------------------+
  |                                                            |
  |              +----------------------+                      |
  |              |                      |                      |
  |              |  Drag photo here or  |                      |
  |              |  click to select      |                      |
  |              |                      |                      |
  |              |  Supports JPG, PNG   |                      |
  |              |  Max 5MB             |                      |
  |              +----------------------+                      |
  |                                                            |
  |  Subject: [v Math v]   Notes: [____________]              |
  |  [ UPLOAD ]                                                 |
  |                                                            |
  +------------------------------------------------------------+

Processing State (after upload, before grading):
  +------------------------------------------------------------+
  |                                                            |
  |                    Processing...                            |
  |                                                            |
  |              [ thumbnail of uploaded photo ]                |
  |                                                            |
  |  Progress: OCR -> AI Grading -> Generating Comments        |
  |  [██████████░░░░░░░░] 67%                                 |
  |                                                            |
  |  Estimated 15 seconds remaining                            |
  |  [ Cancel ]                                                 |
  |                                                            |
  +------------------------------------------------------------+

Result State (after grading):
  +------------------------------------------------------------+
  |  Score: 85 / 100  Excellent!                                |
  |                                                            |
  |  +----------------+ +------------------------------------+ |
  |  |                | | Teacher Comment:                     | |
  |  |                | | "Your calculation steps are very    | |
  |  |   Photo Pre-   | | clear. The approach to Q3 was       | |
  |  |   view         | | clever. Pay attention to Q5's       | |
  |  |   (click to    | | common denominator step. Practice   | |
  |  |   zoom)        | | more similar exercises."             | |
  |  |                | |                                      | |
  |  |                | | -- Math Tutor                       | |
  |  |                | +------------------------------------+ |
  |  +----------------+                                            |
  |                                                            |
  |  +---+--------------------------------------------------+  |
  |  | # | Question & Answer              | Grading Result  |  |
  |  +---+--------------------------------------------------+  |
  |  | 1 | x = 3                    | Correct (5 pts)       |  |
  |  | 2 | y = 2x + 1               | Correct (5 pts)       |  |
  |  | 3 | 1/3 + 1/4 = 2/7          | Incorrect (2/5 pts)   |  |
  |  |   | -> Correct: 7/12         | View Explanation ->   |  |
  |  | 4 | ...                      | Correct (5 pts)       |  |
  |  | 5 | ...                      | Incorrect (0/5 pts)   |  |
  |  +---+--------------------------------------------------+  |
  |                                                            |
  |  Weak Points: Fraction Operations, Common Denominator      |
  |                                                            |
  |  [ Ask AI ] [ Practice ] [ Back to Dashboard ]             |
  +------------------------------------------------------------+
```

#### Page 4: Exam Interface

```
URL: /exam/:id
Layout: Focused, distraction-free exam mode

Top Bar:
  +------------------------------------------------------------+
  |  Adaptive Test - Algebra & Geometry         Timer: 28:45  |
  |                                                    [Submit]|
  +------------------------------------------------------------+

Left Panel - Question Navigator:
  +------------------------------------------------------------+
  |  Question Navigator                                        |
  |  +--+--+--+--+--+--+--+--+--+--+                          |
  |  | 1| 2| 3| 4| 5| 6| 7| 8| 9|10|  <- clickable           |
  |  +--+--+--+--+--+--+--+--+--+--+                          |
  |  |11|12|13|14|15|16|17|18|19|20|                          |
  |  +--+--+--+--+--+--+--+--+--+--+                          |
  |  Filled = answered, Empty = unanswered, Flag = review     |
  |                                                            |
  |  Answered: 12/20   Flagged: 2                              |
  +------------------------------------------------------------+

Center - Question Area:
  +------------------------------------------------------------+
  |  Question 3  (Fill in the blank)  Points: 5                |
  |                                                            |
  |  If the vertex of quadratic function y = ax^2 + bx + c     |
  |  is (2, -3), and it passes through (0, 1),                  |
  |  find the values of a, b, c.                               |
  |                                                            |
  |  a = [_____]  b = [_____]  c = [_____]                    |
  |                                                            |
  |  [ Formula Panel ] [ Scratch Paper ]                       |
  |                                                            |
  |  [ Previous ]          [ Next -> ]                         |
  +------------------------------------------------------------+

Exam Submission Confirmation Modal:
  +------------------------------------------------------------+
  |  Confirm submission?                                        |
  |                                                            |
  |  Completed: 12/20  |  Flagged for review: 2                |
  |                                                            |
  |  [ Continue ]  [ Confirm Submit ]                          |
  +------------------------------------------------------------+
```

#### Page 5: Diagnostic Report Page

```
URL: /analysis/report/:examId
Layout: Scrollable report with multiple sections

Report Header:
  +------------------------------------------------------------+
  |  Learning Diagnostic Report                                 |
  |  Test: Adaptive Test - Algebra & Geometry   Date: 2026-06-18|
  |  Score: 78 / 100  (Class Rank: 8/32)                        |
  +------------------------------------------------------------+

Section 1: Score Breakdown
  +------------------------------------------------------------+
  |  Knowledge Point Scores                                     |
  |                                                            |
  |  Equation Solving    [██████████████░░]  88%  +5%          |
  |  Inequalities        [█████████████░░░░]  75%  +2%         |
  |  Geometric Proof     [███████░░░░░░░░░]  52%  -3%          |
  |  Similar Triangles   [██████░░░░░░░░░░]  45%  -8%          |
  |  Function Graphs     [███████████░░░░░]  70%  +1%          |
  +------------------------------------------------------------+

Section 2: Trend Analysis
  +------------------------------------------------------------+
  |  Score Trend (last 5 exams)                                 |
  |                                                            |
  |  100 |                                    ^                |
  |      |                              ^    |                |
  |   80 |     ^  ^          ^  ^    ^    |                |
  |      |  ^  ^  ^  ^  ^  ^  ^  ^  ^    |                |
  |   60 |^^^^  ^  ^  ^  ^  ^  ^  ^    |                |
  |      +------------------------------------------------   |
  |      Exam 1  Exam 2  Exam 3  Exam 4  Exam 5              |
  +------------------------------------------------------------+

Section 3: Strengths & Weaknesses
  +---------------------+ +---------------------+
  | Strengths           | | Needs Improvement   |
  |                     | |                     |
  |  * Equation Solving | |  * Similar Triangles|
  |    (88%)            | |    (45%)            |
  |  * Inequalities (75%)| |  * Geometric Proof  |
  |  * Function Graphs  | |    (52%)            |
  |    (70%)            | |                     |
  +---------------------+ +---------------------+

Section 4: Learning Plan
  +------------------------------------------------------------+
  |  Next 2 Weeks Learning Plan                                 |
  |                                                            |
  |  Monday: Similar triangle review (10min) + 5 practice (15m)|
  |  Tuesday: Geometric proof basics (10min) + 3 practice (15m)|
  |  Wednesday: Comprehensive geometry practice (25min)         |
  |  Thursday: Error book review - geometry (20min)             |
  |  Friday: Mini quiz - geometric proofs (15min)               |
  |  Saturday: Free review + preview next week                  |
  |  Sunday: Rest                                              |
  |                                                            |
  |  Expected: Geometry accuracy could improve to 65%+ in 2 wks|
  |                                                            |
  |  [ Export PDF ] [ Share with Teacher ] [ Start Today -> ]  |
  +------------------------------------------------------------+
```

#### Page 6: Teacher Dashboard

```
URL: /teacher/dashboard
Layout: Multi-panel admin view

Top Stats Bar:
  +----------+----------+----------+----------+----------+
  | Students | Submits  | Avg Score| Complete | Pending  |
  |    32    |    18    |   76.8   |   87%    |    5     |
  +----------+----------+----------+----------+----------+

Panel 1: Error Knowledge Point Heatmap
  +------------------------------------------------------------+
  |  Class Error Distribution by Knowledge Point                |
  |                                                            |
  |               Completing  Fractions  Pythag  Similar       |
  |  Zhang        ████    ██    █        ████                  |
  |  Li           ██     ████   ███      █                     |
  |  Wang         █      ██     ████     ███                   |
  |  Zhao         ███    █      █        ████                  |
  |  Chen         ██     ██     ███      ██                    |
  |  ...                                                    |
  |  Legend: None(0) Few(1-2) Medium(3-5) Many(6+)             |
  +------------------------------------------------------------+

Panel 2: Top 3 Common Errors
  +------------------------------------------------------------+
  |  Top Class-Wide Errors                                      |
  |                                                            |
  |  1. Completing the square - 18 errors, 12 students (+20%)  |
  |     -> Suggestion: Focus on this in next class              |
  |                                                            |
  |  2. Similar triangle criteria - 14 errors, 9 students      |
  |     -> Suggestion: Assign targeted practice                  |
  |                                                            |
  |  3. Fraction operations - 11 errors, 7 students            |
  |     -> Suggestion: 5-min warm-up drill                      |
  +------------------------------------------------------------+

Panel 3: Students Needing Attention
  +------------------------------------------------------------+
  |  Students Needing Attention                                 |
  |                                                            |
  |  +------------------------------------------------------+  |
  |  | Li  Warning: 3 consecutive exams below 60             |  |
  |  | Avg: 52.3  | Recent errors: Completing the square(4)  |  |
  |  | [ View Details ] [ Send Reminder ] [ Schedule Tutor ] |  |
  |  +------------------------------------------------------+  |
  |  | Zhao  Warning: 2 missed homework submissions           |  |
  |  | Avg: 58.0  | Recent errors: Similar triangles(3)       |  |
  |  | [ View Details ] [ Send Reminder ] [ Schedule Tutor ] |  |
  |  +------------------------------------------------------+  |
  +------------------------------------------------------------+

Panel 4: Quick Actions
  +------------------------------------------------------------+
  |  Quick Actions                                             |
  |  [ Generate Weekly Report ] [ Batch Question Gen ]         |
  |  [ Send Announcement ] [ Export Grades ] [ Batch Grade ]   |
  |  [ Class Management ]                                     |
  +------------------------------------------------------------+

Student Detail View (drill-down from dashboard):
  When teacher clicks a student name:
  +------------------------------------------------------------+
  |  Student Detail: Li (ID: 2024005)                           |
  |                                                            |
  |  Basic: Grade 8 | Entry Score: 72 | Current Avg: 58        |
  |                                                            |
  |  Score Curve:  [line chart showing decline trend]          |
  |                                                            |
  |  Recent Homework:                                           |
  |  - 6/15: 62pts (Completing the square error)               |
  |  - 6/12: 55pts (Fraction error)                           |
  |  - 6/10: 60pts (Similar triangles)                        |
  |                                                            |
  |  Knowledge Mastery:                                         |
  |  Equations: [████████░░] 70%  Fractions: [████░░░░░░] 35% |
  |  Geometry Proof: [████░░░░░░] 45%                          |
  |                                                            |
  |  AI Suggestion:                                             |
  |  "Start from basic concepts, prioritize fraction            |
  |   operations, 15 min daily practice. Completing the          |
  |   square requires understanding of perfect square formula." |
  |                                                            |
  |  [ Send Encouragement ] [ Adjust Plan ] [ Mark as Noted ]  |
  +------------------------------------------------------------+
```

### 7.3 Responsive Design Breakpoints

```
Mobile (< 640px):
  - Single column layout
  - Collapsible sidebar -> hamburger menu
  - Exam interface: full-screen, no side panels
  - Upload: camera-first experience

Tablet (640px - 1024px):
  - Two-column layout for dashboard
  - Exam with collapsible navigator

Desktop (> 1024px):
  - Full three-panel exam interface
  - Teacher dashboard with all panels visible
  - Hover states and tooltips enabled
```

---

## 8. Deployment & Operations

### 8.1 Project Structure

```
math-teaching-agent/
+-- backend/
|   +-- app/
|   |   +-- __init__.py
|   |   +-- main.py                  # FastAPI app entry
|   |   +-- config.py                # Settings from env vars
|   |   +-- database.py              # SQLAlchemy engine/session
|   |   +-- models/                  # SQLAlchemy ORM models
|   |   |   +-- student.py
|   |   |   +-- homework.py
|   |   |   +-- exam.py
|   |   |   +-- problem.py
|   |   |   +-- error.py
|   |   |   +-- report.py
|   |   +-- schemas/                 # Pydantic request/response schemas
|   |   |   +-- auth.py
|   |   |   +-- homework.py
|   |   |   +-- exam.py
|   |   |   +-- analysis.py
|   |   +-- api/                     # Route handlers
|   |   |   +-- auth.py
|   |   |   +-- homework.py
|   |   |   +-- exams.py
|   |   |   +-- analysis.py
|   |   |   +-- teacher.py
|   |   +-- services/                # Business logic
|   |   |   +-- auth_service.py
|   |   |   +-- homework_service.py
|   |   |   +-- exam_service.py
|   |   |   +-- analysis_service.py
|   |   |   +-- coze_adapter.py      # Coze API integration
|   |   |   +-- ocr_service.py       # OCR processing
|   |   +-- tasks/                   # Async task definitions
|   |   |   +-- grade_homework.py
|   |   |   +-- generate_report.py
|   |   +-- utils/                   # Helpers
|   |   |   +-- security.py          # JWT, password hashing
|   |   |   +-- validators.py        # Input validation
|   |   |   +-- prompts.py           # Prompt templates
|   +-- uploads/                     # Uploaded images (gitignored)
|   +-- alembic/                     # Database migrations
|   +-- tests/
|   +-- requirements.txt
|   +-- Dockerfile
|   +-- pyproject.toml
+-- frontend/
|   +-- src/
|   |   +-- app/                     # Next.js App Router
|   |   |   +-- layout.tsx
|   |   |   +-- page.tsx             # Landing page
|   |   |   +-- login/
|   |   |   +-- dashboard/
|   |   |   +-- homework/
|   |   |   +-- exam/
|   |   |   +-- analysis/
|   |   |   +-- teacher/
|   |   |   +-- api/                # API route handlers (BFF)
|   |   +-- components/
|   |   |   +-- ui/                  # shadcn/ui components
|   |   |   +-- homework/
|   |   |   +-- exam/
|   |   |   +-- charts/
|   |   |   +-- layout/
|   |   +-- lib/
|   |   |   +-- api-client.ts        # Typed API client
|   |   |   +-- auth.ts              # Auth utilities
|   |   |   +-- math.ts              # Math rendering helpers
|   |   +-- hooks/
|   |   |   +-- use-auth.ts
|   |   |   +-- use-exam.ts
|   |   |   +-- use-homework.ts
|   |   +-- stores/                  # Zustand stores
|   |   +-- styles/
|   |   |   +-- globals.css
|   +-- public/
|   +-- next.config.js
|   +-- tailwind.config.js
|   +-- tsconfig.json
|   +-- Dockerfile
|   +-- package.json
+-- docker-compose.yml
+-- nginx/
|   +-- nginx.conf
+-- .env.example
+-- .gitignore
+-- README.md
```

### 8.2 Docker Compose (Development)

```yaml
version: "3.9"

services:
  db:
    image: sqlite:latest
    volumes:
      - sqlite_data:/data/math_agent.db
    environment:
      SQLITE_FILE: /data/math_agent.db

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: sqlite:////data/math_agent.db
      COZE_API_KEY: ${COZE_API_KEY}
      JWT_SECRET: ${JWT_SECRET}
      OCR_MODEL_PATH: ./models
    volumes:
      - uploads_data:/app/uploads
      - ./backend/app:/app/app
    depends_on:
      - db

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1
    depends_on:
      - backend

volumes:
  sqlite_data:
  uploads_data:
```

### 8.3 Production Deployment Options

| Option              | Pros                          | Cons                        | Best For          |
| ------------------- | ----------------------------- | --------------------------- | ----------------- |
| VPS (Ubuntu)        | Full control, low cost        | Self-managed                | Small deployments |
| Railway / Render    | Zero infra management         | Higher cost at scale        | MVP / staging     |
| AWS ECS + RDS       | Scalable, enterprise-grade    | Complex setup               | Production scale  |
| Docker + Nginx      | Portable, consistent          | Requires ops knowledge      | Custom hosting    |

**Recommended for initial deployment**: VPS with Docker Compose + Nginx reverse proxy. Cost ~$5-10/month for a basic 1-core/2GB instance.

---

## 9. Security Considerations

### 9.1 Authentication & Authorization

- JWT access tokens expire in 15 minutes
- Refresh tokens stored in httpOnly, Secure, SameSite=Strict cookies
- Role-based access control (RBAC): student vs. teacher roles enforced at API level
- Student can only access their own data (enforced via middleware)
- Teacher can access class-level data but not other classes

### 9.2 Data Protection

- All API traffic over HTTPS (TLS 1.2+)
- Passwords hashed with bcrypt (cost 12)
- Uploaded photos stored with opaque filenames (UUID + extension)
- SQLite database encrypted at rest (SQLCipher) for compliance
- Coze API keys stored in environment variables, never in code

### 9.3 Input Validation

- All API inputs validated with Pydantic schemas
- File uploads: size limit 5MB, MIME type check (image/jpeg, image/png), virus scan
- SQL injection prevention via parameterized queries (SQLAlchemy ORM)
- XSS prevention via input sanitization and React's built-in escaping
- Rate limiting: 100 req/min per IP on public endpoints, 500 req/min on authenticated

### 9.4 Privacy Compliance

- Student data treated as minor-sensitive information
- No third-party analytics without parental consent
- Data retention policy: homework photos retained for 1 year, exam records for 3 years
- Right to deletion: teachers can request full data removal for any student

---

## Appendix A: API Endpoint Summary

| Method   | Endpoint                              | Auth    | Role    | Description                    |
| -------- | ------------------------------------- | ------- | ------- | ------------------------------ |
| POST     | /api/v1/auth/register                 | No      | Public  | Register new student           |
| POST     | /api/v1/auth/login                    | No      | Public  | Login                          |
| POST     | /api/v1/auth/refresh                  | No      | Public  | Refresh token                  |
| POST     | /api/v1/auth/logout                   | Yes     | Student | Logout                         |
| GET      | /api/v1/auth/me                       | Yes     | Student | Current user info              |
| POST     | /api/v1/homework/upload               | Yes     | Student | Upload homework photo          |
| GET      | /api/v1/homework/:id                  | Yes     | Student | Get homework result            |
| GET      | /api/v1/homework                      | Yes     | Student | List homework submissions      |
| POST     | /api/v1/homework/:id/grade            | Yes     | Student | Re-trigger grading             |
| GET      | /api/v1/homework/:id/explain          | Yes     | Student | Get question explanation       |
| GET      | /api/v1/homework/stats/overview       | Yes     | Student | Homework statistics            |
| POST     | /api/v1/exams/generate                | Yes     | Student | Generate adaptive exam         |
| POST     | /api/v1/exams/:id/submit              | Yes     | Student | Submit exam answers            |
| GET      | /api/v1/exams/:id/report              | Yes     | Student | Get exam diagnostic report     |
| GET      | /api/v1/exams/history                 | Yes     | Student | Exam history                   |
| POST     | /api/v1/exams/:id/retry               | Yes     | Student | Generate new exam              |
| GET      | /api/v1/analysis/student/:id          | Yes     | Student | Student performance analysis   |
| GET      | /api/v1/analysis/class                | Yes     | Teacher | Class-wide analysis            |
| GET      | /api/v1/analysis/knowledge-map        | Yes     | Student | Knowledge mastery map          |
| GET      | /api/v1/teacher/errors                | Yes     | Teacher | Error knowledge point matrix   |
| GET      | /api/v1/teacher/dashboard             | Yes     | Teacher | Teacher overview dashboard     |
| GET      | /api/v1/teacher/student/:id/detail    | Yes     | Teacher | Individual student detail      |
| POST     | /api/v1/teacher/report/generate       | Yes     | Teacher | Generate class report          |
| GET      | /api/v1/teacher/report/:id            | Yes     | Teacher | Get generated report           |
| POST     | /api/v1/teacher/student/:id/remind    | Yes     | Teacher | Send reminder to student       |

## Appendix B: Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///./math_agent.db

# JWT
JWT_SECRET=your-random-secret-key-at-least-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Coze
COZE_API_KEY=coze_xxxxxxxxxxxxxxxx
COZE_BOT_ID=math_tutor_bot_12345
COZE_BASE_URL=https://api.coze.com/open_api/v2

# OCR
OCR_MODEL_PATH=./models/easyocr

# File Upload
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE_MB=5

# CORS
ALLOWED_ORIGINS=https://mathagent.example.com,http://localhost:3000

# Logging
LOG_LEVEL=INFO
```

## Appendix C: File Size & Performance Targets

| Metric                  | Target                  |
| ----------------------- | ----------------------- |
| API response time (p95) | < 500ms (non-Coze)      |
| Coze grading time       | < 15 seconds            |
| Page load time          | < 2 seconds (LCP)       |
| Image upload size       | Max 5 MB                |
| Concurrent users        | Support 200+            |
| SQLite file size        | < 2 GB (with pruning)   |
| Coze API cost estimate  | ~$0.01 per grading call |
