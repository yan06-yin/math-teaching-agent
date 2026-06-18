"""
Coze 插件 API 路由
同时支持 Form-data 和 JSON Body（Coze 发的是 JSON）
"""
import logging

from fastapi import APIRouter, HTTPException, Request, Query
from sqlalchemy.orm import Session
from fastapi import Depends

from database import get_db
from models import Student, HomeworkSubmission, ExamAttempt
from services.ocr_service import ocr_service
from services.coze_service import coze_service
from services.exam_service import generate_and_save_exam, grade_exam
from utils.knowledge_mapper import normalize_knowledge_point, get_knowledge_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plugin", tags=["Coze 插件"])


async def _parse_body(request: Request) -> dict:
    """一次性解析请求体（JSON 或 Form），返回参数字典"""
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        try:
            return await request.json() or {}
        except Exception:
            return {}
    try:
        form = await request.form()
        return dict(form)
    except Exception:
        return {}


def _g(body: dict, name: str, default=None):
    """从 body 中获取参数"""
    return body.get(name, default)


@router.post("/ocr")
async def plugin_ocr(request: Request):
    """[插件] OCR 识别"""
    body = await _parse_body(request)
    image_url = _g(body, "image_url")
    if not image_url:
        raise HTTPException(status_code=422, detail="image_url is required")
    try:
        text = ocr_service.extract_text(image_url)
        return {"success": True, "text": text, "text_length": len(text)}
    except Exception as e:
        logger.error(f"OCR 失败: {e}")
        return {"success": False, "text": "", "error": str(e)}


@router.post("/grade")
async def plugin_grade(request: Request):
    """[插件] AI 批改作业"""
    body = await _parse_body(request)
    student_name = _g(body, "student_name")
    school_level = _g(body, "school_level", "初中")
    questions_and_answers = _g(body, "questions_and_answers")
    if not student_name or not questions_and_answers:
        raise HTTPException(status_code=422, detail="student_name and questions_and_answers are required")
    try:
        result = await coze_service.grade_homework(student_name, school_level, questions_and_answers)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"批改失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-exam")
async def plugin_generate_exam(request: Request):
    """[插件] 智能出题"""
    body = await _parse_body(request)
    school_level = _g(body, "school_level")
    if not school_level:
        raise HTTPException(status_code=422, detail="school_level is required")
    knowledge_points = _g(body, "knowledge_points", "")
    difficulty = int(_g(body, "difficulty", 3))
    question_count = int(_g(body, "question_count", 10))
    points_list = [p.strip() for p in str(knowledge_points).split(",") if p.strip()]
    config = {"knowledge_points": points_list, "difficulty": difficulty, "question_count": question_count}
    try:
        result = await coze_service.generate_exam(school_level, config)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"出题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnose")
async def plugin_diagnose(request: Request):
    """[插件] 学习诊断"""
    body = await _parse_body(request)
    student_name = _g(body, "student_name")
    school_level = _g(body, "school_level", "初中")
    performance_data = _g(body, "performance_data")
    if not student_name or not performance_data:
        raise HTTPException(status_code=422, detail="student_name and performance_data are required")
    try:
        result = await coze_service.generate_diagnostic_report(student_name, school_level, performance_data)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"诊断失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learning-plan")
async def plugin_learning_plan(request: Request):
    """[插件] 学习计划"""
    body = await _parse_body(request)
    student_name = _g(body, "student_name")
    school_level = _g(body, "school_level", "初中")
    weak_points = _g(body, "weak_points")
    if not student_name or not weak_points:
        raise HTTPException(status_code=422, detail="student_name and weak_points are required")
    points_list = [p.strip() for p in str(weak_points).split(",") if p.strip()]
    try:
        result = await coze_service.generate_learning_plan(student_name, school_level, points_list)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"学习计划生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-point")
async def plugin_knowledge_point(
    text: str = Query(..., description="要查询的知识点关键词"),
    level: str = Query("初中", description="学段"),
):
    """[插件] 知识点映射"""
    standard = normalize_knowledge_point(text)
    info = get_knowledge_info(standard, level)
    return {"success": True, "original": text, "standard": standard, "info": info}


@router.get("/health")
async def plugin_health():
    """插件健康检查"""
    return {"status": "ok", "service": "数学教学智能体 Coze 插件", "version": "1.0.0"}
