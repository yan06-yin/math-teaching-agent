"""
FastAPI 主应用入口
"""
import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager

# Windows 编码兼容（确保中文正确处理）
if os.name == "nt":
    os.environ.setdefault("PYTHONUTF8", "1")
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pathlib import Path

from config import settings

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(levelname)s:     %(message)s",
)

from database import init_db
from routers import auth, homework, exam, analysis, teacher, assignments, classes, admin
from seed_admin import seed_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    init_db()
    try:
        seed_admin()
        from services.open_model_service import open_model_service
        open_model_service.reload_from_db()
    except Exception as e:
        logging.warning(f"管理员账号初始化跳过: {e}")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield
    from services.open_model_service import open_model_service
    if open_model_service._client and not open_model_service._client.is_closed:
        await open_model_service._client.aclose()


app = FastAPI(
    title="AI 智能作业批改系统 API",
    description="AI 多学科作业批改系统",
    version="2.0.0",
    lifespan=lifespan,
)


# 速率限制
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    HAS_RATE_LIMIT = True
except ImportError:
    HAS_RATE_LIMIT = False
    logging.warning("slowapi 未安装，速率限制未启用。安装：pip install slowapi")


# 全局异常处理器
@app.exception_handler(500)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if hasattr(exc, "status_code"):
        raise exc
    logging.error(f"未捕获的异常: {exc}\n{traceback.format_exc()}")
    detail = "内部服务器错误，请稍后重试或联系管理员"
    if settings.is_production:
        return JSONResponse(status_code=500, content={"detail": detail})
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)}"},
    )


# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# 安全响应头中间件
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # 上传目录的图片通过 img 标签引用，不会执行脚本
    if request.url.path.startswith("/uploads/"):
        response.headers["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    return response

# 静态文件（上传的图片）
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")

# API 路由（必须在 catch-all 前面注册）
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(homework.router, prefix="/api/homework", tags=["作业"])
app.include_router(exam.router, prefix="/api/exam", tags=["考试"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["分析"])
app.include_router(teacher.router, prefix="/api/teacher", tags=["教师端"])
app.include_router(assignments.router, prefix="/api", tags=["作业发布"])
app.include_router(classes.router, prefix="/api/classes", tags=["班级管理"])
app.include_router(admin.router, prefix="/api/admin", tags=["管理员"])


@app.get("/api/health")
async def health_check():
    db_type = "unknown"
    _url = settings.DATABASE_URL
    if _url.startswith("sqlite"):
        db_type = "SQLite"
    elif _url.startswith("mysql"):
        db_type = "MySQL"
    elif _url.startswith("postgresql") or _url.startswith("postgres"):
        db_type = "PostgreSQL"
    return {
        "status": "ok",
        "message": "AI 智能作业批改系统运行中",
        "database": db_type,
    }


# 前端 SPA 托管
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists() and (FRONTEND_DIR / "index.html").exists():
    # 挂载所有前端静态资源
    app.mount("/_next", StaticFiles(directory=str(FRONTEND_DIR / "_next")), name="next")

    index_content = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("uploads/") or full_path.startswith("_next/"):
            return JSONResponse(content={"detail": "Not Found"}, status_code=404)
        # 阻止访问敏感文件（配置、源码、数据库、备份等）
        blocked_exts = {".env", ".py", ".db", ".sqlite", ".sqlite3", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".bak", ".log"}
        blocked_names = {".env", ".gitignore", ".gitattributes", "Dockerfile", "docker-compose.yml"}
        from urllib.parse import unquote
        safe_path = unquote(full_path)
        name = os.path.basename(safe_path)
        _, ext = os.path.splitext(name)
        if name in blocked_names or ext.lower() in blocked_exts:
            return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
        # 尝试精确匹配静态文件
        fp = FRONTEND_DIR / full_path
        if fp.exists() and fp.is_file():
            # 防止路径穿越
            try:
                fp.resolve().relative_to(FRONTEND_DIR.resolve())
            except ValueError:
                return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
            return FileResponse(fp)
        # 尝试添加 .html 后缀
        fp_html = FRONTEND_DIR / f"{full_path}.html"
        if fp_html.exists() and fp_html.is_file():
            try:
                fp_html.resolve().relative_to(FRONTEND_DIR.resolve())
            except ValueError:
                return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
            return FileResponse(fp_html)
        # SPA 回退
        return HTMLResponse(content=index_content)
