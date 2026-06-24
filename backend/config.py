"""
数学教学智能体 — 配置文件
"""
import logging
import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # 项目根目录
    PROJECT_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 数据库（可通过 DATABASE_URL 环境变量切换 MySQL/PostgreSQL/SQLite）
    DB_PATH: str = os.path.join(PROJECT_DIR, "database", "math_teaching.db")
    DATABASE_URL: str = f"sqlite:///{DB_PATH}"

    # JWT（生产环境必须通过环境变量 SECRET_KEY 设置，否则每次启动会重新生成）
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时

    # Agnes AI API（替代 Coze，使用 OpenAI 兼容接口）
    # .env 文件示例：
    # AGNES_API_KEY=your_key_here
    # AGNES_BASE_URL=https://apihub.agnes-ai.com/v1
    # AGNES_MODEL=agnes-2.0-flash
    AGNES_API_KEY: str = ""
    AGNES_BASE_URL: str = "https://apihub.agnes-ai.com/v1"
    AGNES_MODEL: str = "agnes-2.0-flash"

    # 文件上传
    UPLOAD_DIR: str = os.path.join(PROJECT_DIR, "uploads")

    # 跨域
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # 日志级别
    LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """DATABASE_URL 为空时回退到 SQLite；SECRET_KEY 为空时自动生成"""
        if not self.DATABASE_URL or not self.DATABASE_URL.strip():
            self.DATABASE_URL = f"sqlite:///{self.DB_PATH}"
        if not self.SECRET_KEY:
            self.SECRET_KEY = secrets.token_hex(32)
            logging.warning("⚠️ SECRET_KEY 未设置，已自动生成随机密钥（重启后失效，生产环境请设置环境变量）")
        return self


settings = Settings()

# 启动时日志（隐藏密码等敏感信息）
_url = settings.DATABASE_URL
if _url.startswith("sqlite"):
    logging.info(f"📦 数据库: SQLite ({settings.DB_PATH})")
elif _url.startswith("mysql"):
    logging.info("📦 数据库: MySQL")
elif _url.startswith("postgresql") or _url.startswith("postgres"):
    logging.info("📦 数据库: PostgreSQL")
else:
    logging.warning(f"⚠️ 未知数据库类型: {_url[:20]}...")
