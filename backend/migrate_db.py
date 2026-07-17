"""
数据库迁移脚本 — 为多学科支持添加新字段

SQLite 版本：由于 SQLite 的 ALTER TABLE 能力有限，使用 recreate 策略。
PostgreSQL 版本：使用标准的 ALTER TABLE ADD COLUMN。

用法：
    python backend/migrate_db.py
"""

import asyncio
import logging
import os
import sys

# 添加 backend 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_sqlite():
    """SQLite 迁移 — 通过 recreate 表的方式添加 subject 字段"""
    from database import engine, Base
    from sqlalchemy import inspect, text
    from sqlalchemy.ext.asyncio import create_async_engine

    # 获取当前数据库路径
    db_url = str(engine.url)
    logger.info(f"当前数据库: {db_url}")

    inspector = inspect(engine)

    # 检查 homework_submissions 表是否有 subject 字段
    columns = [col["name"] for col in inspector.get_columns("homework_submissions")]
    logger.info(f"homework_submissions 现有字段: {columns}")

    if "subject" not in columns:
        logger.info("添加 subject 字段到 homework_submissions...")
        async with engine.begin() as conn:
            # SQLite 需要 recreate 表
            await conn.execute(text("""
                CREATE TABLE homework_submissions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL,
                    photo_url VARCHAR(512) NOT NULL,
                    extracted_text TEXT DEFAULT '',
                    student_answers TEXT DEFAULT '',
                    subject VARCHAR(20) DEFAULT 'math',
                    correct_count INTEGER DEFAULT 0,
                    total_count INTEGER DEFAULT 0,
                    score FLOAT DEFAULT 0,
                    comments TEXT DEFAULT '',
                    wrong_questions_json JSON DEFAULT '[]',
                    status VARCHAR(20) DEFAULT 'pending',
                    is_deleted BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(student_id) REFERENCES students(id)
                )
            """))
            await conn.execute(text("""
                INSERT INTO homework_submissions_new
                SELECT id, student_id, photo_url, extracted_text, student_answers,
                       'math' as subject, correct_count, total_count, score, comments,
                       wrong_questions_json, status, is_deleted, created_at
                FROM homework_submissions
            """))
            await conn.execute(text("DROP TABLE homework_submissions"))
            await conn.execute(text("ALTER TABLE homework_submissions_new RENAME TO homework_submissions"))
            await conn.execute(text("CREATE INDEX ix_homework_submissions_id ON homework_submissions(id)"))
            await conn.execute(text("CREATE INDEX ix_homework_submissions_student_id ON homework_submissions(student_id)"))
        logger.info("✅ homework_submissions 迁移完成")
    else:
        logger.info("✅ homework_submissions 已有 subject 字段，跳过")

    # 检查 knowledge_points 表
    if "knowledge_points" in [t for t in await engine.run_sync(lambda: inspector.get_table_names())]:
        kp_columns = [col["name"] for col in inspector.get_columns("knowledge_points")]
        logger.info(f"knowledge_points 现有字段: {kp_columns}")

        if "subject" not in kp_columns:
            logger.info("添加 subject 字段到 knowledge_points...")
            async with engine.begin() as conn:
                await conn.execute(text("""
                    CREATE TABLE knowledge_points_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100) UNIQUE NOT NULL,
                        level VARCHAR(10),
                        subject VARCHAR(20) DEFAULT 'math',
                        description TEXT DEFAULT '',
                        related_points_json JSON DEFAULT '[]'
                    )
                """))
                await conn.execute(text("""
                    INSERT INTO knowledge_points_new
                    SELECT id, name, level, 'math' as subject, description, related_points_json
                    FROM knowledge_points
                """))
                await conn.execute(text("DROP TABLE knowledge_points"))
                await conn.execute(text("ALTER TABLE knowledge_points_new RENAME TO knowledge_points"))
                await conn.execute(text("CREATE INDEX ix_knowledge_points_id ON knowledge_points(id)"))
            logger.info("✅ knowledge_points 迁移完成")
        else:
            logger.info("✅ knowledge_points 已有 subject 字段，跳过")

    logger.info("🎉 SQLite 迁移完成！")


async def migrate_postgresql():
    """PostgreSQL 迁移 — 直接 ALTER TABLE ADD COLUMN"""
    from database import engine
    from sqlalchemy import inspect, text

    inspector = inspect(engine)

    # homework_submissions
    columns = [col["name"] for col in inspector.get_columns("homework_submissions")]
    if "subject" not in columns:
        logger.info("PostgreSQL: 添加 subject 到 homework_submissions...")
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE homework_submissions ADD COLUMN subject VARCHAR(20) DEFAULT 'math'"))
        logger.info("✅ 完成")
    else:
        logger.info("✅ homework_submissions.subject 已存在")

    # knowledge_points
    if "knowledge_points" in inspector.get_table_names():
        kp_columns = [col["name"] for col in inspector.get_columns("knowledge_points")]
        if "subject" not in kp_columns:
            logger.info("PostgreSQL: 添加 subject 到 knowledge_points...")
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE knowledge_points ADD COLUMN subject VARCHAR(20) DEFAULT 'math'"))
            logger.info("✅ 完成")
        else:
            logger.info("✅ knowledge_points.subject 已存在")

    # 插入默认的语文和英语知识点
    async with engine.begin() as conn:
        from utils.knowledge_mapper import CHINESE_KNOWLEDGE, ENGLISH_KNOWLEDGE
        for kp_name in CHINESE_KNOWLEDGE:
            await conn.execute(text(
                "INSERT INTO knowledge_points (name, level, subject) VALUES (:name, :level, :subject) ON CONFLICT (name) DO NOTHING"
            ), {"name": kp_name, "level": "初中", "subject": "chinese"})
        for kp_name in ENGLISH_KNOWLEDGE:
            await conn.execute(text(
                "INSERT INTO knowledge_points (name, level, subject) VALUES (:name, :level, :subject) ON CONFLICT (name) DO NOTHING"
            ), {"name": kp_name, "level": "初中", "subject": "english"})
        logger.info("✅ 默认语文/英语知识点已插入")

    logger.info("🎉 PostgreSQL 迁移完成！")


async def main():
    """自动检测数据库类型并执行迁移"""
    from database import engine
    db_url = str(engine.url)

    if "sqlite" in db_url.lower():
        logger.info("检测到 SQLite 数据库，执行 SQLite 迁移...")
        await migrate_sqlite()
    elif "postgresql" in db_url.lower() or "postgres" in db_url.lower():
        logger.info("检测到 PostgreSQL 数据库，执行 PostgreSQL 迁移...")
        await migrate_postgresql()
    else:
        logger.warning(f"未知数据库类型: {db_url}，尝试 SQLite 迁移...")
        await migrate_sqlite()


if __name__ == "__main__":
    asyncio.run(main())