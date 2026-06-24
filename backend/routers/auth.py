"""
认证路由 — 学生注册/登录、教师登录/注册
使用异步 SQLAlchemy
"""
import logging
import traceback
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Student, Teacher, ActivityLog, InviteCode, ClassStudent, Class, Assignment, AssignmentSubmission, ErrorRecord, HomeworkSubmission, ExamAttempt, GradingTask
from schemas import (
    StudentRegister, StudentLogin, StudentSetPassword, StudentResetPassword,
    TeacherLogin, TeacherRegister, TeacherResetPassword, TokenResponse,
)
from utils.auth import require_teacher, require_student
from config import settings

import hashlib
import secrets

logger = logging.getLogger(__name__)

# ===== 密码哈希 — 同时支持 bcrypt（新密码）和 SHA-256（bcrypt 4.1 不兼容期存的旧密码）=====
from passlib.context import CryptContext

try:
    _bcrypt_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _bcrypt_ctx.hash("test")
    _has_bcrypt = True
    logger.info("使用 bcrypt 密码哈希")
except Exception:
    _has_bcrypt = False
    logger.warning("bcrypt C 扩展不可用，回退到纯 Python SHA-256")


def _hash_password(password: str) -> str:
    if _has_bcrypt:
        return _bcrypt_ctx.hash(password)
    salt = secrets.token_hex(16)
    h = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"sha256${salt}${h}"


def _verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    if hashed.startswith("sha256$"):
        try:
            parts = hashed.split("$")
            return len(parts) == 3 and hashlib.sha256((password + parts[1]).encode()).hexdigest() == parts[2]
        except Exception:
            return False
    if _has_bcrypt:
        return _bcrypt_ctx.verify(password, hashed)
    try:
        parts = hashed.split("$")
        return len(parts) == 3 and parts[0] == "sha256" and hashlib.sha256((password + parts[1]).encode()).hexdigest() == parts[2]
    except Exception:
        return False


class _PasswordContext:
    def hash(self, password: str) -> str:
        return _hash_password(password)
    def verify(self, password: str, hashed: str) -> bool:
        return _verify_password(password, hashed)

pwd_context = _PasswordContext()

router = APIRouter()


def create_access_token(data: dict) -> str:
    from jose import jwt
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post("/register", response_model=TokenResponse)
async def register(body: StudentRegister, db: AsyncSession = Depends(get_db)):
    """学生注册（姓名+学号+密码+可选邀请码）"""
    try:
        existing = (await db.execute(
            select(Student).filter(Student.student_id == body.student_id, Student.is_deleted == False)
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="该学号已被注册")

        # 检查是否有软删除的同名学生 → 彻底清干净后重建
        deleted = (await db.execute(
            select(Student).filter(Student.student_id == body.student_id, Student.is_deleted == True)
        )).scalar_one_or_none()
        if deleted:
            sid = deleted.id
            for model in [ClassStudent, GradingTask, ExamAttempt, HomeworkSubmission, ErrorRecord, ActivityLog, AssignmentSubmission]:
                objs = (await db.execute(select(model).filter(model.student_id == sid))).scalars().all()
                for obj in objs:
                    await db.delete(obj)
            deleted.is_deleted = False
            deleted.name = body.name
            deleted.password_hash = pwd_context.hash(body.password)
            deleted.school_level = body.school_level
            deleted.role = "student"
            deleted.last_login = None
            await db.flush()
            return await _finish_register(db, deleted, body.invite_code)

        student = Student(
            name=body.name,
            student_id=body.student_id,
            password_hash=pwd_context.hash(body.password),
            school_level=body.school_level,
            role="student",
        )
        db.add(student)
        await db.flush()
        return await _finish_register(db, student, body.invite_code)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"注册失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"系统错误: {str(e)}")


async def _finish_register(db: AsyncSession, student: Student, invite_code: str | None = None) -> TokenResponse:
    """注册收尾：处理邀请码 + 生成 token"""
    if invite_code:
        invite = (await db.execute(
            select(InviteCode).filter(InviteCode.code == invite_code, InviteCode.is_active == True)
        )).scalar_one_or_none()
        if not invite:
            raise HTTPException(status_code=400, detail="邀请码无效")
        if invite.expires_at and invite.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="邀请码已过期")
        if invite.max_used_count > 0 and invite.used_count >= invite.max_used_count:
            raise HTTPException(status_code=400, detail="邀请码已达使用上限")

        cs = ClassStudent(student_id=student.id, class_id=invite.class_id, joined_via="invite")
        db.add(cs)
        invite.used_count += 1

    await db.commit()
    await db.refresh(student)

    token = create_access_token({"sub": str(student.id), "type": "student"})
    return TokenResponse(access_token=token, token_type="bearer", user_type="student", student_id=student.id)


