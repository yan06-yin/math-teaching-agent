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
from models import Student, HomeworkSubmission, GradingTask, ErrorRecord
from config import settings
from utils.auth import require_student

logger = logging.getLogger(__name__)
router = APIRouter()


def _read_file_base64(filepath: str) -> str:
    """同步读取文件并返回 base64 编码（供 run_in_executor 使用）"""
    import base64
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def _run_grading_background(grading_task_id: int):
    """后台执行批改（使用独立 session，不依赖 HTTP 请求）"""
    bg_db = SessionLocal()
    try:
        task = bg_db.get(GradingTask, grading_task_id)
        if not task:
            return

        task.status = "processing"
        bg_db.commit()

        submission = bg_db.get(HomeworkSubmission, task.submission_id)
        if submission:
            # 直接调用 AI 批改，不再走 process_homework（process_homework 会重复创建记录）
            from models import Student
            import base64
            student = bg_db.get(Student, task.student_id)
            school_level = student.school_level if student else "初中"
            student_name = student.name if student else f"学生{task.student_id}"

            # 读取图片转为 base64（文件 I/O 用线程池避免阻塞事件循环）
            photo_local_path = submission.photo_url
            if photo_local_path.startswith("/uploads/"):
                photo_local_path = os.path.join(settings.UPLOAD_DIR, os.path.basename(photo_local_path))

            image_base64 = ""
            try:
                loop = asyncio.get_event_loop()
                image_base64 = await loop.run_in_executor(None, _read_file_base64, photo_local_path)
            except Exception as e:
                logger.error(f"读取图片失败: {e}")

            # 调用 AI 多模态批改（优先使用活跃的模型，如果是 DeepSeek 不支持多模态则回退到文本）
            from services.open_model_service import open_model_service

            # 检查当前模型是否支持多模态（DeepSeek V4 Flash 不支持图片）
            current_model = open_model_service.model.lower()
            supports_vision = "agnes" in current_model or "gpt" in current_model or "claude" in current_model or "gemini" in current_model or "qwen" in current_model

            if supports_vision:
                result = await open_model_service.grade_homework_with_image(
                    student_name=student_name,
                    school_level=school_level,
                    image_base64=image_base64,
                )
            else:
                # DeepSeek 等不支持图片的模型，用文本方式批改
                result = await open_model_service.grade_homework(
                    student_name=student_name,
                    school_level=school_level,
                    questions_and_answers=f"学生作业图片已上传。请根据以下信息批改：\n学生：{student_name}\n学段：{school_level}\n(图片内容无法直接识别，请给出一般性评语)",
                )

            # 更新已有 submission 记录（不新建）
            submission.score = float(result.get("score", 0))
            submission.correct_count = int(result.get("correct_count", 0))
            submission.total_count = int(result.get("total_count", 0))
            submission.comments = result.get("comments", "")
            submission.wrong_questions_json = result.get("details", [])
            submission.status = "done"
            bg_db.commit()

            # 更新错题记录
            from datetime import datetime, timezone
            from utils.knowledge_mapper import normalize_knowledge_point
            for wrong in (result.get("details") or []):
                if not wrong.get("correct", True):
                    kp = normalize_knowledge_point(wrong.get("question", "未知知识点"))
                    existing = bg_db.query(ErrorRecord).filter(
                        ErrorRecord.student_id == task.student_id,
                        ErrorRecord.knowledge_point == kp,
                    ).first()
                    if existing:
                        existing.error_count += 1
                        existing.last_error_date = datetime.now(timezone.utc)
                    else:
                        bg_db.add(ErrorRecord(
                            student_id=task.student_id,
                            knowledge_point=kp,
                            question_text=wrong.get("question", ""),
                            student_answer=wrong.get("student_answer", ""),
                            correct_answer=wrong.get("correct_answer", ""),
                        ))
            bg_db.commit()

            task.result_json = {
                "score": result.get("score", 0),
                "correct_count": result.get("correct_count", 0),
                "total_count": result.get("total_count", 0),
                "comments": result.get("comments", ""),
                "wrong_questions": result.get("details") or [],
            }
            task.status = "done"
            task.completed_at = datetime.now(timezone.utc)
            bg_db.commit()
    except Exception as e:
        bg_db.rollback()
        logger.error(f"后台批改失败: {e}")
        task = bg_db.get(GradingTask, grading_task_id)
        if task:
            task.status = "error"
            task.error_message = str(e)
            if task.submission_id:
                subm = bg_db.get(HomeworkSubmission, task.submission_id)
                if subm:
                    subm.status = "error"
            bg_db.commit()
    finally:
        bg_db.close()


@router.post("/upload")
async def upload_homework(
    file: UploadFile = File(...),
    student_answers: str = "",
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """上传作业照片 → 立即返回 task_id，后台异步批改"""
    student_id = current_user[0].id
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 保存图片
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
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
    asyncio.create_task(_run_grading_background(grading_task.id))

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
        HomeworkSubmission.is_deleted == False,
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
        .filter(HomeworkSubmission.student_id == student_id, HomeworkSubmission.is_deleted == False)
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
            HomeworkSubmission.is_deleted == False,
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
