"""
管理员路由 — 异步 SQLAlchemy
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, union_all, cast, String, extract
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from database import get_db
from models import (
    Teacher, Student, Class, ClassStudent, InviteCode,
    Assignment, AssignmentSubmission, HomeworkSubmission, ExamAttempt,
    ErrorRecord, ActivityLog, GradingTask, AIProvider,
)
from schemas import AdminAssignStudent, AIProviderCreate, AIProviderUpdate
from utils.auth import require_admin

router = APIRouter()


@router.get("/dashboard")
async def admin_dashboard(current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    teacher_count = (await db.execute(select(func.count(Teacher.id)).filter(Teacher.is_admin == False, Teacher.is_deleted == False))).scalar() or 0
    class_count = (await db.execute(select(func.count(Class.id)))).scalar() or 0
    student_count = (await db.execute(select(func.count(Student.id)).filter(Student.is_deleted == False))).scalar() or 0
    assignment_count = (await db.execute(select(func.count(Assignment.id)))).scalar() or 0
    hw_count = (await db.execute(select(func.count(HomeworkSubmission.id)).join(Student, HomeworkSubmission.student_id == Student.id).filter(HomeworkSubmission.is_deleted == False, Student.is_deleted == False))).scalar() or 0
    exam_count = (await db.execute(select(func.count(ExamAttempt.id)).join(Student, ExamAttempt.student_id == Student.id).filter(ExamAttempt.is_deleted == False, Student.is_deleted == False))).scalar() or 0

    # 全局平均分
    all_scores = union_all(
        select(HomeworkSubmission.student_id.label("sid"), HomeworkSubmission.score.label("score")).join(Student, HomeworkSubmission.student_id == Student.id).filter(HomeworkSubmission.is_deleted == False, HomeworkSubmission.status == "done", Student.is_deleted == False),
        select(ExamAttempt.student_id.label("sid"), ExamAttempt.score.label("score")).join(Student, ExamAttempt.student_id == Student.id).filter(ExamAttempt.is_deleted == False, ExamAttempt.status == "graded", Student.is_deleted == False),
    ).subquery()
    student_avg_subq = select(func.avg(all_scores.c.score).label("student_avg")).group_by(all_scores.c.sid).subquery()
    row = (await db.execute(select(func.avg(student_avg_subq.c.student_avg)))).scalar()
    avg_score = round(float(row), 1) if row else 0

    # 月度趋势
    months_data = []
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        month = now.month - i
        year = now.year
        while month < 1:
            month += 12
            year -= 1
        label = f"{year}-{month:02d}"

        hw_in_month = (await db.execute(select(func.count(HomeworkSubmission.id)).join(Student, HomeworkSubmission.student_id == Student.id).filter(extract("year", HomeworkSubmission.created_at) == year, extract("month", HomeworkSubmission.created_at) == month, HomeworkSubmission.is_deleted == False, Student.is_deleted == False))).scalar() or 0
        exam_in_month = (await db.execute(select(func.count(ExamAttempt.id)).join(Student, ExamAttempt.student_id == Student.id).filter(extract("year", ExamAttempt.created_at) == year, extract("month", ExamAttempt.created_at) == month, ExamAttempt.is_deleted == False, Student.is_deleted == False))).scalar() or 0

        hw_scores_m = select(HomeworkSubmission.student_id.label("sid"), HomeworkSubmission.score.label("score")).join(Student, HomeworkSubmission.student_id == Student.id).filter(extract("year", HomeworkSubmission.created_at) == year, extract("month", HomeworkSubmission.created_at) == month, HomeworkSubmission.is_deleted == False, HomeworkSubmission.status == "done", Student.is_deleted == False)
        exam_scores_m = select(ExamAttempt.student_id.label("sid"), ExamAttempt.score.label("score")).join(Student, ExamAttempt.student_id == Student.id).filter(extract("year", ExamAttempt.created_at) == year, extract("month", ExamAttempt.created_at) == month, ExamAttempt.is_deleted == False, ExamAttempt.status == "graded", Student.is_deleted == False)
        all_scores_m = union_all(hw_scores_m, exam_scores_m).subquery()
        m_student_avg = select(func.avg(all_scores_m.c.score).label("student_avg")).group_by(all_scores_m.c.sid).subquery()
        m_row = (await db.execute(select(func.avg(m_student_avg.c.student_avg)))).scalar()
        avg_in_month = round(float(m_row), 1) if m_row else 0

        months_data.append({"month": label, "homework_count": hw_in_month, "exam_count": exam_in_month, "avg_score": avg_in_month})

    return {"teacher_count": teacher_count, "class_count": class_count, "student_count": student_count, "assignment_count": assignment_count, "homework_count": hw_count, "exam_count": exam_count, "avg_score": avg_score, "monthly_trends": months_data}


@router.get("/teachers")
async def list_all_teachers(current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    teachers = (await db.execute(select(Teacher).filter(Teacher.is_admin == False, Teacher.is_deleted == False).order_by(Teacher.created_at.desc()))).scalars().all()
    result = []
    for t in teachers:
        class_count = (await db.execute(select(func.count(Class.id)).filter(Class.teacher_id == t.id))).scalar() or 0
        student_count = (await db.execute(select(func.count(ClassStudent.id)).join(Class, ClassStudent.class_id == Class.id).filter(Class.teacher_id == t.id))).scalar() or 0
        result.append({"id": t.id, "name": t.name, "username": t.username, "school": t.school, "class_count": class_count, "student_count": student_count, "created_at": t.created_at.isoformat() if t.created_at else None})
    return result


@router.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    teacher = (await db.execute(select(Teacher).filter(Teacher.id == teacher_id, Teacher.is_admin == False))).scalar_one_or_none()
    if not teacher:
        raise HTTPException(status_code=404, detail="教师不存在")

    class_ids = [c.id for c in (await db.execute(select(Class).filter(Class.teacher_id == teacher_id))).scalars().all()]
    student_ids = []
    if class_ids:
        student_ids = [r[0] for r in (await db.execute(select(ClassStudent.student_id).filter(ClassStudent.class_id.in_(class_ids)))).all()]
        for model in [ClassStudent, InviteCode]:
            objs = (await db.execute(select(model).filter(model.class_id.in_(class_ids)))).scalars().all()
            for obj in objs:
                await db.delete(obj)

    assignments = (await db.execute(select(Assignment).filter(Assignment.teacher_id == teacher_id))).scalars().all()
    for a in assignments:
        subs = (await db.execute(select(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == a.id))).scalars().all()
        for s in subs:
            await db.delete(s)
        await db.flush()  # 先提交 submissions 的 DELETE
        await db.delete(a)
    await db.flush()

    classes = (await db.execute(select(Class).filter(Class.teacher_id == teacher_id))).scalars().all()
    for c in classes:
        await db.delete(c)

    teacher.is_deleted = True

    if student_ids:
        # 仅删除该教师班级下的学习记录（作业/考试/错题等），不软删除学生账号本身。
        # 学生账号是独立的，跨班级场景下不应因教师删除而丢失账号。
        for model in [GradingTask, ExamAttempt, HomeworkSubmission, ErrorRecord, ActivityLog, AssignmentSubmission]:
            objs = (await db.execute(select(model).filter(model.student_id.in_(student_ids)))).scalars().all()
            for obj in objs:
                await db.delete(obj)

    await db.commit()
    return {"message": f"已删除教师 {teacher.name} 及其班级/作业数据（学生账号保留）"}


@router.get("/classes")
async def list_all_classes(current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    classes = (await db.execute(select(Class).order_by(Class.created_at.desc()))).scalars().all()
    result = []
    for cls in classes:
        teacher = await db.get(Teacher, cls.teacher_id)
        student_count = (await db.execute(select(func.count(ClassStudent.id)).filter(ClassStudent.class_id == cls.id))).scalar() or 0
        result.append({"id": cls.id, "name": cls.name, "teacher_id": cls.teacher_id, "teacher_name": teacher.name if teacher else "未知", "school_level": cls.school_level, "student_count": student_count, "created_at": cls.created_at.isoformat() if cls.created_at else None})
    return result


@router.delete("/classes/{class_id}")
async def admin_delete_class(class_id: int, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cls = await db.get(Class, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    # 先删该班级下的作业提交（FK 约束），逐级 flush 确保顺序
    assignments = (await db.execute(select(Assignment).filter(Assignment.class_id == class_id))).scalars().all()
    for a in assignments:
        subs = (await db.execute(select(AssignmentSubmission).filter(AssignmentSubmission.assignment_id == a.id))).scalars().all()
        for s in subs:
            await db.delete(s)
        await db.flush()  # 先提交 submission 的 DELETE，再删 assignment
        await db.delete(a)
    await db.flush()
    # 再删邀请码和学生关联
    invites = (await db.execute(select(InviteCode).filter(InviteCode.class_id == class_id))).scalars().all()
    for i in invites:
        await db.delete(i)
    members = (await db.execute(select(ClassStudent).filter(ClassStudent.class_id == class_id))).scalars().all()
    for m in members:
        await db.delete(m)
    await db.delete(cls)
    await db.commit()
    return {"message": "班级已删除"}


@router.get("/students")
async def list_all_students(current_user=Depends(require_admin), db: AsyncSession = Depends(get_db), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
    total = (await db.execute(select(func.count(Student.id)).filter(Student.is_deleted == False))).scalar() or 0
    students = (await db.execute(select(Student).filter(Student.is_deleted == False).order_by(Student.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    result = []
    for s in students:
        cs = (await db.execute(select(ClassStudent).filter(ClassStudent.student_id == s.id))).scalar_one_or_none()
        class_name = None
        if cs:
            cls = await db.get(Class, cs.class_id)
            class_name = cls.name if cls else None
        hw_count = (await db.execute(select(func.count(HomeworkSubmission.id)).filter(HomeworkSubmission.student_id == s.id, HomeworkSubmission.is_deleted == False))).scalar() or 0
        exam_count = (await db.execute(select(func.count(ExamAttempt.id)).filter(ExamAttempt.student_id == s.id, ExamAttempt.is_deleted == False))).scalar() or 0
        hw_avg = (await db.execute(select(func.avg(HomeworkSubmission.score)).filter(HomeworkSubmission.student_id == s.id, HomeworkSubmission.is_deleted == False, HomeworkSubmission.status == "done"))).scalar() or 0
        exam_avg = (await db.execute(select(func.avg(ExamAttempt.score)).filter(ExamAttempt.student_id == s.id, ExamAttempt.is_deleted == False, ExamAttempt.status == "graded"))).scalar() or 0
        hw_valid = hw_count
        exam_valid = exam_count
        total_scores = float(hw_avg or 0) * hw_valid + float(exam_avg or 0) * exam_valid
        total_valid = hw_valid + exam_valid
        avg_score = round(total_scores / total_valid, 1) if total_valid > 0 else 0
        result.append({"id": s.id, "name": s.name, "student_id": s.student_id, "school_level": s.school_level, "class_name": class_name, "homework_count": hw_count, "exam_count": exam_count, "avg_score": round(avg_score, 1), "created_at": s.created_at.isoformat() if s.created_at else None})
    return {"total": total, "offset": offset, "limit": limit, "students": result}


@router.post("/students/assign")
async def admin_assign_student(body: AdminAssignStudent, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, body.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    cls = await db.get(Class, body.class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="班级不存在")
    existing = (await db.execute(select(ClassStudent).filter(ClassStudent.student_id == body.student_id))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="该学生已在班级中")
    db.add(ClassStudent(student_id=body.student_id, class_id=body.class_id, joined_via="manual"))
    await db.commit()
    return {"message": f"已将 {student.name} 分配到班级 {cls.name}"}


@router.delete("/students/{student_id}/class")
async def admin_remove_student_class(student_id: int, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    cs = (await db.execute(select(ClassStudent).filter(ClassStudent.student_id == student_id))).scalar_one_or_none()
    if not cs:
        raise HTTPException(status_code=404, detail="该学生不在任何班级中")
    await db.delete(cs)
    await db.commit()
    return {"message": "已移出班级"}


@router.delete("/students/{student_id}")
async def admin_delete_student(student_id: int, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    student.is_deleted = True
    for model in [ClassStudent, GradingTask, ExamAttempt, HomeworkSubmission, ErrorRecord, ActivityLog, AssignmentSubmission]:
        objs = (await db.execute(select(model).filter(model.student_id == student_id))).scalars().all()
        for obj in objs:
            await db.delete(obj)
    await db.commit()
    return {"message": f"已删除学生 {student.name}({student.student_id}) 及相关数据"}


@router.get("/assignments")
async def list_all_assignments(current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    assignments = (await db.execute(select(Assignment).order_by(Assignment.created_at.desc()))).scalars().all()
    result = []
    for a in assignments:
        teacher = await db.get(Teacher, a.teacher_id)
        sub_count = (await db.execute(select(func.count(AssignmentSubmission.id)).filter(AssignmentSubmission.assignment_id == a.id))).scalar() or 0
        class_name = None
        if a.class_id:
            cls = await db.get(Class, a.class_id)
            class_name = cls.name if cls else "广播作业"
        result.append({"id": a.id, "title": a.title, "teacher_name": teacher.name if teacher else "未知", "class_name": class_name, "questions_count": len(a.questions_json) if a.questions_json else 0, "submissions": sub_count, "created_at": a.created_at.isoformat() if a.created_at else None})
    return result


@router.get("/exams")
async def list_exam_records(current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    exams = (await db.execute(select(ExamAttempt).join(Student, ExamAttempt.student_id == Student.id).filter(ExamAttempt.is_deleted == False, Student.is_deleted == False).order_by(ExamAttempt.created_at.desc()).limit(200))).scalars().all()
    result = []
    for e in exams:
        student = await db.get(Student, e.student_id)
        result.append({"id": e.id, "student_name": student.name if student else "未知", "student_id": student.student_id if student else "", "score": e.score, "questions_count": len(e.questions_json) if e.questions_json else 0, "created_at": e.created_at.isoformat() if e.created_at else None})
    return result


@router.get("/ai-providers")
async def list_ai_providers(current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    providers = (await db.execute(select(AIProvider).order_by(AIProvider.created_at.desc()))).scalars().all()
    return [{"id": p.id, "name": p.name, "provider": p.provider, "base_url": p.base_url, "model": p.model, "is_active": p.is_active, "created_at": p.created_at.isoformat() if p.created_at else None} for p in providers]


@router.post("/ai-providers")
async def create_ai_provider(body: AIProviderCreate, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if body.is_active:
        providers = (await db.execute(select(AIProvider).filter(AIProvider.is_active == True))).scalars().all()
        for p in providers:
            p.is_active = False
    provider = AIProvider(name=body.name, provider=body.provider, base_url=body.base_url.rstrip("/"), api_key=body.api_key, model=body.model, is_active=body.is_active)
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    from services.open_model_service import open_model_service
    open_model_service.reload_from_db()
    return {"id": provider.id, "name": provider.name, "model": provider.model, "is_active": provider.is_active, "message": "配置已添加并生效"}


@router.put("/ai-providers/{provider_id}")
async def update_ai_provider(provider_id: int, body: AIProviderUpdate, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    provider = await db.get(AIProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="配置不存在")
    if body.is_active:
        others = (await db.execute(select(AIProvider).filter(AIProvider.is_active == True, AIProvider.id != provider_id))).scalars().all()
        for p in others:
            p.is_active = False
    update_data = body.model_dump(exclude_unset=True)
    for field in ["name", "provider", "base_url", "api_key", "model"]:
        if field in update_data:
            value = update_data[field]
            setattr(provider, field, value.rstrip("/") if field == "base_url" else value)
    if "is_active" in update_data:
        provider.is_active = update_data["is_active"]
    await db.commit()
    from services.open_model_service import open_model_service
    open_model_service.reload_from_db()
    return {"message": "配置已更新并生效"}


@router.delete("/ai-providers/{provider_id}")
async def delete_ai_provider(provider_id: int, current_user=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    provider = await db.get(AIProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="配置不存在")
    was_active = provider.is_active
    await db.delete(provider)
    await db.commit()
    if was_active:
        from services.open_model_service import open_model_service
        fallback = (await db.execute(select(AIProvider).filter(AIProvider.is_active == True))).scalars().first()
        if not fallback:
            fallback = (await db.execute(select(AIProvider))).scalars().first()
            if fallback:
                fallback.is_active = True
                await db.commit()
        open_model_service.reload_from_db()
    return {"message": "配置已删除"}
