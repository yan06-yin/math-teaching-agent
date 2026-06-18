"""
教师端路由 — 错题汇总、班级分析
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Student, ErrorRecord, HomeworkSubmission, ExamAttempt
from utils.knowledge_mapper import normalize_knowledge_point

router = APIRouter()


@router.get("/errors")
async def get_error_summary(
    teacher_id: int = Depends(lambda: 1),  # TODO: JWT
    db: Session = Depends(get_db),
    knowledge_point: str = None,
):
    """获取全班错题汇总（按知识点分组）"""
    query = (
        db.query(
            ErrorRecord.knowledge_point,
            func.count(ErrorRecord.id).label("affected_students"),
            func.sum(ErrorRecord.error_count).label("total_errors"),
        )
        .group_by(ErrorRecord.knowledge_point)
    )

    if knowledge_point:
        query = query.filter(ErrorRecord.knowledge_point == knowledge_point)

    results = query.order_by(func.sum(ErrorRecord.error_count).desc()).all()

    total_students = db.query(func.count(Student.id)).scalar() or 1

    return [
        {
            "knowledge_point": r.knowledge_point,
            "error_count": r.total_errors,
            "affected_students": r.affected_students,
            "error_rate": round(r.affected_students / total_students * 100, 1),
            "recent_errors": [],  # 可扩展
        }
        for r in results
    ]


@router.get("/dashboard")
async def get_teacher_dashboard(
    teacher_id: int = Depends(lambda: 1),
    db: Session = Depends(get_db),
):
    """教师仪表盘总览"""
    total_students = db.query(func.count(Student.id)).scalar() or 0
    total_homework = db.query(func.count(HomeworkSubmission.id)).scalar() or 0
    total_exams = db.query(func.count(ExamAttempt.id)).scalar() or 0

    # 班级平均分
    avg_hw = db.query(func.avg(HomeworkSubmission.score)).scalar() or 0
    avg_exam = db.query(func.avg(ExamAttempt.score)).scalar() or 0
    class_avg = float((avg_hw + avg_exam) / 2) if avg_hw and avg_exam else float(avg_hw or avg_exam or 0)

    # 知识点薄弱热力图
    errors = (
        db.query(
            ErrorRecord.knowledge_point,
            func.sum(ErrorRecord.error_count).label("total"),
            func.count(ErrorRecord.id).label("students"),
        )
        .group_by(ErrorRecord.knowledge_point)
        .order_by(func.sum(ErrorRecord.error_count).desc())
        .all()
    )

    heatmap = [
        {
            "point": e.knowledge_point,
            "error_rate": round(int(e.students) / max(total_students, 1) * 100, 1),
            "severity": "high" if int(e.students) / max(total_students, 1) > 0.5
                        else "medium" if int(e.students) / max(total_students, 1) > 0.2
                        else "low",
        }
        for e in errors[:15]
    ]

    # 问题学生排行
    student_errors = (
        db.query(
            ErrorRecord.student_id,
            func.sum(ErrorRecord.error_count).label("total_errors"),
            func.count(ErrorRecord.knowledge_point).label("weak_points"),
        )
        .group_by(ErrorRecord.student_id)
        .order_by(func.sum(ErrorRecord.error_count).desc())
        .limit(10)
        .all()
    )

    top_students = []
    for se in student_errors:
        student = db.query(Student).get(se.student_id)
        top_students.append({
            "student_id": se.student_id,
            "name": student.name if student else "未知",
            "total_errors": se.total_errors,
            "weak_points": se.weak_points,
        })

    return {
        "total_students": total_students,
        "total_homework": total_homework,
        "total_exams": total_exams,
        "class_avg_score": round(class_avg, 1),
        "knowledge_heatmap": heatmap,
        "top_error_students": top_students,
    }


@router.get("/student/{student_id}/errors")
async def get_student_errors(
    student_id: int,
    teacher_id: int = Depends(lambda: 1),
    db: Session = Depends(get_db),
):
    """查看单个学生的错题详情"""
    student = db.query(Student).get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    errors = (
        db.query(ErrorRecord)
        .filter(ErrorRecord.student_id == student_id)
        .order_by(ErrorRecord.error_count.desc())
        .all()
    )

    return {
        "student": {"id": student.id, "name": student.name, "level": student.school_level},
        "errors": [
            {
                "knowledge_point": e.knowledge_point,
                "question": e.question_text,
                "student_answer": e.student_answer,
                "correct_answer": e.correct_answer,
                "error_count": e.error_count,
                "last_error_date": e.last_error_date.isoformat() if e.last_error_date else None,
            }
            for e in errors
        ],
    }
