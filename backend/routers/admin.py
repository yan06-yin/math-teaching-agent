"""
管理员路由 — 管理教师、班级、学生、作业、成绩
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import (
    Teacher, Student, Class, ClassStudent, InviteCode,
    Assignment, AssignmentSubmission, HomeworkSubmission, ExamAttempt,
    ErrorRecord, ActivityLog,
)
from schemas import AdminAssignStudent
from utils.auth import require_admin, require_teacher

router = APIRouter()


# ===== 总览 =====

@router.get("/dashboard")
async def admin_dashboard(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """系统总览数据"""
    teacher_count = db.query(func.count(Teacher.id)).filter(Teacher.is_admin == False).scalar() or 0
    class_count = db.query(func.count(Class.id)).scalar() or 0
    student_count = db.query(func.count(Student.id)).scalar() or 0
    assignment_count = db.query(func.count(Assignment.id)).scalar() or 0
    hw_count = db.query(func.count(HomeworkSubmission.id)).scalar() or 0
    exam_count = db.query(func.count(ExamAttempt.id)).scalar() or 0
    avg_hw = db.query(func.avg(HomeworkSubmission.score)).scalar() or 0
    avg_exam = db.query(func.avg(ExamAttempt.score)).scalar() or 0
    avg_score = round(float((avg_hw + avg_exam) / 2) if avg_hw and avg_exam else float(avg_hw or avg_exam or 0), 1)

    # 每月趋势数据（近6个月）
    from sqlalchemy import extract
    from datetime import datetime, timezone, timedelta

    months_data = []
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        month = now.month - i
        year = now.year
        while month < 1:
            month += 12
            year -= 1
        label = f"{year}-{month:02d}"

        hw_in_month = db.query(func.count(HomeworkSubmission.id)).filter(
            extract("year", HomeworkSubmission.created_at) == year,
            extract("month", HomeworkSubmission.created_at) == month,
        ).scalar() or 0

        exam_in_month = db.query(func.count(ExamAttempt.id)).filter(
            extract("year", ExamAttempt.created_at) == year,
            extract("month", ExamAttempt.created_at) == month,
        ).scalar() or 0

        avg_in_month = db.query(func.avg(ExamAttempt.score)).filter(
            extract("year", ExamAttempt.created_at) == year,
            extract("month", ExamAttempt.created_at) == month,
        ).scalar() or 0

        months_data.append({
            "month": label,
            "homework": hw_in_month,
            "exam": exam_in_month,
            "avg_score": round(float(avg_in_month), 1),
        })

    return {
        "teacher_count": teacher_count,
        "class_count": class_count,
        "student_count": student_count,
        "assignment_count": assignment_count,
        "homework_count": hw_count,
        "exam_count": exam_count,
        "avg_score": avg_score,
        "monthly_trends": months_data,
    }


# ===== 教师管理 =====

@router.get("/teachers")
async def list_all_teachers(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看所有教师"""
    teachers = db.query(Teacher).filter(Teacher.is_admin == False).order_by(Teacher.created_at.desc()).all()
    result = []
    for t in teachers:
        class_count = db.query(func.count(Class.id)).filter(Class.teacher_id == t.id).scalar() or 0
        student_count = (
            db.query(func.count(ClassStudent.id))
            .join(Class, ClassStudent.class_id == Class.id)
            .filter(Class.teacher_id == t.id)
            .scalar() or 0
        )
        result.append({
            "id": t.id,
            "name": t.name,
            "username": t.username,
            "school": t.school,
            "class_count": class_count,
            "student_count": student_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return result


@router.delete("/teachers/{teacher_id}")
async def delete_teacher(
    teacher_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除教师（级联清理所有班级、作业、关联数据）"""
    teacher = db.query(Teacher).filter(Teacher.id == teacher_id, Teacher.is_admin == False).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    # 级联删除班级相关的学生关联
    class_ids = [c.id for c in db.query(Class).filter(Class.teacher_id == teacher_id).all()]
    if class_ids:
        db.query(ClassStudent).filter(ClassStudent.class_id.in_(class_ids)).delete(synchronize_session=False)
        db.query(InviteCode).filter(InviteCode.class_id.in_(class_ids)).delete(synchronize_session=False)

    # 教师发布的作业及提交
    assignments = db.query(Assignment).filter(Assignment.teacher_id == teacher_id).all()
    for a in assignments:
        db.query(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == a.id).delete(synchronize_session=False)
    db.query(Assignment).filter(Assignment.teacher_id == teacher_id).delete(synchronize_session=False)

    # 班级
    db.query(Class).filter(Class.teacher_id == teacher_id).delete(synchronize_session=False)

    teacher.is_deleted = True
    db.commit()
    return {"message": f"已删除教师 {teacher.name}"}


# ===== 班级管理 =====

@router.get("/classes")
async def list_all_classes(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看所有班级"""
    classes = db.query(Class).order_by(Class.created_at.desc()).all()
    result = []
    for cls in classes:
        teacher = db.query(Teacher).get(cls.teacher_id)
        student_count = db.query(func.count(ClassStudent.id)).filter(ClassStudent.class_id == cls.id).scalar() or 0
        result.append({
            "id": cls.id,
            "name": cls.name,
            "teacher_id": cls.teacher_id,
            "teacher_name": teacher.name if teacher else "未知",
            "school_level": cls.school_level,
            "student_count": student_count,
            "created_at": cls.created_at.isoformat() if cls.created_at else None,
        })
    return result


@router.delete("/classes/{class_id}")
async def admin_delete_class(
    class_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员删除班级"""
    cls = db.query(Class).get(class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    db.delete(cls)
    db.commit()
    return {"message": "班级已删除"}


# ===== 学生管理 =====

@router.get("/students")
async def list_all_students(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """查看所有学生（支持分页）"""
    total = db.query(func.count(Student.id)).scalar() or 0
    students = db.query(Student).filter(Student.is_deleted == False).order_by(Student.created_at.desc()).offset(offset).limit(limit).all()
    result = []
    for s in students:
        cs = db.query(ClassStudent).filter(ClassStudent.student_id == s.id).first()
        class_name = None
        if cs:
            cls = db.query(Class).get(cs.class_id)
            class_name = cls.name if cls else None

        hw_count = db.query(func.count(HomeworkSubmission.id)).filter(HomeworkSubmission.student_id == s.id).scalar() or 0
        exam_count = db.query(func.count(ExamAttempt.id)).filter(ExamAttempt.student_id == s.id).scalar() or 0
        hw_avg = db.query(func.avg(HomeworkSubmission.score)).filter(HomeworkSubmission.student_id == s.id).scalar() or 0
        exam_avg = db.query(func.avg(ExamAttempt.score)).filter(ExamAttempt.student_id == s.id).scalar() or 0
        avg_score = float((hw_avg + exam_avg) / 2) if hw_avg and exam_avg else float(hw_avg or exam_avg or 0)

        result.append({
            "id": s.id,
            "name": s.name,
            "student_id": s.student_id,
            "school_level": s.school_level,
            "class_name": class_name,
            "homework_count": hw_count,
            "exam_count": exam_count,
            "avg_score": round(avg_score, 1),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "students": result,
    }


@router.post("/students/assign")
async def admin_assign_student(
    body: AdminAssignStudent,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员分配学生到班级"""
    student = db.query(Student).get(body.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    cls = db.query(Class).get(body.class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")

    existing = db.query(ClassStudent).filter(ClassStudent.student_id == body.student_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该学生已在班级中")

    cs = ClassStudent(
        student_id=body.student_id,
        class_id=body.class_id,
        joined_via="manual",
    )
    db.add(cs)
    db.commit()
    return {"message": f"已将 {student.name} 分配到班级 {cls.name}"}


@router.delete("/students/{student_id}/class")
async def admin_remove_student_class(
    student_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员将学生移出班级"""
    cs = db.query(ClassStudent).filter(ClassStudent.student_id == student_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="该学生不在任何班级中")
    db.delete(cs)
    db.commit()
    return {"message": "已移出班级"}


# ===== 作业管理 =====

@router.get("/assignments")
async def list_all_assignments(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看所有作业"""
    assignments = db.query(Assignment).order_by(Assignment.created_at.desc()).all()
    result = []
    for a in assignments:
        teacher = db.query(Teacher).get(a.teacher_id)
        sub_count = db.query(func.count(AssignmentSubmission.id)).filter(
            AssignmentSubmission.assignment_id == a.id
        ).scalar() or 0

        class_name = None
        if a.class_id:
            cls = db.query(Class).get(a.class_id)
            class_name = cls.name if cls else "广播作业"

        result.append({
            "id": a.id,
            "title": a.title,
            "teacher_name": teacher.name if teacher else "未知",
            "class_name": class_name,
            "questions_count": len(a.questions_json) if a.questions_json else 0,
            "submissions": sub_count,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return result


# ===== 成绩统计 =====

@router.get("/exams")
async def list_exam_records(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看考试记录"""
    exams = db.query(ExamAttempt).order_by(ExamAttempt.created_at.desc()).limit(200).all()
    result = []
    for e in exams:
        student = db.query(Student).get(e.student_id)
        result.append({
            "id": e.id,
            "student_name": student.name if student else "未知",
            "student_id": student.student_id if student else "",
            "score": e.score,
            "questions_count": len(e.questions_json) if e.questions_json else 0,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        })
    return result


# ===== AI 模型配置 =====

@router.get("/ai-providers")
async def list_ai_providers(
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看所有 AI 模型配置"""
    from models import AIProvider
    providers = db.query(AIProvider).order_by(AIProvider.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "provider": p.provider,
            "base_url": p.base_url,
            "model": p.model,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in providers
    ]


@router.post("/ai-providers")
async def create_ai_provider(
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """新增 AI 模型配置"""
    from models import AIProvider

    if body.get("is_active"):
        db.query(AIProvider).filter(AIProvider.is_active == True).update({"is_active": False})

    provider = AIProvider(
        name=body["name"],
        provider=body.get("provider", "openai-compatible"),
        base_url=body["base_url"].rstrip("/"),
        api_key=body["api_key"],
        model=body["model"],
        is_active=body.get("is_active", False),
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    from services.open_model_service import open_model_service
    open_model_service.reload_from_db(db)

    return {
        "id": provider.id,
        "name": provider.name,
        "model": provider.model,
        "is_active": provider.is_active,
        "message": "配置已添加并生效",
    }


@router.put("/ai-providers/{provider_id}")
async def update_ai_provider(
    provider_id: int,
    body: dict,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新 AI 模型配置"""
    from models import AIProvider
    provider = db.query(AIProvider).get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="配置不存在")

    if body.get("is_active"):
        db.query(AIProvider).filter(AIProvider.is_active == True, AIProvider.id != provider_id).update({"is_active": False})

    for field in ["name", "provider", "base_url", "api_key", "model"]:
        if field in body:
            setattr(provider, field, body[field])
    if "is_active" in body:
        provider.is_active = body["is_active"]

    db.commit()

    from services.open_model_service import open_model_service
    open_model_service.reload_from_db(db)

    return {"message": "配置已更新并生效"}


@router.delete("/ai-providers/{provider_id}")
async def delete_ai_provider(
    provider_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除 AI 模型配置"""
    from models import AIProvider
    provider = db.query(AIProvider).get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="配置不存在")
    was_active = provider.is_active
    db.delete(provider)
    db.commit()

    if was_active:
        from services.open_model_service import open_model_service
        fallback = db.query(AIProvider).filter(AIProvider.is_active == True).first()
        if not fallback:
            fallback = db.query(AIProvider).first()
            if fallback:
                fallback.is_active = True
                db.commit()
        open_model_service.reload_from_db(db)

    return {"message": "配置已删除"}
