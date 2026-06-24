"""
管理账号初始化脚本 — 自动创建管理员账号 + 默认 AI 模型配置
"""
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, SessionLocal
from models import Teacher, AIProvider
from sqlalchemy import text
from config import settings

logger = logging.getLogger(__name__)

# 兼容 bcrypt + 旧 SHA-256 格式（共用 routers/auth.py 的 _verify_password）
from routers.auth import _hash_password, _verify_password

pwd_context = type("PwdCtx", (), {"hash": staticmethod(_hash_password), "verify": staticmethod(_verify_password)})()

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
        existing_provider = db.query(AIProvider).first()
        if not existing_provider:
            # 从环境变量读取默认 API Key
            default_api_key = settings.AGNES_API_KEY or ""
            default_base_url = settings.AGNES_BASE_URL
            default_model = settings.AGNES_MODEL

            if default_api_key:
                default = AIProvider(
                    name="Agnes AI Flash (默认)",
                    provider="openai-compatible",
                    base_url=default_base_url,
                    api_key=default_api_key,
                    model=default_model,
                    is_active=True,
                )
                db.add(default)
                logger.info(f"已从环境变量添加默认 AI 模型: {default_model}")
            else:
                logger.warning("⚠️ 未设置 AGNES_API_KEY，跳过 AI 模型自动配置。请在管理后台手动添加。")

            db.commit()
        else:
            # 已存在配置：不覆写已有 key，只保证至少有一个活跃的
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
