"""
FastAPI 主应用入口
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

from config import settings
from database import init_db
from routers import auth, homework, exam, analysis, teacher, coze_plugin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    init_db()
    # 确保上传目录存在
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(
    title="数学教学智能体 API",
    description="AI 数学教学辅助系统",
    version="2.0.0",
    lifespan=lifespan,
)

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件（上传的图片）
app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")

# API 路由（必须在 catch-all 前面注册）
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(homework.router, prefix="/api/homework", tags=["作业"])
app.include_router(exam.router, prefix="/api/exam", tags=["考试"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["分析"])
app.include_router(teacher.router, prefix="/api/teacher", tags=["教师端"])
app.include_router(coze_plugin.router, tags=["Coze 插件"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "数学教学智能体运行中"}


# 前端 SPA 托管（所有非 /api/ 路由都返回 index.html）
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists() and (FRONTEND_DIR / "index.html").exists():
    app.mount("/_next", StaticFiles(directory=str(FRONTEND_DIR / "_next")), name="next")

    index_html = FRONTEND_DIR / "index.html"
    index_content = index_html.read_text(encoding="utf-8")

    @app.api_route("/{full_path:path}", methods=["GET"], include_in_schema=False)
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("uploads/"):
            return HTMLResponse(content="", status_code=404)
        fp = FRONTEND_DIR / full_path
        if fp.exists() and fp.is_file():
            return FileResponse(fp)
        return HTMLResponse(content=index_content)
