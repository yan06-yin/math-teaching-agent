"""
管理账号初始化脚本 — 自动创建管理员账号
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, SessionLocal
from models import Teacher
from passlib.context import CryptContext
from sqlalchemy import text

logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "超级管理员"


def seed_admin():
    """确保管理员账号存在（幂等，启动时调用）"""
    init_db()

    db = SessionLocal()
    try:
        # 确保 is_admin 列存在（兼容旧数据库）
        try:
            db.execute(text("ALTER TABLE teachers ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            db.commit()
        except Exception:
            db.rollback()  # 列已存在，忽略

        existing = db.query(Teacher).filter(Teacher.username == ADMIN_USERNAME).first()
        if existing:
            if not existing.is_admin:
                existing.is_admin = True
                db.commit()
                logger.info(f"已升级 '{ADMIN_USERNAME}' 为管理员")
            return

        admin = Teacher(
            name=ADMIN_NAME,
            username=ADMIN_USERNAME,
            password_hash=pwd_context.hash(ADMIN_PASSWORD),
            school="系统管理",
            is_admin=True,
        )
        db.add(admin)
        db.commit()
        logger.info(f"管理员账号创建成功 (admin / {ADMIN_PASSWORD})")
    except Exception as e:
        logger.error(f"管理员账号创建失败: {e}")
        db.rollback()
    finally:
        db.close()
