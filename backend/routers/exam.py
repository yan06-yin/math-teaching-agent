"""
考试路由 — 生成试卷、提交答卷、查看报告
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Student, ExamAttempt
from schemas import ExamGenerateConfig, ExamSubmit
from services.exam_service import generate_and_save_exam, grade_exam
from utils.auth import require_student

router = APIRouter()


@router.post("/generate")
async def generate_exam(
    config: ExamGenerateConfig,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """根据学生情况生成试卷"""
    student_id = current_user[0].id
    student = db.query(Student).get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    exam_config = {
        **config.model_dump(),
        "school_level": student.school_level,
    }

    try:
        exam = await generate_and_save_exam(db, student_id, exam_config)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"出题失败: {str(e)}")

    return {
        "id": exam.id,
        "questions": exam.questions_json,
    }


@router.post("/{exam_id}/submit")
async def submit_exam(
    exam_id: int,
    body: ExamSubmit,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """提交答卷 — 保存答案，返回状态"""
    student_id = current_user[0].id

    exam = db.query(ExamAttempt).get(exam_id)
    if not exam or exam.student_id != student_id:
        raise HTTPException(status_code=404, detail="考试不存在")

    exam.student_answers = body.answers
    db.commit()

    return {
        "id": exam.id,
        "status": "grading",
        "message": "答案已保存",
    }


@router.get("/{exam_id}/status")
async def get_exam_status(
    exam_id: int,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """查看/触发考试批改"""
    student_id = current_user[0].id

    exam = db.query(ExamAttempt).filter(
        ExamAttempt.id == exam_id,
        ExamAttempt.student_id == student_id,
    ).first()

    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    # 已有结果
    if exam.score is not None and exam.score > 0:
        return {
            "id": exam.id,
            "status": "done",
            "score": exam.score,
            "questions": exam.questions_json,
            "student_answers": exam.student_answers,
            "diagnostic_report": exam.diagnostic_report or {},
            "learning_plan": exam.learning_plan or [],
            "created_at": exam.created_at.isoformat() if exam.created_at else None,
        }

    # 还没批改，触发批改
    try:
        graded = await grade_exam(db, exam_id, exam.student_answers or [])
        return {
            "id": graded.id,
            "status": "done",
            "score": graded.score,
            "questions": graded.questions_json,
            "student_answers": graded.student_answers,
            "diagnostic_report": graded.diagnostic_report or {},
            "learning_plan": graded.learning_plan or [],
            "created_at": graded.created_at.isoformat() if graded.created_at else None,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "id": exam.id,
            "status": "grading",
            "score": None,
            "questions": exam.questions_json,
            "student_answers": exam.student_answers,
            "diagnostic_report": {},
            "learning_plan": [],
            "created_at": exam.created_at.isoformat() if exam.created_at else None,
        }


@router.get("/{exam_id}/report")
async def get_exam_report(
    exam_id: int,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """获取考试报告和诊断"""
    student_id = current_user[0].id

    exam = db.query(ExamAttempt).filter(
        ExamAttempt.id == exam_id,
        ExamAttempt.student_id == student_id,
    ).first()

    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    return {
        "id": exam.id,
        "score": exam.score,
        "questions": exam.questions_json,
        "student_answers": exam.student_answers,
        "diagnostic_report": exam.diagnostic_report,
        "learning_plan": exam.learning_plan,
        "created_at": exam.created_at.isoformat() if exam.created_at else None,
    }


@router.get("/my")
async def my_exams(
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
    limit: int = 20,
):
    """获取我的考试记录"""
    student_id = current_user[0].id

    exams = (
        db.query(ExamAttempt)
        .filter(ExamAttempt.student_id == student_id)
        .order_by(ExamAttempt.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id,
            "score": e.score,
            "questions_count": len(e.questions_json) if e.questions_json else 0,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in exams
    ]
