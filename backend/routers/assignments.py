"""
作业发布路由 — 支持文字作业和拍照作业
使用异步 SQLAlchemy
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database import get_db
from models import Assignment, AssignmentSubmission, Student, Class, ClassStudent
from utils.auth import require_teacher, require_student
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assignments", tags=["作业发布"])

# 上传文件大小上限（10MB）
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/teacher")
async def create_assignment(
    title: str = Form(...),
    description: str = Form(""),
    class_id: Optional[int] = Form(None),
    questions: str = Form("[]"),   # JSON 字符串
    photo: Optional[UploadFile] = File(None),  # 可选的照片
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """教师发布作业 — 支持文字题目和/或拍照"""
    import json
    teacher = current_user[0]

    if class_id:
        cls = (await db.execute(select(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id))).scalar_one_or_none()
        if not cls:
            raise HTTPException(status_code=404, detail="班级不存在或不属于你")

    # 解析题目 JSON
    try:
        questions_list = json.loads(questions) if questions else []
    except json.JSONDecodeError:
        questions_list = []

    # 处理照片上传（分块读取并校验大小，防止 OOM）
    photo_url = None
    if photo and photo.filename:
        ext = os.path.splitext(photo.filename)[1] or ".jpg"
        filename = f"hw_{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(settings.UPLOAD_DIR, filename)
        content = bytearray()
        while True:
            chunk = await photo.read(1024 * 1024)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"文件过大，最大支持 {MAX_UPLOAD_BYTES // (1024*1024)}MB")
        with open(filepath, "wb") as f:
            f.write(content)
        photo_url = f"/uploads/{filename}"

    assignment = Assignment(
        teacher_id=teacher.id,
        class_id=class_id,
        title=title,
        description=description,
        photo_url=photo_url,
        questions_json=questions_list,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return {
        "id": assignment.id,
        "title": assignment.title,
        "class_id": assignment.class_id,
        "photo_url": assignment.photo_url,
        "questions_count": len(assignment.questions_json),
        "created_at": assignment.created_at.isoformat(),
    }


@router.get("/teacher")
async def list_assignments(current_user=Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    teacher_id = current_user[0].id
    assignments = (await db.execute(select(Assignment).filter(Assignment.teacher_id == teacher_id).order_by(Assignment.created_at.desc()))).scalars().all()
    result = []
    for a in assignments:
        sub_count = (await db.execute(select(func.count(AssignmentSubmission.id)).filter(AssignmentSubmission.assignment_id == a.id))).scalar() or 0
        class_name = None
        if a.class_id:
            cls = await db.get(Class, a.class_id)
            class_name = cls.name if cls else None
        result.append({
            "id": a.id, "title": a.title, "description": a.description,
            "class_id": a.class_id, "class_name": class_name,
            "photo_url": a.photo_url,
            "questions_count": len(a.questions_json),
            "submissions": sub_count,
            "created_at": a.created_at.isoformat(),
        })
    return result


@router.get("/teacher/{assignment_id}/submissions")
async def view_submissions(assignment_id: int, current_user=Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    subs = (await db.execute(select(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment_id).order_by(AssignmentSubmission.submitted_at.desc()))).scalars().all()
    result = []
    for s in subs:
        student = await db.get(Student, s.student_id)
        result.append({"student_id": s.student_id, "student_name": student.name if student else "未知", "score": s.score, "answers": s.answers_json, "status": s.status, "submitted_at": s.submitted_at.isoformat()})
    return {"assignment": {"id": assignment.id, "title": assignment.title, "photo_url": assignment.photo_url, "questions": assignment.questions_json}, "submissions": result}


@router.get("/student")
async def student_assignments(current_user=Depends(require_student), db: AsyncSession = Depends(get_db)):
    student_id = current_user[0].id
    cs = (await db.execute(select(ClassStudent).filter(ClassStudent.student_id == student_id))).scalar_one_or_none()
    my_class_id = cs.class_id if cs else None

    # 在 SQL 层过滤：广播作业(class_id IS NULL)或本班作业，避免全表加载后 Python 过滤
    if my_class_id is not None:
        assignments = (await db.execute(
            select(Assignment)
            .filter(or_(Assignment.class_id == None, Assignment.class_id == my_class_id))
            .order_by(Assignment.created_at.desc())
        )).scalars().all()
    else:
        assignments = (await db.execute(
            select(Assignment).filter(Assignment.class_id == None).order_by(Assignment.created_at.desc())
        )).scalars().all()

    result = []
    for a in assignments:
        sub = (await db.execute(select(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == a.id, AssignmentSubmission.student_id == student_id))).scalar_one_or_none()
        class_name = None
        if a.class_id:
            cls = await db.get(Class, a.class_id)
            class_name = cls.name if cls else None
        result.append({
            "id": a.id, "title": a.title, "description": a.description,
            "class_name": class_name, "photo_url": a.photo_url,
            "questions": a.questions_json,
            "submitted": sub is not None,
            "submission": {"score": sub.score if sub else None, "answers": sub.answers_json if sub else [], "submitted_at": sub.submitted_at.isoformat() if sub else None} if sub else None,
            "created_at": a.created_at.isoformat(),
        })
    return result


@router.post("/student/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    answers: str = Form("[]"),
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """学生提交作业答案"""
    import json
    student_id = current_user[0].id
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")
    existing = (await db.execute(select(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == assignment_id, AssignmentSubmission.student_id == student_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="已提交过该作业")

    try:
        answers_list = json.loads(answers) if answers else []
    except json.JSONDecodeError:
        answers_list = []

    sub = AssignmentSubmission(assignment_id=assignment_id, student_id=student_id, answers_json=answers_list)
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return {"id": sub.id, "status": "submitted", "message": "提交成功"}
