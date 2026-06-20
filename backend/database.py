"""
数据库连接与初始化
支持 SQLite（默认）、MySQL、PostgreSQL
"""
import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import settings

logger = logging.getLogger(__name__)

# 根据不同数据库类型设置连接参数
_db_url = settings.DATABASE_URL

try:
    if _db_url.startswith("sqlite"):
        # SQLite：确保目录存在，路径可能来自 DB_PATH 或相对路径
        db_path = settings.DB_PATH
        if not db_path or not os.path.exists(os.path.dirname(db_path)):
            # 从 URL 中提取路径（sqlite:///path）
            db_path = _db_url.replace("sqlite:///", "", 1)
        DB_DIR = os.path.dirname(db_path)
        os.makedirs(DB_DIR, exist_ok=True)
        logger.info(f"📁 SQLite 数据库目录: {DB_DIR}")
        engine = create_engine(
            _db_url,
            connect_args={"check_same_thread": False},
        )
    elif _db_url.startswith("mysql"):
        # MySQL
        engine = create_engine(
            _db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    elif _db_url.startswith("postgresql") or _db_url.startswith("postgres"):
        # PostgreSQL
        engine = create_engine(
            _db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    else:
        raise ValueError(f"不支持的数据库类型（URL 前缀）: {_db_url[:30]}...")

except Exception as e:
    logger.error(f"❌ 数据库连接失败: {e}")
    logger.error(f"   DATABASE_URL 前缀: {_db_url[:40] if _db_url else '(空)'}...")
    raise

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