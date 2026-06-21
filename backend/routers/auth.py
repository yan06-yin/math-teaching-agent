"""
认证路由 — 学生注册/登录、教师登录/注册
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Student, Teacher, ActivityLog
from schemas import (
    StudentRegister, StudentLogin, StudentSetPassword, TeacherLogin, TeacherRegister, TokenResponse,
)
from utils.auth import require_teacher
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
    """学生注册（姓名+学号+密码）"""
    existing = db.query(Student).filter(Student.student_id == body.student_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该学号已被注册")

    student = Student(
        name=body.name,
        student_id=body.student_id,
        password_hash=pwd_context.hash(body.password),
        school_level=body.school_level,
        role="student",
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
    """学生登录（姓名+学号+密码）"""
    student = db.query(Student).filter(
        Student.student_id == body.student_id,
        Student.name == body.name,
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="学号或姓名不正确",
        )

    # 处理旧数据：没有密码的学生需要设置密码
    if not student.password_hash:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先设置密码后登录",
        )

    if not pwd_context.verify(body.password, student.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密码不正确",
        )

    # 更新最后登录时间
    student.last_login = datetime.now(timezone.utc)
    db.commit()

    # 记录登录活动
    activity = ActivityLog(
        student_id=student.id,
        activity_type="login",
        detail="学生登录",
    )
    db.add(activity)
    db.commit()

    token = create_access_token({"sub": str(student.id), "type": "student"})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_type="student",
        student_id=student.id,
    )


@router.post("/student/reset-password", response_model=TokenResponse)
async def reset_student_password(
    body: StudentLogin,
    db: Session = Depends(get_db),
):
    """学生重置密码（通过姓名+学号验证身份后重置）"""
    student = db.query(Student).filter(
        Student.student_id == body.student_id,
        Student.name == body.name,
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="学号或姓名不正确",
        )

    student.password_hash = pwd_context.hash(body.password)
    student.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(student)

    token = create_access_token({"sub": str(student.id), "type": "student"})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_type="student",
        student_id=student.id,
    )


@router.post("/teacher/reset-password")
async def reset_teacher_password(
    body: TeacherLogin,
    db: Session = Depends(get_db),
):
    """教师重置密码（通过用户名验证身份后重置）"""
    teacher = db.query(Teacher).filter(Teacher.username == body.username).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名不存在",
        )

    teacher.password_hash = pwd_context.hash(body.password)
    db.commit()

    token = create_access_token({"sub": str(teacher.id), "type": "teacher"})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_type="teacher",
    )
async def set_password(
    body: StudentSetPassword,
    student_id: int,
    db: Session = Depends(get_db),
):
    """学生设置密码（针对旧数据中无密码的账号）"""
    student = db.query(Student).get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    if student.password_hash:
        raise HTTPException(status_code=400, detail="该账号已设置密码")

    student.password_hash = pwd_context.hash(body.password)
    db.commit()
    db.refresh(student)

    token = create_access_token({"sub": str(student.id), "type": "student"})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_type="student",
        student_id=student.id,
    )


@router.delete("/teacher/me")
async def delete_teacher(
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师删除自己的账号"""
    teacher = current_user[0]
    db.delete(teacher)
    db.commit()
    return {"message": f"已删除教师 {teacher.name}"}


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


@router.post("/teacher/register", response_model=TokenResponse)
async def teacher_register(body: TeacherRegister, db: Session = Depends(get_db)):
    """教师注册（开放注册）"""
    existing = db.query(Teacher).filter(
        (Teacher.username == body.username) | (Teacher.name == body.name)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名或姓名已被注册")

    teacher = Teacher(
        name=body.name,
        username=body.username,
        password_hash=pwd_context.hash(body.password),
        school=body.school,
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)

    token = create_access_token({"sub": str(teacher.id), "type": "teacher"})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_type="teacher",
    )
