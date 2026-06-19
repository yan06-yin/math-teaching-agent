"""
Coze 插件 API 路由
同时支持 Form-data 和 JSON Body（Coze 发的是 JSON）
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Student, HomeworkSubmission, ExamAttempt, ErrorRecord, ActivityLog
from services.ocr_service import ocr_service
from services.coze_service import coze_service
from services.exam_service import generate_and_save_exam, grade_exam
from utils.knowledge_mapper import normalize_knowledge_point, get_knowledge_info

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/plugin", tags=["Coze 插件"])


async def _parse_body(request: Request) -> dict:
    """从请求中提取参数（兼容 JSON 和 Form）"""
    import json as _json
    try:
        raw = await request.body()
        if not raw:
            return {}
        ct = request.headers.get("content-type", "")
        if not ct:
            return {}
        if "json" in ct.lower():
            return _json.loads(raw.decode("utf-8"))
    except Exception:
        pass
    try:
        form = await request.form()
        return dict(form)
    except Exception:
        return {}


def _g(body: dict, name: str, default=None):
    return body.get(name, default)


# ==================== 1. 学生登录/注册 ====================

@router.post("/student/login")
async def plugin_student_login(request: Request, db: Session = Depends(get_db)):
    """
    [插件] 学生登录/注册
    传入 name + student_id + school_level，如果学号已存在则登录，否则自动注册
    """
    body = await _parse_body(request)
    name = _g(body, "name")
    student_id = _g(body, "student_id")
    school_level = _g(body, "school_level", "初中")

    if not name or not student_id:
        raise HTTPException(status_code=422, detail="name and student_id are required")

    student = db.query(Student).filter(Student.student_id == student_id).first()
    if student:
        # 登录
        ActivityLog(student_id=student.id, activity_type="login", detail="登录系统")
        db.commit()
        return {"success": True, "data": {"id": student.id, "name": student.name, "student_id": student.student_id, "school_level": student.school_level, "is_new": False}}
    else:
        # 注册
        student = Student(name=name, student_id=student_id, school_level=school_level)
        db.add(student)
        db.commit()
        db.refresh(student)
        ActivityLog(student_id=student.id, activity_type="login", detail="注册并登录")
        db.commit()
        return {"success": True, "data": {"id": student.id, "name": student.name, "student_id": student.student_id, "school_level": student.school_level, "is_new": True}}


# ==================== 2. 保存作业批改结果到数据库 ====================

@router.post("/homework/save")
async def plugin_homework_save(request: Request, db: Session = Depends(get_db)):
    """
    [插件] 保存作业批改结果到数据库
    传入 student_id, photo_url, extracted_text, score, correct_count, total_count, comments, wrong_questions
    """
    body = await _parse_body(request)
    student_id = int(_g(body, "student_id", 0))
    if not student_id:
        raise HTTPException(status_code=422, detail="student_id is required")

    submission = HomeworkSubmission(
        student_id=student_id,
        photo_url=_g(body, "photo_url", ""),
        extracted_text=_g(body, "extracted_text", ""),
        student_answers=_g(body, "student_answers", ""),
        correct_count=int(_g(body, "correct_count", 0)),
        total_count=int(_g(body, "total_count", 0)),
        score=float(_g(body, "score", 0)),
        comments=_g(body, "comments", ""),
        wrong_questions=_g(body, "wrong_questions", []),
        status="done",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # 记录活动日志
    ActivityLog(student_id=student_id, activity_type="homework",
                detail=json.dumps({"submission_id": submission.id, "score": submission.score}, ensure_ascii=False))
    db.commit()

    # 如果是错题，更新错题记录
    wrong_list = submission.wrong_questions or []
    for w in wrong_list:
        if not w.get("correct", True):
            kp = normalize_knowledge_point(w.get("question", "未知知识点"))
            existing = db.query(ErrorRecord).filter(
                ErrorRecord.student_id == student_id,
                ErrorRecord.knowledge_point == kp,
            ).first()
            if existing:
                existing.error_count += 1
                existing.last_error_date = datetime.now(timezone.utc)
            else:
                db.add(ErrorRecord(
                    student_id=student_id,
                    knowledge_point=kp,
                    question_text=w.get("question", ""),
                    student_answer=w.get("student_answer", ""),
                    correct_answer=w.get("correct_answer", ""),
                ))
    db.commit()

    return {"success": True, "data": {"id": submission.id, "status": "saved"}}


# ==================== 3. 保存考试结果到数据库 ====================

@router.post("/exam/save")
async def plugin_exam_save(request: Request, db: Session = Depends(get_db)):
    """
    [插件] 保存考试结果到数据库
    传入 student_id, questions, answers, score, diagnostic_report, learning_plan
    """
    body = await _parse_body(request)
    student_id = int(_g(body, "student_id", 0))
    if not student_id:
        raise HTTPException(status_code=422, detail="student_id is required")

    exam = ExamAttempt(
        student_id=student_id,
        exam_config_json=_g(body, "config", {}),
        questions_json=_g(body, "questions", []),
        student_answers=_g(body, "answers", []),
        score=float(_g(body, "score", 0)),
        diagnostic_report=_g(body, "diagnostic_report", {}),
        learning_plan=_g(body, "learning_plan", []),
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    ActivityLog(student_id=student_id, activity_type="exam",
                detail=json.dumps({"exam_id": exam.id, "score": exam.score}, ensure_ascii=False))
    db.commit()

    return {"success": True, "data": {"id": exam.id, "status": "saved"}}


# ==================== 4. 教师端：学生错题汇总 ====================

@router.get("/teacher/error-summary")
async def plugin_teacher_error_summary(
    db: Session = Depends(get_db),
    knowledge_point: str = Query(None, description="按知识点筛选（可选）"),
):
    """
    [插件] 教师端错题汇总
    按知识点统计全班错误率，返回每个知识点的错误学生数
    """
    query = db.query(
        ErrorRecord.knowledge_point,
        func.count(ErrorRecord.id).label("affected_students"),
        func.sum(ErrorRecord.error_count).label("total_errors"),
    ).group_by(ErrorRecord.knowledge_point)

    if knowledge_point:
        query = query.filter(ErrorRecord.knowledge_point == knowledge_point)

    results = query.order_by(func.sum(ErrorRecord.error_count).desc()).all()
    total_students = db.query(func.count(Student.id)).scalar() or 1

    return {
        "success": True,
        "data": [{
            "knowledge_point": r.knowledge_point,
            "error_count": r.total_errors,
            "affected_students": r.affected_students,
            "error_rate": round(r.affected_students / total_students * 100, 1),
        } for r in results]
    }


# ==================== 5. 教师端：学生排行（按错题数） ====================

@router.get("/teacher/student-ranking")
async def plugin_teacher_student_ranking(
    db: Session = Depends(get_db),
    limit: int = Query(10, description="返回人数"),
):
    """
    [插件] 教师端学生错题排行
    返回错题最多的学生列表，含姓名和薄弱知识点数
    """
    results = db.query(
        ErrorRecord.student_id,
        func.sum(ErrorRecord.error_count).label("total_errors"),
        func.count(ErrorRecord.knowledge_point).label("weak_points"),
    ).group_by(ErrorRecord.student_id).order_by(
        func.sum(ErrorRecord.error_count).desc()
    ).limit(limit).all()

    students = []
    for r in results:
        student = db.query(Student).get(r.student_id)
        students.append({
            "student_id": r.student_id,
            "name": student.name if student else "未知",
            "total_errors": r.total_errors,
            "weak_points_count": r.weak_points,
        })

    return {"success": True, "data": students}


# ==================== 6. 查看学生个人信息（含全部记录） ====================

@router.get("/student/{student_id}/profile")
async def plugin_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
):
    """[插件] 学生学习画像"""
    student = db.query(Student).get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    homework_count = db.query(func.count(HomeworkSubmission.id)).filter(
        HomeworkSubmission.student_id == student_id).scalar() or 0
    exam_count = db.query(func.count(ExamAttempt.id)).filter(
        ExamAttempt.student_id == student_id).scalar() or 0
    avg_hw = db.query(func.avg(HomeworkSubmission.score)).filter(
        HomeworkSubmission.student_id == student_id).scalar() or 0
    avg_exam = db.query(func.avg(ExamAttempt.score)).filter(
        ExamAttempt.student_id == student_id).scalar() or 0
    avg_score = float((avg_hw + avg_exam) / 2) if avg_hw and avg_exam else float(avg_hw or avg_exam or 0)

    # 薄弱知识点
    errors = db.query(ErrorRecord).filter(
        ErrorRecord.student_id == student_id
    ).order_by(ErrorRecord.error_count.desc()).all()

    return {
        "success": True,
        "data": {
            "id": student.id,
            "name": student.name,
            "student_id": student.student_id,
            "level": student.school_level,
            "homework_count": homework_count,
            "exam_count": exam_count,
            "avg_score": round(avg_score, 1),
            "weak_points": [{"point": e.knowledge_point, "count": e.error_count} for e in errors[:10]],
        }
    }


# ==================== 7. 查询学生错题详情 ====================

@router.get("/student/{student_id}/errors")
async def plugin_student_errors(
    student_id: int,
    db: Session = Depends(get_db),
):
    """[插件] 查看学生错题详情"""
    errors = db.query(ErrorRecord).filter(
        ErrorRecord.student_id == student_id
    ).order_by(ErrorRecord.error_count.desc()).all()

    return {
        "success": True,
        "data": [{
            "knowledge_point": e.knowledge_point,
            "question": e.question_text,
            "student_answer": e.student_answer,
            "correct_answer": e.correct_answer,
            "error_count": e.error_count,
        } for e in errors]
    }


# ==================== 原有的 OCR / 出题 / 批改等接口保持不变 ====================

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
