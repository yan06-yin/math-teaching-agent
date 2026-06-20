"""
数据库连接与初始化
支持 SQLite（默认）、MySQL、PostgreSQL
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings

# 根据不同数据库类型设置连接参数
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite 需要确保目录存在
    DB_DIR = os.path.dirname(settings.DB_PATH)
    os.makedirs(DB_DIR, exist_ok=True)
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
elif settings.DATABASE_URL.startswith("mysql"):
    # MySQL 使用 pymysql
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
else:
    # PostgreSQL 或其他
    engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()