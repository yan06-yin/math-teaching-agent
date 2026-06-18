"""
Coze 插件 API 路由
供 Coze Bot 作为插件调用，暴露核心能力：
OCR、批改作业、出题、诊断、学习计划
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from fastapi import Depends

from database import get_db
from models import Student, HomeworkSubmission, ExamAttempt
from services.ocr_service import ocr_service
from services.coze_service import coze_service
from services.exam_service import generate_and_save_exam, grade_exam
from utils.knowledge_mapper import normalize_knowledge_point, get_knowledge_info
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plugin", tags=["Coze 插件"])


@router.post("/ocr")
async def plugin_ocr(
    image_url: str = Form(..., description="图片 URL 或本地路径"),
):
    """
    [插件] OCR 识别：从图片中提取文字
    适用于 Coze 插件调用，支持网络图片 URL
    """
    try:
        text = ocr_service.extract_text(image_url)
        return {"success": True, "text": text, "text_length": len(text)}
    except Exception as e:
        logger.error(f"OCR 失败: {e}")
        return {"success": False, "text": "", "error": str(e)}


@router.post("/grade")
async def plugin_grade(
    student_name: str = Form(..., description="学生姓名"),
    school_level: str = Form("初中", description="学段：小学/初中/高中"),
    questions_and_answers: str = Form(..., description="作业题目和答案内容"),
):
    """
    [插件] AI 批改作业：传入作业内容，返回评分和批改详情
    支持 JSON 或纯文本格式的作业内容
    """
    try:
        result = await coze_service.grade_homework(
            student_name=student_name,
            school_level=school_level,
            questions_and_answers=questions_and_answers,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"批改失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-exam")
async def plugin_generate_exam(
    school_level: str = Form(..., description="学段：小学/初中/高中"),
    knowledge_points: str = Form("", description="薄弱知识点，逗号分隔"),
    difficulty: int = Form(3, description="难度 1-5"),
    question_count: int = Form(10, description="题目数量 1-50"),
):
    """
    [插件] 智能出题：根据知识点和难度生成试卷
    """
    try:
        points_list = [p.strip() for p in knowledge_points.split(",") if p.strip()]
        config = {
            "knowledge_points": points_list,
            "difficulty": difficulty,
            "question_count": question_count,
        }
        result = await coze_service.generate_exam(school_level, config)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"出题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnose")
async def plugin_diagnose(
    student_name: str = Form(..., description="学生姓名"),
    school_level: str = Form("初中", description="学段"),
    performance_data: str = Form(..., description="近期考试或作业表现数据"),
):
    """
    [插件] 学习诊断：根据学生近期表现生成诊断报告
    """
    try:
        result = await coze_service.generate_diagnostic_report(
            student_name=student_name,
            school_level=school_level,
            performance_data=performance_data,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"诊断失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learning-plan")
async def plugin_learning_plan(
    student_name: str = Form(..., description="学生姓名"),
    school_level: str = Form("初中", description="学段"),
    weak_points: str = Form(..., description="薄弱知识点列表，逗号分隔"),
):
    """
    [插件] 生成学习计划：根据薄弱知识点制定两周学习计划
    """
    try:
        points_list = [p.strip() for p in weak_points.split(",") if p.strip()]
        result = await coze_service.generate_learning_plan(
            student_name=student_name,
            school_level=school_level,
            weak_points=points_list,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"学习计划生成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge-point")
async def plugin_knowledge_point(
    text: str = Query(..., description="要查询的知识点关键词"),
    level: str = Query("初中", description="学段"),
):
    """
    [插件] 知识点映射：将文本归类到标准知识点
    """
    standard = normalize_knowledge_point(text)
    info = get_knowledge_info(standard, level)
    return {"success": True, "original": text, "standard": standard, "info": info}


@router.post("/student/create")
async def plugin_create_student(
    name: str = Form(..., description="学生姓名"),
    student_id: str = Form(..., description="学号"),
    school_level: str = Form("初中", description="学段"),
    db: Session = Depends(get_db),
):
    """
    [插件] 创建学生账号
    """
    existing = db.query(Student).filter(Student.student_id == student_id).first()
    if existing:
        return {"success": True, "data": {"id": existing.id, "name": existing.name, "already_exists": True}}

    student = Student(name=name, student_id=student_id, school_level=school_level)
    db.add(student)
    db.commit()
    db.refresh(student)
    return {"success": True, "data": {"id": student.id, "name": student.name, "already_exists": False}}


@router.get("/student/{student_id}/profile")
async def plugin_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
):
    """
    [插件] 获取学生学习画像
    """
    from sqlalchemy import func

    student = db.query(Student).get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    homework_count = db.query(func.count(HomeworkSubmission.id)).filter(
        HomeworkSubmission.student_id == student_id
    ).scalar() or 0

    exam_count = db.query(func.count(ExamAttempt.id)).filter(
        ExamAttempt.student_id == student_id
    ).scalar() or 0

    avg_hw = db.query(func.avg(HomeworkSubmission.score)).filter(
        HomeworkSubmission.student_id == student_id
    ).scalar() or 0

    avg_exam = db.query(func.avg(ExamAttempt.score)).filter(
        ExamAttempt.student_id == student_id
    ).scalar() or 0

    avg_score = float((avg_hw + avg_exam) / 2) if avg_hw and avg_exam else float(avg_hw or avg_exam or 0)

    return {
        "success": True,
        "data": {
            "name": student.name,
            "level": student.school_level,
            "homework_count": homework_count,
            "exam_count": exam_count,
            "avg_score": round(avg_score, 1),
        }
    }


@router.get("/health")
async def plugin_health():
    """插件健康检查"""
    return {"status": "ok", "service": "数学教学智能体 Coze 插件", "version": "1.0.0"}
