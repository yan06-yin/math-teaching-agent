"""
批改服务 — 直接使用 AI 多模态识别图片并批改
"""
import base64
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models import HomeworkSubmission, ErrorRecord
from services.open_model_service import open_model_service
from utils.knowledge_mapper import normalize_knowledge_point

logger = logging.getLogger(__name__)


def ensure_upload_dir():
    """确保上传目录存在（惰性初始化，避免 import 时权限问题）"""
    try:
        Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.warning(f"无法创建上传目录: {e}")
        alt_dir = Path("uploads")
        alt_dir.mkdir(parents=True, exist_ok=True)
        if alt_dir.exists():
            settings.UPLOAD_DIR = str(alt_dir.resolve())
            logger.info(f"回退到上传目录: {settings.UPLOAD_DIR}")


async def process_homework(db: Session, student_id: int, photo_path: str,
                           student_answers: str = "") -> HomeworkSubmission:
    """完整作业批改流程"""
    ensure_upload_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"homework_{student_id}_{timestamp}.jpg"
    dest_path = Path(settings.UPLOAD_DIR) / filename

    if photo_path.startswith(("http://", "https://")):
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(photo_path)
            resp.raise_for_status()
            dest_path.write_bytes(resp.content)
    else:
        import shutil
        shutil.copy2(photo_path, dest_path)

    photo_url = f"/uploads/{filename}"

    image_base64 = ""
    try:
        with open(dest_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"读取图片失败: {e}")

    submission = HomeworkSubmission(
        student_id=student_id,
        photo_url=photo_url,
        extracted_text="",
        student_answers=student_answers,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    try:
        from models import Student
        student = db.get(Student, student_id)
        school_level = student.school_level if student else "初中"
        student_name = student.name if student else f"学生{student_id}"

        result = await open_model_service.grade_homework_with_image(
            student_name=student_name,
            school_level=school_level,
            image_base64=image_base64,
        )

        submission.score = float(result.get("score", 0))
        submission.correct_count = int(result.get("correct_count", 0))
        submission.total_count = int(result.get("total_count", 0))
        submission.comments = result.get("comments", "")
        submission.wrong_questions = result.get("details", [])
        db.commit()

        for wrong in submission.wrong_questions or []:
            if not wrong.get("correct", True):
                kp = normalize_knowledge_point(wrong.get("question", "未知知识点"))
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
                        question_text=wrong.get("question", ""),
                        student_answer=wrong.get("student_answer", ""),
                        correct_answer=wrong.get("correct_answer", ""),
                    ))
                db.commit()
    except Exception as e:
        logger.error(f"AI 批改失败: {e}")
        submission.comments = f"批改失败: {str(e)}"
        db.commit()

    db.refresh(submission)
    return submission
