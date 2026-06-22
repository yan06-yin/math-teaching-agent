"""
考试路由 — 生成试卷（异步）、提交答卷、轮询结果
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import Student, ExamAttempt, GradingTask
from schemas import ExamGenerateConfig, ExamSubmit
from services.exam_service import generate_and_save_exam, grade_exam
from utils.auth import require_student
import traceback

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_exam_grading_background(grading_task_id: int, exam_id: int, answers: list[dict]):
    """后台执行考试批改（使用独立连接，不依赖请求 session）"""
    bg_db = SessionLocal()
    try:
        task = bg_db.query(GradingTask).get(grading_task_id)
        if task:
            task.status = "processing"
            bg_db.commit()

        graded, details = await grade_exam(bg_db, exam_id, answers)
        task = bg_db.query(GradingTask).get(grading_task_id)
        if task:
            task.status = "done"
            task.result_json = {
                "exam_id": graded.id,
                "score": graded.score,
                "questions": graded.questions_json,
                "details": details,
                "student_answers": graded.student_answers,
                "diagnostic_report": graded.diagnostic_report,
                "learning_plan": graded.learning_plan,
            }
            task.completed_at = datetime.now(timezone.utc)
            bg_db.commit()
    except Exception as e:
        try:
            bg_db.rollback()
        except:
            pass
        logger.error(f"后台考试批改失败: {e}")
        try:
            task = bg_db.query(GradingTask).get(grading_task_id)
            if task:
                task.status = "error"
                task.error_message = str(e)
                bg_db.commit()
        except:
            pass
        import traceback
        traceback.print_exc()
    finally:
        bg_db.close()


@router.post("/generate")
async def generate_exam(
    config: ExamGenerateConfig,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """根据学生情况生成试卷 — 返回 task_id，后台异步出题"""
    student_id = current_user[0].id
    student = db.query(Student).get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    exam_config = {
        **config.model_dump(),
        "school_level": student.school_level,
    }

    # 同步创建考试记录（空题目，稍后填充）
    exam = ExamAttempt(
        student_id=student_id,
        exam_config_json=exam_config,
        questions_json=[],
        student_answers=[],
    )
    db.add(exam)
    db.flush()

    # 创建出题任务
    task = GradingTask(
        student_id=student_id,
        task_type="exam_generate",
        status="processing",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    db.refresh(exam)

    # 后台异步生成试卷
    asyncio.create_task(_run_exam_generate_background(task.id, exam.id, exam_config))

    return {
        "task_id": task.id,
        "exam_id": exam.id,
        "status": "generating",
        "message": "试卷正在生成中",
    }


async def _run_exam_generate_background(task_id: int, exam_id: int, exam_config: dict):
    """后台生成试卷（使用独立 session，不依赖请求 session）"""
    bg_db = SessionLocal()
    try:
        exam = bg_db.query(ExamAttempt).get(exam_id)
        if exam and not exam.questions_json:
            result = await generate_and_save_exam(bg_db, exam.student_id, exam_config)
            # 更新任务
            task = bg_db.query(GradingTask).get(task_id)
            if task:
                task.status = "done"
                task.result_json = {"exam_id": result.id, "questions": result.questions_json}
                task.completed_at = datetime.now(timezone.utc)
                bg_db.commit()
    except Exception as e:
        try:
            bg_db.rollback()
        except:
            pass
        try:
            task = bg_db.query(GradingTask).get(task_id)
            if task:
                task.status = "error"
                task.error_message = str(e)
                bg_db.commit()
        except:
            pass
        logger.error(f"后台出题失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        bg_db.close()


@router.get("/generate/{exam_id}/status")
async def get_exam_generate_status(
    exam_id: int,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """轮询试卷生成状态"""
    student_id = current_user[0].id
    task = db.query(GradingTask).filter(
        GradingTask.task_type == "exam_generate",
        GradingTask.student_id == student_id,
    ).order_by(GradingTask.created_at.desc()).first()

    exam = db.query(ExamAttempt).filter(ExamAttempt.id == exam_id, ExamAttempt.student_id == student_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    if exam.questions_json:
        return {"status": "done", "exam_id": exam.id, "questions": exam.questions_json}

    if task and task.status == "error":
        return {"status": "error", "error": task.error_message}

    # Check all recent tasks for this student (not just 'exam_generate' type)
    all_tasks = db.query(GradingTask).filter(
        GradingTask.student_id == student_id,
    ).order_by(GradingTask.created_at.desc()).limit(5).all()
    for t in all_tasks:
        if t.status == "error" and t.error_message:
            return {"status": "error", "error": t.error_message}

    return {"status": "generating", "exam_id": exam.id}


@router.post("/{exam_id}/submit")
async def submit_exam(
    exam_id: int,
    body: ExamSubmit,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """提交答卷 — 保存答案，触发异步批改"""
    student_id = current_user[0].id

    exam = db.query(ExamAttempt).get(exam_id)
    if not exam or exam.student_id != student_id:
        raise HTTPException(status_code=404, detail="考试不存在")

    exam.student_answers = body.answers
    db.commit()

    # 创建批改任务
    task = GradingTask(
        student_id=student_id,
        task_type="exam_grade",
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 后台异步批改
    asyncio.create_task(_run_exam_grading_background(task.id, exam_id, body.answers))

    return {
        "task_id": task.id,
        "exam_id": exam.id,
        "status": "grading",
        "message": "答案已提交，正在批改中",
    }


@router.get("/{exam_id}/status")
async def get_exam_status(
    exam_id: int,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """查询考试批改状态"""
    student_id = current_user[0].id

    exam = db.query(ExamAttempt).filter(
        ExamAttempt.id == exam_id,
        ExamAttempt.student_id == student_id,
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试记录不存在")

    # 查找批改任务（优先通过任务判断状态）
    task = db.query(GradingTask).filter(
        GradingTask.task_type == "exam_grade",
        GradingTask.student_id == student_id,
    ).order_by(GradingTask.created_at.desc()).first()

    if task and task.status == "done":
        # 同步结果到 exam 记录
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
            "details": task.result_json.get("details", []) if task.result_json else [],
            "diagnostic_report": task.result_json.get("diagnostic_report", {}) if task.result_json else {},
            "learning_plan": task.result_json.get("learning_plan", []) if task.result_json else [],
            "created_at": exam.created_at.isoformat() if exam.created_at else None,
        }
    elif task and task.status == "error":
        return {"status": "error", "error": task.error_message}

    # 退路：如果已有分数（兼容旧数据），也返回 done
    if exam.score is not None and exam.score > 0:
        return {
            "status": "done",
            "exam_id": exam.id,
            "score": exam.score,
            "questions": exam.questions_json,
            "student_answers": exam.student_answers,
            "details": [],
            "diagnostic_report": exam.diagnostic_report or {},
            "learning_plan": exam.learning_plan or [],
            "created_at": exam.created_at.isoformat() if exam.created_at else None,
        }

    return {"status": "grading", "exam_id": exam.id}


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
