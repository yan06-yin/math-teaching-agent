"""
批改服务 — 编排 OCR + Agnes AI 批改的完整流程
"""
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from models import HomeworkSubmission, ErrorRecord
from services.agnes_service import agences_service
from services.ocr_service import ocr_service
from utils.knowledge_mapper import normalize_knowledge_point

logger = logging.getLogger(__name__)
UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def process_homework(db: Session, student_id: int, photo_path: str,
                           student_answers: str = "") -> HomeworkSubmission:
    """
    完整作业批改流程：
    1. 保存照片
    2. OCR 提取文字
    3. 调用 Agnes AI 批改
    4. 存入数据库
    5. 更新错题记录
    """
    # Step 1: 保存照片
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"homework_{student_id}_{timestamp}.jpg"
    dest_path = UPLOAD_DIR / filename
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 如果是 URL，下载；如果是本地路径，复制
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

    # Step 2: OCR 提取文字
    extracted_text = ""
    try:
        extracted_text = ocr_service.extract_text(dest_path)
    except Exception as e:
        logger.warning(f"OCR 失败: {e}")

    # Step 3: 创建待批改记录
    submission = HomeworkSubmission(
        student_id=student_id,
        photo_url=photo_url,
        extracted_text=extracted_text,
        student_answers=student_answers,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Step 4: 调用 Agnes AI 批改
    try:
        # 组装作业内容
        content = extracted_text or student_answers
        if not content:
            content = "(图片无法识别，请手动输入题目)"

        # 获取学生信息
        from models import Student
        student = db.query(Student).get(student_id)
        school_level = student.school_level if student else "初中"
        student_name = student.name if student else f"学生{student_id}"

        result = await agences_service.grade_homework(
            student_name=student_name,
            school_level=school_level,
            questions_and_answers=content,
        )

        # Step 5: 更新批改结果
        submission.score = float(result.get("score", 0))
        submission.correct_count = int(result.get("correct_count", 0))
        submission.total_count = int(result.get("total_count", 0))
        submission.comments = result.get("comments", "")
        submission.wrong_questions = result.get("details", [])
        db.commit()

        # Step 6: 更新错题记录
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
        logger.error(f"Agnes AI 批改失败: {e}")
        submission.comments = f"批改失败: {str(e)}"
        db.commit()

    db.refresh(submission)
    return submission
