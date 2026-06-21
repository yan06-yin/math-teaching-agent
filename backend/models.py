"""
SQLAlchemy ORM 数据模型
"""
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON,
    Index, func, Boolean
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    student_id = Column(String(30), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False, default="")
    school_level = Column(String(10), nullable=False)  # 小学/初中/高中
    role = Column(String(20), default="student", nullable=False)
    last_login = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    homework_submissions = relationship("HomeworkSubmission", back_populates="student")
    exam_attempts = relationship("ExamAttempt", back_populates="student")
    error_records = relationship("ErrorRecord", back_populates="student")


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    school = Column(String(100), default="")
    is_admin = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    token = Column(String(512), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class HomeworkSubmission(Base):
    __tablename__ = "homework_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    photo_url = Column(String(512), nullable=False)
    extracted_text = Column(Text, default="")
    student_answers = Column(Text, default="")
    correct_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    score = Column(Float, default=0)
    comments = Column(Text, default="")
    wrong_questions_json = Column(JSON, default=list)
    status = Column(String(20), default="pending")  # pending / grading / done / error
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    student = relationship("Student", back_populates="homework_submissions")

    @property
    def wrong_questions(self):
        return self.wrong_questions_json or []

    @wrong_questions.setter
    def wrong_questions(self, value):
        self.wrong_questions_json = value


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    exam_config_json = Column(JSON, nullable=False)  # 出题配置
    questions_json = Column(JSON, nullable=False)     # 题目
    student_answers = Column(JSON, default=list)      # 学生答案
    score = Column(Float, default=0)
    diagnostic_report = Column(JSON, default=dict)    # 诊断报告
    learning_plan = Column(JSON, default=list)        # 学习计划
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    student = relationship("Student", back_populates="exam_attempts")


class ProblemBank(Base):
    __tablename__ = "problem_bank"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_point = Column(String(100), nullable=False)
    difficulty = Column(Integer, default=1)  # 1-5
    subject_area = Column(String(50))         # 代数/几何/统计等
    question_text = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    explanation = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class ErrorRecord(Base):
    __tablename__ = "error_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    knowledge_point = Column(String(100), nullable=False)
    question_text = Column(Text, default="")
    student_answer = Column(Text, default="")
    correct_answer = Column(Text, default="")
    error_count = Column(Integer, default=1)
    last_error_date = Column(DateTime, default=datetime.now(timezone.utc))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    student = relationship("Student", back_populates="error_records")

    __table_args__ = (
        Index("idx_student_knowledge", "student_id", "knowledge_point"),
    )


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    level = Column(String(10))  # 小学/初中/高中
    description = Column(Text, default="")
    related_points_json = Column(JSON, default=list)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    activity_type = Column(String(50), nullable=False)  # homework / exam / login
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Assignment(Base):
    """教师发布的作业"""
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)  # NULL=广播
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    questions_json = Column(JSON, default=list)
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class AssignmentSubmission(Base):
    """学生提交的作业"""
    __tablename__ = "assignment_submissions"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    answers_json = Column(JSON, default=list)
    score = Column(Float, default=0)
    status = Column(String(20), default="submitted")
    submitted_at = Column(DateTime, default=datetime.now(timezone.utc))


class Class(Base):
    """班级"""
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False, index=True)
    school_level = Column(String(10), nullable=False)  # 小学/初中/高中
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    teacher = relationship("Teacher")
    members = relationship("ClassStudent", back_populates="class_", cascade="all, delete-orphan")
    invite_codes = relationship("InviteCode", back_populates="class_", cascade="all, delete-orphan")


class InviteCode(Base):
    """邀请码"""
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(20), unique=True, nullable=False, index=True)
    max_used_count = Column(Integer, default=0)  # 0=不限
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)  # NULL=永不过期
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    class_ = relationship("Class", back_populates="invite_codes")


class ClassStudent(Base):
    """班级-学生关联"""
    __tablename__ = "class_students"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), unique=True, nullable=False, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False, index=True)
    joined_via = Column(String(20), default="invite")  # invite / manual
    joined_at = Column(DateTime, default=datetime.now(timezone.utc))

    class_ = relationship("Class", back_populates="members")
    student = relationship("Student")


class GradingTask(Base):
    """异步批改任务"""
    __tablename__ = "grading_tasks"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    submission_id = Column(Integer, ForeignKey("homework_submissions.id"), nullable=True)
    task_type = Column(String(20), default="homework")  # homework / exam
    status = Column(String(20), default="pending")  # pending / processing / done / error
    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class AIProvider(Base):
    """AI 模型提供商配置"""
    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)  # 显示名称，如 "Agnes Flash" / "DeepSeek"
    provider = Column(String(50), nullable=False)  # 标识，如 "openai-compatible"
    base_url = Column(String(256), nullable=False)
    api_key = Column(String(512), nullable=False)
    model = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=False)  # 只有一个可以活跃
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
