"""
作业路由 — 上传（异步批改）、查询批改结果
"""
import asyncio
import os
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from models import Student, HomeworkSubmission, GradingTask
from services.grading_service import process_homework as do_grading
from config import settings
from utils.auth import require_student

logger = logging.getLogger(__name__)
router = APIRouter()


async def _run_grading_background(db: Session, grading_task_id: int):
    """后台执行批改（在事件循环中不阻塞 HTTP）"""
    task = db.query(GradingTask).get(grading_task_id)
    if not task:
        return

    try:
        task.status = "processing"
        db.commit()

        # 新建一个独立 DB session 做耗时操作，不占用请求 session
        bg_db = SessionLocal()
        try:
            submission = bg_db.query(HomeworkSubmission).get(task.submission_id)
            if submission:
                result = await do_grading(bg_db, task.student_id, submission.photo_url, "")
                task.result_json = {
                    "score": result.score,
                    "correct_count": result.correct_count,
                    "total_count": result.total_count,
                    "comments": result.comments,
                    "wrong_questions": result.wrong_questions or [],
                }
                task.status = "done"
                bg_db.commit()
        except Exception as e:
            bg_db.rollback()
            task.status = "error"
            task.error_message = str(e)
            bg_db.commit()
        finally:
            bg_db.close()

        # 主 session 同步状态
        task_refetch = db.query(GradingTask).get(grading_task_id)
        if task_refetch:
            task_refetch.status = task.status
            task_refetch.result_json = task.result_json
            task_refetch.error_message = task.error_message
            task_refetch.completed_at = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        logger.error(f"后台批改失败: {e}")
        task.status = "error"
        task.error_message = str(e)
        db.commit()


@router.post("/upload")
async def upload_homework(
    file: UploadFile = File(...),
    student_answers: str = "",
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """上传作业照片 → 立即返回 task_id，后台异步批改"""
    student_id = current_user[0].id
    student = db.query(Student).get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 保存图片
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    # 创建作业记录（初始状态为 pending）
    submission = HomeworkSubmission(
        student_id=student_id,
        photo_url=f"/uploads/{filename}",
        student_answers=student_answers,
        status="pending",
    )
    db.add(submission)
    db.flush()

    # 创建批改任务
    grading_task = GradingTask(
        student_id=student_id,
        submission_id=submission.id,
        task_type="homework",
        status="pending",
    )
    db.add(grading_task)
    db.commit()
    db.refresh(grading_task)
    db.refresh(submission)

    # 后台启动异步批改
    asyncio.create_task(_run_grading_background(SessionLocal(), grading_task.id))

    return {
        "task_id": grading_task.id,
        "submission_id": submission.id,
        "status": "pending",
        "message": "作业已上传，正在批改中",
    }


@router.get("/upload/{submission_id}/status")
async def get_grading_status(
    submission_id: int,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """轮询批改进度"""
    student_id = current_user[0].id
    submission = db.query(HomeworkSubmission).filter(
        HomeworkSubmission.id == submission_id,
        HomeworkSubmission.student_id == student_id,
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="作业不存在")

    task = db.query(GradingTask).filter(
        GradingTask.submission_id == submission_id,
    ).first()

    if not task:
        return {"status": submission.status, "done": submission.status == "done"}

    if task.status == "done" and task.result_json:
        submission.score = task.result_json.get("score", 0)
        submission.correct_count = task.result_json.get("correct_count", 0)
        submission.total_count = task.result_json.get("total_count", 0)
        submission.comments = task.result_json.get("comments", "")
        submission.wrong_questions_json = task.result_json.get("wrong_questions", [])
        submission.status = "done"
        db.commit()

        return {
            "status": "done",
            "result": task.result_json,
            "submission_id": submission.id,
        }
    elif task.status == "error":
        submission.status = "error"
        db.commit()
        return {"status": "error", "error": task.error_message}
    else:
        return {"status": "processing", "done": False}


@router.get("/my")
async def my_homework(
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取我的作业列表"""
    student_id = current_user[0].id
    submissions = (
        db.query(HomeworkSubmission)
        .filter(HomeworkSubmission.student_id == student_id)
        .order_by(HomeworkSubmission.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "photo_url": s.photo_url,
            "score": s.score,
            "correct_count": s.correct_count,
            "total_count": s.total_count,
            "comments": s.comments,
            "status": s.status,
            "created_at": s.created_at.isoformat(),
        }
        for s in submissions
    ]


@router.get("/{submission_id}/result")
async def homework_result(
    submission_id: int,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """获取批改详情"""
    student_id = current_user[0].id
    submission = (
        db.query(HomeworkSubmission)
        .filter(
            HomeworkSubmission.id == submission_id,
            HomeworkSubmission.student_id == student_id,
        )
        .first()
    )
    if not submission:
        raise HTTPException(status_code=404, detail="作业不存在")

    return {
        "id": submission.id,
        "photo_url": submission.photo_url,
        "score": submission.score,
        "correct_count": submission.correct_count,
        "total_count": submission.total_count,
        "comments": submission.comments,
        "wrong_questions": submission.wrong_questions or [],
        "status": submission.status,
        "created_at": submission.created_at.isoformat(),
    }