@router.post("/login", response_model=TokenResponse)
async def login(body: StudentLogin, db: AsyncSession = Depends(get_db)):
    """学生登录（姓名+学号+密码）"""
    try:
        student = (await db.execute(
            select(Student).filter(
                Student.student_id == body.student_id,
                Student.name == body.name,
                Student.is_deleted == False,
            )
        )).scalar_one_or_none()

        if not student:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="学号或姓名不正确")

        if not student.password_hash:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="请先设置密码后登录")

        if not pwd_context.verify(body.password, student.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密码不正确")

        student.last_login = datetime.now(timezone.utc)
        db.add(ActivityLog(student_id=student.id, activity_type="login", detail="学生登录"))
        await db.commit()

        token = create_access_token({"sub": str(student.id), "type": "student"})
        return TokenResponse(access_token=token, token_type="bearer", user_type="student", student_id=student.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"系统错误: {str(e)}")


@router.post("/student/reset-password", response_model=TokenResponse)
async def reset_student_password(body: StudentResetPassword, db: AsyncSession = Depends(get_db)):
    """学生重置密码（需提供旧密码验证身份）"""
    student = (await db.execute(
        select(Student).filter(
            Student.student_id == body.student_id,
            Student.name == body.name,
            Student.is_deleted == False,
        )
    )).scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="学号或姓名不正确")

    if not student.password_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该账号尚未设置密码，请使用注册流程")

    if not pwd_context.verify(body.old_password, student.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="旧密码不正确")

    student.password_hash = pwd_context.hash(body.new_password)
    student.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(student)

    token = create_access_token({"sub": str(student.id), "type": "student"})
    return TokenResponse(access_token=token, token_type="bearer", user_type="student", student_id=student.id)


@router.post("/teacher/reset-password")
async def reset_teacher_password(body: TeacherResetPassword, db: AsyncSession = Depends(get_db)):
    """教师重置密码（需提供旧密码验证身份）"""
    teacher = (await db.execute(
        select(Teacher).filter(Teacher.username == body.username, Teacher.is_deleted == False)
    )).scalar_one_or_none()

    if not teacher:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名不存在")

    if not pwd_context.verify(body.old_password, teacher.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="旧密码不正确")

    teacher.password_hash = pwd_context.hash(body.new_password)
    await db.commit()

    token = create_access_token({"sub": str(teacher.id), "type": "teacher"})
    return TokenResponse(access_token=token, token_type="bearer", user_type="teacher")


@router.post("/set-password")
async def set_password(
    body: StudentSetPassword,
    student_id: int,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """学生设置密码（针对旧数据中无密码的账号）"""
    user, _ = current_user
    if user.id != student_id:
        raise HTTPException(status_code=403, detail="只能设置自己的密码")

    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    if student.password_hash:
        raise HTTPException(status_code=400, detail="该账号已设置密码")

    student.password_hash = pwd_context.hash(body.password)
    await db.commit()
    await db.refresh(student)

    token = create_access_token({"sub": str(student.id), "type": "student"})
    return TokenResponse(access_token=token, token_type="bearer", user_type="student", student_id=student.id)


@router.delete("/teacher/me")
async def delete_teacher(current_user=Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    """教师删除自己的账号（级联清理班级、作业等数据）"""
    teacher = current_user[0]
    teacher_id = teacher.id

    class_ids = [c.id for c in (await db.execute(select(Class).filter(Class.teacher_id == teacher_id))).scalars().all()]
    if class_ids:
        for model in [ClassStudent, InviteCode]:
            objs = (await db.execute(select(model).filter(model.class_id.in_(class_ids)))).scalars().all()
            for obj in objs:
                await db.delete(obj)

    assignments = (await db.execute(select(Assignment).filter(Assignment.teacher_id == teacher_id))).scalars().all()
    for a in assignments:
        subs = (await db.execute(select(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == a.id))).scalars().all()
        for s in subs:
            await db.delete(s)
        await db.flush()  # 先提交 submissions 的 DELETE
        await db.delete(a)
    await db.flush()

    classes = (await db.execute(select(Class).filter(Class.teacher_id == teacher_id))).scalars().all()
    for c in classes:
        await db.delete(c)

    teacher.is_deleted = True
    await db.commit()
    return {"message": f"已删除教师 {teacher.name} 及相关数据"}


@router.post("/teacher/login", response_model=TokenResponse)
async def teacher_login(body: TeacherLogin, db: AsyncSession = Depends(get_db)):
    """教师登录"""
    teacher = (await db.execute(
        select(Teacher).filter(Teacher.username == body.username, Teacher.is_deleted == False)
    )).scalar_one_or_none()

    if not teacher or not pwd_context.verify(body.password, teacher.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码不正确")

    token = create_access_token({"sub": str(teacher.id), "type": "teacher"})
    return TokenResponse(access_token=token, token_type="bearer", user_type="teacher")


@router.post("/teacher/register", response_model=TokenResponse)
async def teacher_register(body: TeacherRegister, db: AsyncSession = Depends(get_db)):
    """教师注册（开放注册）"""
    existing = (await db.execute(
        select(Teacher).filter(Teacher.username == body.username)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已被注册")

    teacher = Teacher(
        name=body.name,
        username=body.username,
        password_hash=pwd_context.hash(body.password),
        school=body.school,
    )
    db.add(teacher)
    await db.commit()
    await db.refresh(teacher)

    token = create_access_token({"sub": str(teacher.id), "type": "teacher"})
    return TokenResponse(access_token=token, token_type="bearer", user_type="teacher")
