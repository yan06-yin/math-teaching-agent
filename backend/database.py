"""
数据库连接与初始化
支持 SQLite（默认）、MySQL、PostgreSQL
使用异步 SQLAlchemy（aiosqlite / asyncpg）
"""
import logging
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

logger = logging.getLogger(__name__)

# ===== 异步引擎（主请求处理用）=====
_db_url = settings.DATABASE_URL

def _to_async_url(url: str) -> str:
    """将同步 URL 转为异步 URL"""
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1).replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("mysql"):
        return url.replace("mysql://", "mysql+aiomysql://", 1)
    return url

try:
    async_url = _to_async_url(_db_url)

    if _db_url.startswith("sqlite"):
        db_path = settings.DB_PATH
        if not db_path or not os.path.exists(os.path.dirname(db_path)):
            db_path = _db_url.replace("sqlite:///", "", 1)
        DB_DIR = os.path.dirname(db_path)
        os.makedirs(DB_DIR, exist_ok=True)
        logger.info(f"📁 SQLite 数据库目录: {DB_DIR}")
    elif _db_url.startswith("postgresql") or _db_url.startswith("postgres"):
        logger.info("📦 PostgreSQL 数据库（异步）")
    elif _db_url.startswith("mysql"):
        logger.info("📦 MySQL 数据库（异步）")

    async_engine = create_async_engine(
        async_url,
        pool_pre_ping=True,
        **({"pool_size": 20, "max_overflow": 20, "pool_recycle": 300} if "postgresql" in async_url else {}),
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("✅ 异步数据库引擎已创建")

except Exception as e:
    logger.error(f"❌ 异步数据库引擎创建失败: {e}")
    logger.warning("⚠️ 回退到 SQLite...")
    _db_url = f"sqlite:///{settings.DB_PATH}"
    async_url = _to_async_url(_db_url)
    db_path = settings.DB_PATH
    if not db_path or not os.path.exists(os.path.dirname(db_path)):
        db_path = _db_url.replace("sqlite:///", "", 1)
    DB_DIR = os.path.dirname(db_path)
    os.makedirs(DB_DIR, exist_ok=True)
    async_engine = create_async_engine(async_url)
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


# ===== 同步引擎（仅用于启动时迁移和 seed_admin）=====
sync_db_url = _db_url if _db_url else f"sqlite:///{settings.DB_PATH}"
sync_engine = create_engine(
    sync_db_url,
    connect_args={"check_same_thread": False} if sync_db_url.startswith("sqlite") else {},
)


class Base(DeclarativeBase):
    pass


def init_db():
    """创建所有表（同步，启动时调用）"""
    Base.metadata.create_all(bind=sync_engine)

    # 兼容旧数据库：检查并添加缺失的列
    try:
        from sqlalchemy import inspect, text as sa_text
        inspector = inspect(sync_engine)
        table_names = set(inspector.get_table_names())

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
                    with sync_engine.connect() as conn:
                        try:
                            conn.execute(sa_text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                            conn.commit()
                            logger.info(f"已为 {table} 表添加 {column} 列")
                        except Exception as e:
                            conn.rollback()
                            logger.warning(f"添加 {table}.{column} 失败（可忽略）: {e}")

        if "grading_tasks" in table_names:
            with sync_engine.connect() as conn:
                try:
                    conn.execute(sa_text("ALTER TABLE grading_tasks DROP CONSTRAINT IF EXISTS grading_tasks_submission_id_fkey"))
                    conn.commit()
                except Exception:
                    conn.rollback()

    except Exception as e:
        logger.warning(f"数据库兼容性检查（可忽略）: {e}")


async def get_db():
    """依赖注入：获取异步数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            pass  # async with 自动关闭


# 保留同步 SessionLocal 供 seed_admin 使用
from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
