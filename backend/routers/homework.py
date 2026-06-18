"""
作业路由 — 上传、查询批改结果
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from database import get_db
from models import Student, HomeworkSubmission
from schemas import HomeworkResult
from services.grading_service import process_homework
from config import settings
import os
import uuid

router = APIRouter()


@router.post("/upload")
async def upload_homework(
    file: UploadFile = File(...),
    student_answers: str = "",
    student_id: int = Depends(lambda: 1),  # TODO: JWT 鉴权
    db: Session = Depends(get_db),
):
    """上传作业照片，触发自动批改"""
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

    # 异步批改
    submission = await process_homework(db, student_id, filepath, student_answers)

    return {
        "id": submission.id,
        "photo_url": submission.photo_url,
        "score": submission.score,
        "correct_count": submission.correct_count,
        "total_count": submission.total_count,
        "comments": submission.comments,
        "wrong_questions": submission.wrong_questions or [],
        "status": submission.status,
    }


@router.get("/my")
async def my_homework(
    student_id: int = Depends(lambda: 1),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    """获取我的作业列表"""
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
    student_id: int = Depends(lambda: 1),
    db: Session = Depends(get_db),
):
    """获取批改详情"""
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
