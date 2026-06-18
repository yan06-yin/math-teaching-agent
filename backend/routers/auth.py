"""
认证路由 — 学生注册/登录、教师登录
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models import Student, Teacher, Session as SessionModel
from schemas import (
    StudentRegister, StudentLogin, TeacherLogin, TokenResponse,
)
from config import settings
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()


def create_access_token(data: dict) -> str:
    """创建 JWT token"""
    from jose import jwt
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/register", response_model=TokenResponse)
async def register(body: StudentRegister, db: Session = Depends(get_db)):
    """学生注册"""
    # 检查学号是否已存在
    existing = db.query(Student).filter(Student.student_id == body.student_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该学号已被注册")

    student = Student(
        name=body.name,
        student_id=body.student_id,
        school_level=body.school_level,
    )
    db.add(student)
    db.commit()
    db.refresh(student)

    token = create_access_token({"sub": str(student.id), "type": "student"})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_type="student",
        student_id=student.id,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: StudentLogin, db: Session = Depends(get_db)):
    """学生登录（姓名+学号）"""
    student = db.query(Student).filter(
        Student.student_id == body.student_id,
        Student.name == body.name,
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="学号或姓名不正确",
        )

    token = create_access_token({"sub": str(student.id), "type": "student"})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_type="student",
        student_id=student.id,
    )


@router.post("/teacher/login", response_model=TokenResponse)
async def teacher_login(body: TeacherLogin, db: Session = Depends(get_db)):
    """教师登录"""
    teacher = db.query(Teacher).filter(Teacher.username == body.username).first()

    if not teacher or not pwd_context.verify(body.password, teacher.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
        )

    token = create_access_token({"sub": str(teacher.id), "type": "teacher"})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_type="teacher",
    )
