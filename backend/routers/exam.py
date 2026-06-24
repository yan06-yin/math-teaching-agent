"""
考试路由 — 生成试卷（异步）、提交答卷、轮询结果
使用异步 SQLAlchemy
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, AsyncSessionLocal
from models import Student, ExamAttempt, GradingTask
from schemas import ExamGenerateConfig, ExamSubmit
from services.exam_service import generate_and_save_exam, grade_exam
from utils.auth import require_student

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_exam_generate_background(task_id: int, exam_id: int, exam_config: dict):
    """后台生成试卷"""
    async with AsyncSessionLocal() as bg_db:
        try:
            exam = await bg_db.get(ExamAttempt, exam_id)
            if exam and not exam.questions_json:
                result = await generate_and_save_exam(bg_db, exam.student_id, exam_config, exam_id)
                task = await bg_db.get(GradingTask, task_id)
                if task:
                    task.status = "done"
                    task.result_json = {"exam_id": result.id, "questions": result.questions_json}
                    task.completed_at = datetime.now(timezone.utc)
                    await bg_db.commit()
        except Exception as e:
            try:
                await bg_db.rollback()
            except Exception:
                pass
            try:
                task = await bg_db.get(GradingTask, task_id)
                if task:
                    task.status = "error"
                    task.error_message = str(e)
                    await bg_db.commit()
            except Exception:
                pass
            logger.error(f"后台出题失败: {e}")


async def _run_exam_grading_background(grading_task_id: int, exam_id: int, answers: list[dict]):
    """后台执行考试批改"""
    async with AsyncSessionLocal() as bg_db:
        try:
            task = await bg_db.get(GradingTask, grading_task_id)
            if task:
                task.status = "processing"
                await bg_db.commit()

            graded, details = await grade_exam(bg_db, exam_id, answers)
            task = await bg_db.get(GradingTask, grading_task_id)
            if task:
                task.status = "done"
                task.result_json = {
                    "exam_id": graded.id, "score": graded.score,
                    "questions": graded.questions_json, "details": details,
                    "student_answers": graded.student_answers,
                    "diagnostic_report": graded.diagnostic_report,
                    "learning_plan": graded.learning_plan,
                }
                task.completed_at = datetime.now(timezone.utc)
                await bg_db.commit()
        except Exception as e:
            try:
                await bg_db.rollback()
            except Exception:
                pass
            try:
                task = await bg_db.get(GradingTask, grading_task_id)
                if task:
                    task.status = "error"
                    task.error_message = str(e)
                    await bg_db.commit()
            except Exception:
                pass
            logger.error(f"后台考试批改失败: {e}")


@router.post("/generate")
async def generate_exam(
    config: ExamGenerateConfig,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """根据学生情况生成试卷 — 返回 task_id，后台异步出题"""
    student_id = current_user[0].id
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    exam_config = {**config.model_dump(), "school_level": student.school_level}

    exam = ExamAttempt(
        student_id=student_id,
        exam_config_json=exam_config,
        questions_json=[],
        student_answers=[],
        status="draft",
    )
    db.add(exam)
    await db.flush()

    task = GradingTask(
        student_id=student_id,
        task_type="exam_generate",
        status="processing",
        submission_id=exam.id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await db.refresh(exam)

    asyncio.create_task(_run_exam_generate_background(task.id, exam.id, exam_config))

    return {"task_id": task.id, "exam_id": exam.id, "status": "generating", "message": "试卷正在生成中"}


@router.get("/generate/{exam_id}/status")
async def get_exam_generate_status(
    exam_id: int,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    student_id = current_user[0].id
    task = (await db.execute(
        select(GradingTask).filter(
            GradingTask.task_type == "exam_generate",
            GradingTask.student_id == student_id,
            GradingTask.submission_id == exam_id,
        ).order_by(GradingTask.created_at.desc())
    )).scalars().first()

    exam = (await db.execute(
        select(ExamAttempt).filter(
            ExamAttempt.id == exam_id,
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    if exam.questions_json:
        return {"status": "done", "exam_id": exam.id, "questions": exam.questions_json}

    if task and task.status == "error":
        return {"status": "error", "error": task.error_message}

    return {"status": "generating", "exam_id": exam.id}


@router.post("/{exam_id}/submit")
async def submit_exam(
    exam_id: int,
    body: ExamSubmit,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    student_id = current_user[0].id

    exam = await db.get(ExamAttempt, exam_id)
    if not exam or exam.student_id != student_id:
        raise HTTPException(status_code=404, detail="考试不存在")

    existing_task = (await db.execute(
        select(GradingTask).filter(GradingTask.submission_id == exam_id, GradingTask.task_type == "exam_grade")
    )).scalars().first()
    if existing_task:
        raise HTTPException(status_code=400, detail="该考试已提交过，不能重复提交")

    exam.student_answers = body.answers
    exam.status = "submitted"
    await db.commit()

    task = GradingTask(
        student_id=student_id,
        task_type="exam_grade",
        status="pending",
        submission_id=exam_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    asyncio.create_task(_run_exam_grading_background(task.id, exam_id, body.answers))

    return {"task_id": task.id, "exam_id": exam.id, "status": "grading", "message": "答案已提交，正在批改中"}


@router.get("/{exam_id}/status")
async def get_exam_status(
    exam_id: int,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    student_id = current_user[0].id

    exam = (await db.execute(
        select(ExamAttempt).filter(
            ExamAttempt.id == exam_id,
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    task = (await db.execute(
        select(GradingTask).filter(
            GradingTask.submission_id == exam_id,
            GradingTask.task_type == "exam_grade",
            GradingTask.student_id == student_id,
        ).order_by(GradingTask.created_at.desc())
    )).scalars().first()

    if task and task.status == "done":
        if task.result_json:
            exam.score = task.result_json.get("score", exam.score)
            exam.student_answers = task.result_json.get("student_answers", exam.student_answers)
            if task.result_json.get("diagnostic_report"):
                exam.diagnostic_report = task.result_json["diagnostic_report"]
            if task.result_json.get("learning_plan"):
                exam.learning_plan = task.result_json["learning_plan"]
        return {
            "status": "done",
            "exam_id": task.result_json.get("exam_id") if task.result_json else exam.id,
            "score": task.result_json.get("score") if task.result_json else exam.score,
            "questions": task.result_json.get("questions") if task.result_json else exam.questions_json,
            "student_answers": task.result_json.get("student_answers") if task.result_json else exam.student_answers,
            "details": task.result_json.get("details") or exam.details_json or [],
            "diagnostic_report": task.result_json.get("diagnostic_report", {}) if task.result_json else {},
            "learning_plan": task.result_json.get("learning_plan", []) if task.result_json else [],
            "created_at": exam.created_at.isoformat() if exam.created_at else None,
        }
    elif task and task.status == "error":
        return {"status": "error", "error": task.error_message}

    if exam.score is not None and hasattr(exam, 'student_answers') and exam.student_answers:
        return {
            "status": "done", "exam_id": exam.id, "score": exam.score,
            "questions": exam.questions_json, "student_answers": exam.student_answers,
            "details": exam.details_json or [], "diagnostic_report": exam.diagnostic_report or {},
            "learning_plan": exam.learning_plan or [], "created_at": exam.created_at.isoformat() if exam.created_at else None,
        }

    return {"status": "grading", "exam_id": exam.id}


@router.get("/{exam_id}/report")
async def get_exam_report(
    exam_id: int,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    student_id = current_user[0].id
    exam = (await db.execute(
        select(ExamAttempt).filter(
            ExamAttempt.id == exam_id,
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_deleted == False,
        )
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")
    return {
        "id": exam.id, "score": exam.score, "questions": exam.questions_json,
        "student_answers": exam.student_answers, "details": exam.details_json or [],
        "diagnostic_report": exam.diagnostic_report, "learning_plan": exam.learning_plan,
        "created_at": exam.created_at.isoformat() if exam.created_at else None,
    }


@router.get("/my")
async def my_exams(
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
):
    student_id = current_user[0].id
    exams = (await db.execute(
        select(ExamAttempt)
        .filter(ExamAttempt.student_id == student_id, ExamAttempt.is_deleted == False)
        .order_by(ExamAttempt.created_at.desc())
        .limit(limit)
    )).scalars().all()
    return [{"id": e.id, "score": e.score, "questions_count": len(e.questions_json) if e.questions_json else 0, "created_at": e.created_at.isoformat() if e.created_at else None} for e in exams]
