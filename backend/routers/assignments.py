"""
作业发布路由 — 教师发布作业（可指定班级），学生查看/提交（只看到自己班级的）
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from database import get_db
from models import Assignment, AssignmentSubmission, Student, Class, ClassStudent
from utils.auth import require_teacher, require_student

router = APIRouter(prefix="/assignments", tags=["作业发布"])


# ===== 请求/响应模型 =====
class AssignmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    questions: list[dict] = Field(default_factory=list)
    due_date: str = ""
    class_id: Optional[int] = Field(default=None, ge=1)  # NULL=广播


class AssignmentSubmit(BaseModel):
    answers: list[dict] = Field(default_factory=list)


# ===== 教师端 =====

@router.post("/teacher")
async def create_assignment(
    body: AssignmentCreate,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师发布作业（可选指定班级，NULL=所有学生可见）"""
    teacher = current_user[0]
    if body.class_id:
        cls = db.query(Class).filter(Class.id == body.class_id, Class.teacher_id == teacher.id).first()
        if not cls:
            raise HTTPException(status_code=404, detail="班级不存在或不属于你")

    assignment = Assignment(
        teacher_id=teacher.id,
        class_id=body.class_id,
        title=body.title,
        description=body.description,
        questions_json=body.questions,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return {
        "id": assignment.id,
        "title": assignment.title,
        "class_id": assignment.class_id,
        "questions_count": len(assignment.questions_json),
        "created_at": assignment.created_at.isoformat(),
    }


@router.get("/teacher")
async def list_assignments(
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师查看自己发布的所有作业（含班级信息）"""
    teacher_id = current_user[0].id
    assignments = (
        db.query(Assignment)
        .filter(Assignment.teacher_id == teacher_id)
        .order_by(Assignment.created_at.desc())
        .all()
    )
    result = []
    for a in assignments:
        sub_count = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == a.id
        ).count()
        class_name = None
        if a.class_id:
            cls = db.query(Class).get(a.class_id)
            class_name = cls.name if cls else None
        result.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "class_id": a.class_id,
            "class_name": class_name,
            "questions_count": len(a.questions_json),
            "submissions": sub_count,
            "created_at": a.created_at.isoformat(),
        })
    return result


@router.get("/teacher/{assignment_id}/submissions")
async def view_submissions(
    assignment_id: int,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师查看某次作业的提交情况"""
    assignment = db.query(Assignment).get(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")

    subs = (
        db.query(AssignmentSubmission)
        .filter(AssignmentSubmission.assignment_id == assignment_id)
        .order_by(AssignmentSubmission.submitted_at.desc())
        .all()
    )
    result = []
    for s in subs:
        student = db.query(Student).get(s.student_id)
        result.append({
            "student_id": s.student_id,
            "student_name": student.name if student else "未知",
            "score": s.score,
            "answers": s.answers_json,
            "status": s.status,
            "submitted_at": s.submitted_at.isoformat(),
        })
    return {
        "assignment": {
            "id": assignment.id,
            "title": assignment.title,
            "questions": assignment.questions_json,
        },
        "submissions": result,
    }


# ===== 学生端 =====

@router.get("/student")
async def student_assignments(
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """学生查看待完成的作业（仅看自己的班级的或广播作业）"""
    student_id = current_user[0].id

    # 获取学生的班级 ID
    cs = db.query(ClassStudent).filter(ClassStudent.student_id == student_id).first()
    my_class_id = cs.class_id if cs else None

    query = db.query(Assignment).order_by(Assignment.created_at.desc()).all()

    result = []
    for a in query:
        # 筛选：广播(class_id=NULL) 或 同班级 或 同教师的作业(该教师下的班级)
        if a.class_id is not None and a.class_id != my_class_id:
            continue

        sub = db.query(AssignmentSubmission).filter(
            AssignmentSubmission.assignment_id == a.id,
            AssignmentSubmission.student_id == student_id,
        ).first()

        class_name = None
        if a.class_id:
            cls = db.query(Class).get(a.class_id)
            class_name = cls.name if cls else None

        result.append({
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "class_name": class_name,
            "questions": a.questions_json,
            "submitted": sub is not None,
            "submission": {
                "score": sub.score if sub else None,
                "answers": sub.answers_json if sub else [],
                "submitted_at": sub.submitted_at.isoformat() if sub else None,
            } if sub else None,
            "created_at": a.created_at.isoformat(),
        })
    return result


@router.post("/student/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    body: AssignmentSubmit,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """学生提交作业"""
    student_id = current_user[0].id
    assignment = db.query(Assignment).get(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="作业不存在")

    existing = db.query(AssignmentSubmission).filter(
        AssignmentSubmission.assignment_id == assignment_id,
        AssignmentSubmission.student_id == student_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="已提交过该作业")

    sub = AssignmentSubmission(
        assignment_id=assignment_id,
        student_id=student_id,
        answers_json=body.answers,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {
        "id": sub.id,
        "status": "submitted",
        "message": "提交成功",
    }
