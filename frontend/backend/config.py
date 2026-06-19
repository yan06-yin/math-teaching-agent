"""
数学教学智能体 — 配置文件
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 项目根目录
    PROJECT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # SQLite 数据库
    DB_PATH: str = os.path.join(PROJECT_DIR, "database", "math_teaching.db")
    DATABASE_URL: str = f"sqlite:///{DB_PATH}"

    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "math-teaching-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时

    # Agnes AI API（替代 Coze）
    AGNES_API_KEY: str = os.getenv("AGNES_API_KEY", "")
    AGNES_BASE_URL: str = os.getenv("AGNES_BASE_URL", "https://apihub.agnes-ai.com/v1")
    AGNES_MODEL: str = os.getenv("AGNES_MODEL", "agnes-2.0-flash")

    # 文件上传
    UPLOAD_DIR: str = os.path.join(PROJECT_DIR, "uploads")

    # 跨域
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = {"env_file": ".env", "case_sensitive": True}


settings = Settings()
