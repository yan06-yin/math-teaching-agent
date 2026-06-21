"""
管理账号初始化脚本 — 自动创建管理员账号 + 默认 AI 模型配置
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, SessionLocal
from models import Teacher
import hashlib
import secrets
from sqlalchemy import text
from config import settings

logger = logging.getLogger(__name__)

# 兼容 bcrypt 不可用的环境
try:
    _test_ctx_pass = CryptContext(schemes=["bcrypt"], deprecated="auto")
    _test_ctx_pass.hash("test")
    pwd_context = _test_ctx_pass
except Exception:
    class _FallbackPwd:
        def hash(self, pw):
            salt = secrets.token_hex(16)
            return f"sha256${salt}${hashlib.sha256((pw + salt).encode()).hexdigest()}"
        def verify(self, pw, h):
            try:
                parts = h.split("$")
                return parts[0] == "sha256" and hashlib.sha256((pw + parts[1]).encode()).hexdigest() == parts[2]
            except Exception:
                return False
    pwd_context = _FallbackPwd()

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "超级管理员"


def seed_admin():
    """确保管理员账号存在，启动时自动调用"""
    init_db()

    db = SessionLocal()
    try:
        # 确保 is_admin 列存在（兼容旧数据库）
        try:
            db.execute(text("ALTER TABLE teachers ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            db.commit()
        except Exception:
            db.rollback()

        existing = db.query(Teacher).filter(Teacher.username == ADMIN_USERNAME).first()
        if existing:
            if not existing.is_admin:
                existing.is_admin = True
                db.commit()
                logger.info(f"已升级 '{ADMIN_USERNAME}' 为管理员")
        else:
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

        # 检查 AI 模型配置
        from models import AIProvider
        existing_provider = db.query(AIProvider).first()
        if not existing_provider:
            default = AIProvider(
                name="Agnes AI (默认)",
                provider="openai-compatible",
                base_url="https://apihub.agnes-ai.com/v1",
                api_key=settings.AGNES_API_KEY or "",
                model=settings.AGNES_MODEL or "agnes-2.0-flash",
                is_active=True,
            )
            db.add(default)
            db.commit()
            logger.info("已添加默认 AI 模型配置")
        else:
            if not db.query(AIProvider).filter(AIProvider.is_active == True).first():
                first = db.query(AIProvider).first()
                if first:
                    first.is_active = True
                    db.commit()

        logger.info("系统初始化完成")
    except Exception as e:
        logger.error(f"系统初始化失败: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
