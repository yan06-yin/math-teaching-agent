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
        table_names = set(inspector.get_table_names())

        # 需要检查的列缺失情况
        migrations = [
            ("students", "is_deleted", "BOOLEAN DEFAULT FALSE"),
            ("teachers", "is_admin", "BOOLEAN DEFAULT FALSE"),
            ("teachers", "is_deleted", "BOOLEAN DEFAULT FALSE"),
            ("assignments", "class_id", "INTEGER REFERENCES classes(id)"),
            ("assignments", "due_date", "TIMESTAMP"),
            ("homework_submissions", "wrong_questions_json", "JSON DEFAULT '[]'"),
            ("homework_submissions", "status", "VARCHAR(20) DEFAULT 'pending'"),
            ("homework_submissions", "is_deleted", "BOOLEAN DEFAULT FALSE"),
            ("exam_attempts", "is_deleted", "BOOLEAN DEFAULT FALSE"),
            ("exam_attempts", "details_json", "JSON DEFAULT '[]'"),
            ("exam_attempts", "status", "VARCHAR(20) DEFAULT 'draft'"),
        ]

        for table, column, col_type in migrations:
            if table in table_names:
                cols = {c["name"] for c in inspector.get_columns(table)}
                if column not in cols:
                    with engine.connect() as conn:
                        try:
                            conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                            conn.commit()
                            logger.info(f"已为 {table} 表添加 {column} 列")
                        except Exception as e:
                            conn.rollback()
                            logger.warning(f"添加 {table}.{column} 失败（可忽略）: {e}")

        # 移除 grading_tasks.submission_id 的外键约束（该字段同时关联 homework 和 exam，不应用 FK）
        if "grading_tasks" in table_names:
            with engine.connect() as conn:
                try:
                    conn.execute(sa_text("ALTER TABLE grading_tasks DROP CONSTRAINT IF EXISTS grading_tasks_submission_id_fkey"))
                    conn.commit()
                except Exception:
                    conn.rollback()

    except Exception as e:
        logger.warning(f"数据库兼容性检查（可忽略）: {e}")


def get_db():
    """依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()