"""
JWT 认证依赖 — 异步版本
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Student, Teacher
from config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """解码 JWT 并返回当前用户 (Student 或 Teacher)。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据，请重新登录",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        user_type: str = payload.get("type")
        if user_id is None or user_type is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if user_type == "student":
        user = (await db.execute(select(Student).filter(Student.id == int(user_id)))).scalar_one_or_none()
    elif user_type == "teacher":
        user = (await db.execute(select(Teacher).filter(Teacher.id == int(user_id)))).scalar_one_or_none()
    else:
        raise credentials_exception

    if user is None:
        raise credentials_exception

    return user, user_type


async def require_student(current_user=Depends(get_current_user)):
    """依赖注入：仅允许学生访问"""
    user, user_type = current_user
    if user_type != "student":
        raise HTTPException(status_code=403, detail="需要学生身份")
    if getattr(user, "is_deleted", False):
        raise HTTPException(status_code=403, detail="账号已被删除")
    return user, user_type


async def require_teacher(current_user=Depends(get_current_user)):
    """依赖注入：仅允许教师访问"""
    user, user_type = current_user
    if user_type != "teacher":
        raise HTTPException(status_code=403, detail="需要教师身份")
    if getattr(user, "is_deleted", False):
        raise HTTPException(status_code=403, detail="账号已被删除")
    return user, user_type


async def require_admin(current_user=Depends(get_current_user)):
    """依赖注入：仅允许管理员访问"""
    user, user_type = current_user
    if user_type != "teacher" or not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if getattr(user, "is_deleted", False):
        raise HTTPException(status_code=403, detail="账号已被删除")
    return user, user_type
