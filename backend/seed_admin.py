"""
管理账号初始化脚本
运行: python seed_admin.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, SessionLocal
from models import Teacher
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "超级管理员"


def seed_admin():
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Teacher).filter(Teacher.username == ADMIN_USERNAME).first()
        if existing:
            if not existing.is_admin:
                existing.is_admin = True
                db.commit()
                print(f"✅ 已升级 '{ADMIN_USERNAME}' 为管理员")
            else:
                print(f"ℹ️ 管理员账号已存在 (id={existing.id})")
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
        print(f"✅ 管理员账号创建成功")
        print(f"   用户名: {ADMIN_USERNAME}")
        print(f"   密码:   {ADMIN_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
