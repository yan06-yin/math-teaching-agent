"""
Pydantic 请求/响应模型
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ===== 认证 =====
class StudentRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    student_id: str = Field(..., min_length=1, max_length=30)
    password: str = Field(..., min_length=6, max_length=128)
    school_level: str = Field(..., pattern="^(小学|初中|高中)$")


class StudentLogin(BaseModel):
    student_id: str
    name: str
    password: str


class StudentSetPassword(BaseModel):
    password: str = Field(..., min_length=6, max_length=128)


class TeacherLogin(BaseModel):
    username: str
    password: str


class TeacherRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    school: str = Field(default="")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_type: str  # "student" or "teacher"
    student_id: Optional[int] = None


# ===== 作业 =====
class HomeworkUpload(BaseModel):
    photo_url: str
    student_answers: str = ""


class HomeworkResult(BaseModel):
    id: int
    photo_url: str
    score: float
    correct_count: int
    total_count: int
    comments: str
    wrong_questions: list
    status: str
    created_at: datetime


# ===== 考试 =====
class ExamGenerateConfig(BaseModel):
    """出题配置"""
    knowledge_points: list[str] = []  # 薄弱知识点（空则随机）
    difficulty: int = Field(default=3, ge=1, le=5)
    question_count: int = Field(default=10, ge=1, le=50)
    subject_areas: list[str] = []


class ExamSubmit(BaseModel):
    answers: list[dict]  # [{"question_index": 0, "answer": "..."}, ...]


class ExamResult(BaseModel):
    id: int
    score: float
    questions: list[dict]
    student_answers: list[dict]
    diagnostic_report: dict
    learning_plan: list[dict]
    created_at: datetime


# ===== 分析 =====
class StudentProfile(BaseModel):
    total_homework: int
    total_exams: int
    avg_score: float
    strengths: list[str]
    weaknesses: list[str]
    trend: str  # rising / stable / falling


# ===== 教师端 =====
class ErrorSummary(BaseModel):
    knowledge_point: str
    error_count: int
    affected_students: int
    error_rate: float
    recent_errors: list[dict]


class TeacherDashboard(BaseModel):
    total_students: int
    total_homework: int
    total_exams: int
    class_avg_score: float
    knowledge_heatmap: list[dict]  # [{point, error_rate}]
    top_error_students: list[dict]
