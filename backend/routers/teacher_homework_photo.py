"""
教师拍照上传作业路由 — 上传照片、AI 批改、查看结果
使用异步 SQLAlchemy
"""
import asyncio
import os
import uuid
import logging
import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, AsyncSessionLocal
from models import HomeworkPhoto, Class, ClassStudent, Student, ErrorRecord
from config import settings
from utils.auth import require_teacher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/homework-photo", tags=["教师拍照批改"])


def _read_file_base64(filepath: str) -> str:
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def _run_photo_grading(photo_id: int):
    """后台异步批改拍照作业"""
    async with AsyncSessionLocal() as bg_db:
        try:
            photo = await bg_db.get(HomeworkPhoto, photo_id)
            if not photo:
                return
            photo.status = "grading"
            await bg_db.commit()

            # 读取图片
            photo_path = photo.photo_url
            if photo_path.startswith("/uploads/"):
                photo_path = os.path.join(settings.UPLOAD_DIR, os.path.basename(photo_path))

            image_base64 = ""
            try:
                loop = asyncio.get_event_loop()
                image_base64 = await loop.run_in_executor(None, _read_file_base64, photo_path)
            except Exception as e:
                logger.error(f"读取图片失败: {e}")

            # 获取班级学生信息
            student_names = []
            if photo.class_id:
                members = (await bg_db.execute(
                    select(ClassStudent, Student)
                    .join(Student, ClassStudent.student_id == Student.id)
                    .filter(ClassStudent.class_id == photo.class_id)
                )).all()
                student_names = [stu.name for _, stu in members]

            from services.open_model_service import open_model_service
            current_model = open_model_service.model.lower()
            supports_vision = any(k in current_model for k in ["agnes", "gpt", "claude", "gemini", "qwen"])

            class_info = ""
            if photo.class_id:
                cls = await bg_db.get(Class, photo.class_id)
                if cls:
                    class_info = f"班级：{cls.name}（{cls.school_level}）"
                    if student_names:
                        class_info += f"\n学生名单：{', '.join(student_names[:30])}"

            if supports_vision and image_base64:
                result = await open_model_service.grade_homework_with_image(
                    student_name=student_names[0] if student_names else "全班",
                    school_level="初中",
                    image_base64=image_base64,
                    extra_context=class_info,
                )
            else:
                prompt = f"请批改以下作业照片。\n{class_info}\n请识别题目并逐题批改。"
                result = await open_model_service.grade_homework(
                    student_name="全班",
                    school_level="初中",
                    questions_and_answers=prompt,
                )

            photo.score = float(result.get("score", 0))
            photo.correct_count = int(result.get("correct_count", 0))
            photo.total_count = int(result.get("total_count", 0))
            photo.comments = result.get("comments", "")
            photo.wrong_questions_json = result.get("details", [])
            photo.status = "done"
            photo.completed_at = datetime.now(timezone.utc)
            await bg_db.commit()

            # 如果有班级，将错题记录到班级学生
            if photo.class_id and photo.wrong_questions_json:
                from utils.knowledge_mapper import normalize_knowledge_point
                for wrong in photo.wrong_questions_json:
                    if not wrong.get("correct", True):
                        kp = normalize_knowledge_point(wrong.get("question", "未知知识点"))
                        # 记录到班级每个学生（简单策略）
                        for _, stu in members[:50]:
                            existing = (await bg_db.execute(
                                select(ErrorRecord).filter(
                                    ErrorRecord.student_id == stu.id,
                                    ErrorRecord.knowledge_point == kp,
                                )
                            )).scalar_one_or_none()
                            if existing:
                                existing.error_count += 1
                                existing.last_error_date = datetime.now(timezone.utc)
                            else:
                                bg_db.add(ErrorRecord(
                                    student_id=stu.id,
                                    knowledge_point=kp,
                                    question_text=wrong.get("question", "")[:200],
                                    student_answer=wrong.get("student_answer", ""),
                                    correct_answer=wrong.get("correct_answer", ""),
                                ))
                await bg_db.commit()

        except Exception as e:
            logger.error(f"拍照批改失败: {e}")
            try:
                photo = await bg_db.get(HomeworkPhoto, photo_id)
                if photo:
                    photo.status = "error"
                    photo.error_message = str(e)
                    await bg_db.commit()
            except Exception:
                pass


