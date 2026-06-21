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
        # PostgreSQL — 增加连接池以支持多 worker 并发
        engine = create_engine(
            _db_url,
            pool_size=20,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_use_lifo=True,
        )
        # 立即测试连接（create_engine 是懒连接，不主动连接不会报错）
        with engine.connect():
            pass
    else:
        raise ValueError(f"不支持的数据库类型（URL 前缀）: {_db_url[:30]}...")

except Exception as e:
    logger.error(f"❌ 数据库连接失败: {e}")
    logger.warning("⚠️ 正在回退到 SQLite...")
    # 回退到 SQLite
    _db_url = f"sqlite:///{settings.DB_PATH}"
    db_path = settings.DB_PATH
    if not db_path or not os.path.exists(os.path.dirname(db_path)):
        db_path = _db_url.replace("sqlite:///", "", 1)
    DB_DIR = os.path.dirname(db_path)
    os.makedirs(DB_DIR, exist_ok=True)
    logger.info(f"📁 SQLite 数据库目录: {DB_DIR}")
    engine = create_engine(
        _db_url,
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)

    # 兼容旧数据库：检查并添加缺失的列
    try:
        from sqlalchemy import inspect, text as sa_text
        inspector = inspect(engine)

        # 检查 students 表
        student_cols = {c["name"] for c in inspector.get_columns("students")} if "students" in inspector.get_table_names() else set()
        if student_cols:
            if "is_deleted" not in student_cols:
                with engine.connect() as conn:
                    conn.execute(sa_text("ALTER TABLE students ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    logger.info("✅ 已为 students 表添加 is_deleted 列")

        # 检查 teachers 表
        teacher_cols = {c["name"] for c in inspector.get_columns("teachers")} if "teachers" in inspector.get_table_names() else set()
        if teacher_cols:
            if "is_admin" not in teacher_cols:
                with engine.connect() as conn:
                    conn.execute(sa_text("ALTER TABLE teachers ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    logger.info("✅ 已为 teachers 表添加 is_admin 列")
            if "is_deleted" not in teacher_cols:
                with engine.connect() as conn:
                    conn.execute(sa_text("ALTER TABLE teachers ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    logger.info("✅ 已为 teachers 表添加 is_deleted 列")
    except Exception as e:
        logger.warning(f"数据库兼容性检查（可忽略）: {e}")


def get_db():
    """依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()