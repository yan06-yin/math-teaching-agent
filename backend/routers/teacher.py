"""
教师端路由 — 错题汇总、班级分析、知识点钻取
使用异步 SQLAlchemy
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Student, Teacher, ErrorRecord, HomeworkSubmission, ExamAttempt, ActivityLog, AssignmentSubmission, Class, ClassStudent, GradingTask
from utils.auth import require_teacher
from utils.knowledge_mapper import normalize_knowledge_point

router = APIRouter()


@router.get("/errors")
async def get_error_summary(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
    knowledge_point: str = None,
    subject: str = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    teacher = current_user[0]
    teacher_class_ids = [c.id for c in (await db.execute(select(Class).filter(Class.teacher_id == teacher.id))).scalars().all()]
    student_ids = [r[0] for r in (await db.execute(select(ClassStudent.student_id).filter(ClassStudent.class_id.in_(teacher_class_ids)))).all()] if teacher_class_ids else [-1]

    query = (
        select(
            ErrorRecord.knowledge_point,
            func.count(func.distinct(ErrorRecord.student_id)).label("affected_students"),
            func.sum(ErrorRecord.error_count).label("total_errors"),
        )
        .filter(ErrorRecord.student_id.in_(student_ids))
        .group_by(ErrorRecord.knowledge_point)
    )
    if knowledge_point:
        query = query.filter(ErrorRecord.knowledge_point == knowledge_point)
    results = (await db.execute(query.order_by(func.sum(ErrorRecord.error_count).desc()))).all()

    total_students = len(student_ids) if student_ids and student_ids != [-1] else 1

    output = []
    for r in results:
        # 按学科过滤知识点
        from utils.knowledge_mapper import get_knowledge_info
        point_info = get_knowledge_info(r.knowledge_point, subject=subject or "math")
        if subject and subject not in " ".join(point_info.get("tags", [])):
            continue

        recent = (await db.execute(
            select(ErrorRecord).filter(
                ErrorRecord.knowledge_point == r.knowledge_point,
                ErrorRecord.student_id.in_(student_ids),
            ).order_by(ErrorRecord.last_error_date.desc()).limit(5)
        )).scalars().all()
        recent_errors = []
        for er in recent:
            student = await db.get(Student, er.student_id)
            recent_errors.append({
                "student_name": student.name if student else "未知",
                "student_id": er.student_id,
                "question": er.question_text,
                "error_count": er.error_count,
                "last_error_date": er.last_error_date.isoformat() if er.last_error_date else None,
            })
        output.append({
            "knowledge_point": r.knowledge_point,
            "error_count": r.total_errors,
            "affected_students": r.affected_students,
            "error_rate": round(r.affected_students / total_students * 100, 1),
            "recent_errors": recent_errors,
        })
    return output


@router.get("/errors/knowledge-point/{knowledge_point}")
async def get_knowledge_point_errors(
    knowledge_point: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    teacher = current_user[0]
    teacher_class_ids = [c.id for c in (await db.execute(select(Class).filter(Class.teacher_id == teacher.id))).scalars().all()]
    student_ids = [-1]
    if teacher_class_ids:
        student_ids = [r[0] for r in (await db.execute(select(ClassStudent.student_id).filter(ClassStudent.class_id.in_(teacher_class_ids)))).all()]

    errors = (await db.execute(
        select(ErrorRecord).filter(
            ErrorRecord.knowledge_point == knowledge_point,
            ErrorRecord.student_id.in_(student_ids),
        ).order_by(ErrorRecord.last_error_date.desc()).limit(limit)
    )).scalars().all()

    result = []
    for er in errors:
        student = await db.get(Student, er.student_id)
        result.append({
            "student_id": er.student_id,
            "student_name": student.name if student else "未知",
            "student_level": student.school_level if student else "未知",
            "question": er.question_text,
            "student_answer": er.student_answer,
            "correct_answer": er.correct_answer,
            "error_count": er.error_count,
            "last_error_date": er.last_error_date.isoformat() if er.last_error_date else None,
        })
    return {"knowledge_point": knowledge_point, "total_errors": len(result), "errors": result}


@router.get("/students")
async def get_all_students(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
    class_id: int = Query(None, ge=1),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    teacher = current_user[0]
    teacher_class_ids = [c.id for c in (await db.execute(select(Class).filter(Class.teacher_id == teacher.id))).scalars().all()]

    student_ids_sub = select(ClassStudent.student_id).filter(ClassStudent.class_id.in_(teacher_class_ids)).scalar_subquery()

    query = select(Student).filter(Student.id.in_(student_ids_sub), Student.is_deleted == False)
    if class_id:
        cls = (await db.execute(select(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id))).scalar_one_or_none()
        if not cls:
            raise HTTPException(status_code=404, detail="班级不存在")
        cs_student_ids = select(ClassStudent.student_id).filter(ClassStudent.class_id == class_id).scalar_subquery()
        query = select(Student).filter(Student.id.in_(cs_student_ids), Student.is_deleted == False)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar() or 0
    students = (await db.execute(query.order_by(Student.created_at.desc()).offset(offset).limit(limit))).scalars().all()

    result = []
    for s in students:
        hw_count = (await db.execute(select(func.count(HomeworkSubmission.id)).filter(HomeworkSubmission.student_id == s.id, HomeworkSubmission.is_deleted == False, HomeworkSubmission.status == "done"))).scalar() or 0
        hw_avg = (await db.execute(select(func.avg(HomeworkSubmission.score)).filter(HomeworkSubmission.student_id == s.id, HomeworkSubmission.is_deleted == False, HomeworkSubmission.status == "done"))).scalar() or 0
        exam_count = (await db.execute(select(func.count(ExamAttempt.id)).filter(ExamAttempt.student_id == s.id, ExamAttempt.is_deleted == False, ExamAttempt.status == "graded"))).scalar() or 0
        exam_avg = (await db.execute(select(func.avg(ExamAttempt.score)).filter(ExamAttempt.student_id == s.id, ExamAttempt.is_deleted == False, ExamAttempt.status == "graded"))).scalar() or 0

        hw_valid = hw_count
        exam_valid = exam_count
        total_score = float(hw_avg or 0) * hw_valid + float(exam_avg or 0) * exam_valid
        total_count = hw_valid + exam_valid
        avg_score = round(total_score / total_count, 1) if total_count > 0 else 0

        error_count = (await db.execute(select(func.sum(ErrorRecord.error_count)).filter(ErrorRecord.student_id == s.id))).scalar() or 0
        weak_count = (await db.execute(select(func.count(func.distinct(ErrorRecord.knowledge_point))).filter(ErrorRecord.student_id == s.id))).scalar() or 0

        result.append({
            "id": s.id, "name": s.name, "student_id": s.student_id, "level": s.school_level,
            "homework_count": hw_count, "exam_count": exam_count, "avg_score": round(avg_score, 1),
            "error_count": error_count, "weak_points": weak_count,
            "last_login": s.last_login.isoformat() if s.last_login else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return {"total": total, "offset": offset, "limit": limit, "students": result}


@router.get("/students/{student_id}/info")
async def get_student_full_info(student_id: int, current_user=Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    teacher = current_user[0]
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    cs = (await db.execute(
        select(ClassStudent).join(Class, ClassStudent.class_id == Class.id)
        .filter(ClassStudent.student_id == student_id, Class.teacher_id == teacher.id)
    )).scalars().first()
    if not cs:
        raise HTTPException(status_code=403, detail="只能查看自己班级的学生")
    return {"id": student.id, "name": student.name, "student_id": student.student_id, "level": student.school_level, "last_login": student.last_login.isoformat() if student.last_login else None, "created_at": student.created_at.isoformat() if student.created_at else None}


@router.delete("/students/{student_id}")
async def delete_student(student_id: int, current_user=Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    teacher = current_user[0]
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    cs = (await db.execute(
        select(ClassStudent).join(Class, ClassStudent.class_id == Class.id)
        .filter(ClassStudent.student_id == student_id, Class.teacher_id == teacher.id)
    )).scalars().first()
    if not cs:
        raise HTTPException(status_code=403, detail="只能删除自己班级的学生")

    student.is_deleted = True
    for model in [ClassStudent, GradingTask, ExamAttempt, HomeworkSubmission, ErrorRecord, ActivityLog, AssignmentSubmission]:
        objs = (await db.execute(select(model).filter(model.student_id == student_id))).scalars().all()
        for obj in objs:
            await db.delete(obj)
    await db.commit()
    return {"message": f"已删除学生 {student.name}({student.student_id}) 及相关数据"}


@router.get("/dashboard")
async def get_teacher_dashboard(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
    subject: str = Query(None, pattern="^(math|chinese|english)$"),
):
    teacher = current_user[0]
    teacher_class_ids = [c.id for c in (await db.execute(select(Class).filter(Class.teacher_id == teacher.id))).scalars().all()]

    if not teacher_class_ids:
        return {"total_students": 0, "total_homework": 0, "total_exams": 0, "class_avg_score": 0, "knowledge_heatmap": [], "top_error_students": []}

    student_ids_sub = select(ClassStudent.student_id).filter(ClassStudent.class_id.in_(teacher_class_ids)).scalar_subquery()

    total_students = (await db.execute(select(func.count(Student.id)).filter(Student.id.in_(student_ids_sub)))).scalar() or 0

    # 按学科筛选作业和考试
    hw_filter = [HomeworkSubmission.student_id.in_(student_ids_sub), HomeworkSubmission.is_deleted == False]
    exam_filter = [ExamAttempt.student_id.in_(student_ids_sub), ExamAttempt.is_deleted == False]
    if subject:
        hw_filter.append(HomeworkSubmission.subject == subject)

    total_homework = (await db.execute(select(func.count(HomeworkSubmission.id)).filter(*hw_filter))).scalar() or 0
    total_exams = (await db.execute(select(func.count(ExamAttempt.id)).filter(*exam_filter))).scalar() or 0

    # 按学科平均分
    hw_score_filter = hw_filter + [HomeworkSubmission.status == "done"]
    exam_score_filter = exam_filter + [ExamAttempt.status == "graded"]

    from sqlalchemy import union_all
    all_scores = union_all(
        select(HomeworkSubmission.student_id.label("sid"), HomeworkSubmission.score.label("score")).filter(*hw_score_filter),
        select(ExamAttempt.student_id.label("sid"), ExamAttempt.score.label("score")).filter(*exam_score_filter),
    ).subquery()
    student_avg_sub = select(func.avg(all_scores.c.score).label("student_avg")).group_by(all_scores.c.sid).subquery()
    class_avg_row = (await db.execute(select(func.avg(student_avg_sub.c.student_avg)))).scalar()
    class_avg = round(float(class_avg_row), 1) if class_avg_row else 0

    # 知识点热力图
    error_filter = [ErrorRecord.student_id.in_(student_ids_sub)]
    if subject:
        # 根据学科过滤知识点（通过知识点名称前缀匹配）
        if subject == "chinese":
            error_filter.append(ErrorRecord.knowledge_point.like("作文%") | ErrorRecord.knowledge_point.like("阅读%") |
                                ErrorRecord.knowledge_point.like("语言运用%") | ErrorRecord.knowledge_point.like("字%") |
                                ErrorRecord.knowledge_point.like("古诗词%") | ErrorRecord.knowledge_point.like("文言%"))
        elif subject == "english":
            error_filter.append(ErrorRecord.knowledge_point.like("英语-%"))

    errors = (await db.execute(
        select(ErrorRecord.knowledge_point, func.sum(ErrorRecord.error_count).label("total"), func.count(func.distinct(ErrorRecord.student_id)).label("students"))
        .filter(*error_filter)
        .group_by(ErrorRecord.knowledge_point)
        .order_by(func.sum(ErrorRecord.error_count).desc())
    )).all()

    heatmap = [{"point": e.knowledge_point, "error_rate": round(int(e.students) / max(total_students, 1) * 100, 1), "severity": "high" if int(e.students) / max(total_students, 1) > 0.5 else "medium" if int(e.students) / max(total_students, 1) > 0.2 else "low"} for e in errors[:15]]

    # 问题学生排行
    student_errors = (await db.execute(
        select(ErrorRecord.student_id, func.sum(ErrorRecord.error_count).label("total_errors"), func.count(ErrorRecord.knowledge_point).label("weak_points"))
        .filter(*error_filter)
        .group_by(ErrorRecord.student_id)
        .order_by(func.sum(ErrorRecord.error_count).desc())
        .limit(10)
    )).all()

    top_students = []
    for se in student_errors:
        student = await db.get(Student, se.student_id)
        top_students.append({"student_id": se.student_id, "name": student.name if student else "未知", "total_errors": se.total_errors, "weak_points": se.weak_points})

    return {"total_students": total_students, "total_homework": total_homework, "total_exams": total_exams, "class_avg_score": round(class_avg, 1), "knowledge_heatmap": heatmap, "top_error_students": top_students}


@router.get("/student/{student_id}/errors")
async def get_student_errors(student_id: int, current_user=Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    teacher = current_user[0]
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    cs = (await db.execute(
        select(ClassStudent).join(Class, ClassStudent.class_id == Class.id)
        .filter(ClassStudent.student_id == student_id, Class.teacher_id == teacher.id)
    )).scalars().first()
    if not cs:
        raise HTTPException(status_code=403, detail="只能查看自己班级的学生")

    errors = (await db.execute(
        select(ErrorRecord).filter(ErrorRecord.student_id == student_id).order_by(ErrorRecord.error_count.desc())
    )).scalars().all()

    return {
        "student": {"id": student.id, "name": student.name, "level": student.school_level},
        "errors": [{"knowledge_point": e.knowledge_point, "question": e.question_text, "student_answer": e.student_answer, "correct_answer": e.correct_answer, "error_count": e.error_count, "last_error_date": e.last_error_date.isoformat() if e.last_error_date else None} for e in errors],
    }
