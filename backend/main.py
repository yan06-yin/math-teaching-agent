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
from routers import auth, homework, exam, analysis, teacher, coze_plugin, assignments


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
app.include_router(assignments.router, prefix="/api", tags=["作业发布"])


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "数学教学智能体运行中"}


# 前端 SPA 托管
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists() and (FRONTEND_DIR / "index.html").exists():
    # 挂载所有前端静态资源
    app.mount("/_next", StaticFiles(directory=str(FRONTEND_DIR / "_next")), name="next")

    index_content = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("uploads/") or full_path.startswith("_next/"):
            return HTMLResponse(content="", status_code=404)
        # 尝试精确匹配静态文件
        fp = FRONTEND_DIR / full_path
        if fp.exists() and fp.is_file():
            return FileResponse(fp)
        # 尝试添加 .html 后缀
        fp_html = FRONTEND_DIR / f"{full_path}.html"
        if fp_html.exists() and fp_html.is_file():
            return FileResponse(fp_html)
        # SPA 回退
        return HTMLResponse(content=index_content)