@router.post("/upload")
async def upload_homework_photo(
    file: UploadFile = File(...),
    title: str = Form("拍照批改"),
    class_id: int = Form(None),
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """教师上传作业照片 → 后台异步批改"""
    teacher = current_user[0]

    # 验证班级归属
    if class_id:
        cls = (await db.execute(
            select(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id)
        )).scalar_one_or_none()
        if not cls:
            raise HTTPException(status_code=404, detail="班级不存在或不属于你")

    # 保存文件
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"teacher_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # 创建记录
    photo = HomeworkPhoto(
        teacher_id=teacher.id,
        class_id=class_id,
        title=title,
        photo_url=f"/uploads/{filename}",
        status="pending",
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    # 后台批改
    asyncio.create_task(_run_photo_grading(photo.id))

    return {
        "id": photo.id,
        "status": "pending",
        "message": "照片已上传，AI 正在批改中",
    }


@router.get("/list")
async def list_homework_photos(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """教师查看拍照批改记录"""
    teacher_id = current_user[0].id
    photos = (await db.execute(
        select(HomeworkPhoto)
        .filter(HomeworkPhoto.teacher_id == teacher_id)
        .order_by(HomeworkPhoto.created_at.desc())
        .offset(offset).limit(limit)
    )).scalars().all()

    result = []
    for p in photos:
        class_name = None
        if p.class_id:
            cls = await db.get(Class, p.class_id)
            class_name = cls.name if cls else None
        result.append({
            "id": p.id, "title": p.title, "photo_url": p.photo_url,
            "score": p.score, "correct_count": p.correct_count,
            "total_count": p.total_count, "comments": p.comments,
            "status": p.status, "class_name": class_name,
            "created_at": p.created_at.isoformat(),
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        })
    return result


@router.get("/{photo_id}/status")
async def get_photo_grading_status(
    photo_id: int,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """轮询批改进度"""
    photo = await db.get(HomeworkPhoto, photo_id)
    if not photo or photo.teacher_id != current_user[0].id:
        raise HTTPException(status_code=404, detail="记录不存在")

    if photo.status == "done":
        return {
            "status": "done",
            "result": {
                "score": photo.score,
                "correct_count": photo.correct_count,
                "total_count": photo.total_count,
                "comments": photo.comments,
                "wrong_questions": photo.wrong_questions_json or [],
                "photo_url": photo.photo_url,
                "title": photo.title,
            },
        }
    elif photo.status == "error":
        return {"status": "error", "error": photo.error_message}
    else:
        return {"status": photo.status}


@router.get("/{photo_id}/result")
async def get_photo_result(
    photo_id: int,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """获取批改结果详情"""
    photo = await db.get(HomeworkPhoto, photo_id)
    if not photo or photo.teacher_id != current_user[0].id:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {
        "id": photo.id, "title": photo.title, "photo_url": photo.photo_url,
        "score": photo.score, "correct_count": photo.correct_count,
        "total_count": photo.total_count, "comments": photo.comments,
        "wrong_questions": photo.wrong_questions_json or [],
        "status": photo.status, "created_at": photo.created_at.isoformat(),
        "completed_at": photo.completed_at.isoformat() if photo.completed_at else None,
    }


@router.delete("/{photo_id}")
async def delete_homework_photo(
    photo_id: int,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """删除拍照批改记录"""
    photo = await db.get(HomeworkPhoto, photo_id)
    if not photo or photo.teacher_id != current_user[0].id:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.delete(photo)
    await db.commit()
    return {"message": "已删除"}
