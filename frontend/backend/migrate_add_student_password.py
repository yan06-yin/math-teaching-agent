"""
数据库迁移脚本 — 为 Student 表添加 password_hash, last_login, role 列
运行一次即可: python migrate_add_student_password.py
"""
import sqlite3
import os

# 数据库路径: backend/../database/math_teaching.db
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "database", "math_teaching.db")
DB_PATH = os.path.normpath(DB_PATH)


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"数据库文件不存在: {DB_PATH}，跳过迁移（首次启动时会自动创建）")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查现有列
    cursor.execute("PRAGMA table_info(students)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    changes = []
    if "password_hash" not in existing_cols:
        cursor.execute(
            "ALTER TABLE students ADD COLUMN password_hash VARCHAR(128) NOT NULL DEFAULT ''"
        )
        changes.append("password_hash")

    if "last_login" not in existing_cols:
        cursor.execute("ALTER TABLE students ADD COLUMN last_login DATETIME")
        changes.append("last_login")

    if "role" not in existing_cols:
        cursor.execute(
            "ALTER TABLE students ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'student'"
        )
        changes.append("role")

    conn.commit()

    if changes:
        print(f"迁移完成，新增列: {', '.join(changes)}")
    else:
        print("所有列已存在，无需迁移。")

    conn.close()


if __name__ == "__main__":
    migrate()
