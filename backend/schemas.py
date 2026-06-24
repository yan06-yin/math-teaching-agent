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
    invite_code: Optional[str] = Field(default=None, max_length=20)


class StudentLogin(BaseModel):
    student_id: str
    name: str
    password: str


class StudentSetPassword(BaseModel):
    password: str = Field(..., min_length=6, max_length=128)


class StudentResetPassword(BaseModel):
    """学生重置密码（需提供旧密码验证身份）"""
    student_id: str
    name: str
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


class TeacherLogin(BaseModel):
    username: str
    password: str


class TeacherResetPassword(BaseModel):
    """教师重置密码（需提供旧密码验证身份）"""
    username: str
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


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
    with_images: bool = True  # 是否自动生成 SVG 配图


class ExamSubmit(BaseModel):
    answers: list[dict]  # [{"question_index": 0, "answer": "..."}, ...]


class ExamResult(BaseModel):
    id: int
    score: float
    questions: list[dict]
    student_answers: list[dict]
    diagnostic_report: Optional[str] = ""  # Markdown 文本
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


# ===== 班级 =====
class ClassCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    school_level: str = Field(..., pattern="^(小学|初中|高中)$")


class ClassInfo(BaseModel):
    id: int
    name: str
    teacher_id: int
    school_level: str
    student_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteCodeGenerate(BaseModel):
    max_used_count: int = Field(default=0, ge=0)
    expires_in_days: Optional[int] = Field(default=None, ge=1)


class InviteCodeInfo(BaseModel):
    id: int
    code: str
    max_used_count: int
    used_count: int
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class JoinClass(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)


class AssignStudent(BaseModel):
    student_id: int


class AdminAssignStudent(BaseModel):
    student_id: int
    class_id: int


class StudentInClass(BaseModel):
    id: int
    name: str
    student_id: str
    school_level: str
    joined_via: str
    joined_at: Optional[datetime]
    last_login: Optional[datetime]


class TeacherInfo(BaseModel):
    id: int
    name: str
    username: str
    school: str
    is_admin: bool
    class_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
