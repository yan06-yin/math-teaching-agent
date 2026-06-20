"""
教师端路由 — 错题汇总、班级分析、知识点钻取
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Student, ErrorRecord, HomeworkSubmission, ExamAttempt
from utils.auth import require_teacher
from utils.knowledge_mapper import normalize_knowledge_point

router = APIRouter()


@router.get("/errors")
async def get_error_summary(
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
    knowledge_point: str = None,
):
    """获取全班错题汇总（按知识点分组），包含最近错题详情"""
    query = (
        db.query(
            ErrorRecord.knowledge_point,
            func.count(func.distinct(ErrorRecord.student_id)).label("affected_students"),
            func.sum(ErrorRecord.error_count).label("total_errors"),
        )
        .group_by(ErrorRecord.knowledge_point)
    )

    if knowledge_point:
        query = query.filter(ErrorRecord.knowledge_point == knowledge_point)

    results = query.order_by(func.sum(ErrorRecord.error_count).desc()).all()

    total_students = db.query(func.count(Student.id)).scalar() or 1

    output = []
    for r in results:
        # 获取该知识点的最近 5 条错题
        recent = (
            db.query(ErrorRecord)
            .filter(ErrorRecord.knowledge_point == r.knowledge_point)
            .order_by(ErrorRecord.last_error_date.desc())
            .limit(5)
            .all()
        )
        recent_errors = []
        for er in recent:
            student = db.query(Student).get(er.student_id)
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
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    """钻取：获取特定知识点的全部错题详情"""
    errors = (
        db.query(ErrorRecord)
        .filter(ErrorRecord.knowledge_point == knowledge_point)
        .order_by(ErrorRecord.last_error_date.desc())
        .limit(limit)
        .all()
    )

    result = []
    for er in errors:
        student = db.query(Student).get(er.student_id)
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

    return {
        "knowledge_point": knowledge_point,
        "total_errors": len(result),
        "errors": result,
    }


@router.get("/students")
async def get_all_students(
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师查看所有学生信息（无论是否参加过考试）"""
    students = db.query(Student).order_by(Student.created_at.desc()).all()
    result = []
    for s in students:
        # 作业统计
        hw_count = db.query(func.count(HomeworkSubmission.id)).filter(
            HomeworkSubmission.student_id == s.id
        ).scalar() or 0
        hw_avg = db.query(func.avg(HomeworkSubmission.score)).filter(
            HomeworkSubmission.student_id == s.id
        ).scalar() or 0

        # 考试统计
        exam_count = db.query(func.count(ExamAttempt.id)).filter(
            ExamAttempt.student_id == s.id
        ).scalar() or 0
        exam_avg = db.query(func.avg(ExamAttempt.score)).filter(
            ExamAttempt.student_id == s.id
        ).scalar() or 0

        # 错题数
        error_count = db.query(func.sum(ErrorRecord.error_count)).filter(
            ErrorRecord.student_id == s.id
        ).scalar() or 0

        # 薄弱知识点数
        weak_count = db.query(func.count(func.distinct(ErrorRecord.knowledge_point))).filter(
            ErrorRecord.student_id == s.id
        ).scalar() or 0

        avg_score = float((hw_avg + exam_avg) / 2) if hw_avg and exam_avg else float(hw_avg or exam_avg or 0)

        result.append({
            "id": s.id,
            "name": s.name,
            "student_id": s.student_id,
            "level": s.school_level,
            "homework_count": hw_count,
            "exam_count": exam_count,
            "avg_score": round(avg_score, 1),
            "error_count": error_count,
            "weak_points": weak_count,
            "last_login": s.last_login.isoformat() if s.last_login else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return result


@router.get("/students/{student_id}/info")
async def get_student_full_info(
    student_id: int,
    current_user=Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """教师查看某个学生的完整信息"""
    student = db.query(Student).get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")
    return {
        "id": student.id,
        "name": student.name,
        "student_id": student.student_id,
        "level": student.school_level,
        "last_login": student.last_login.isoformat() if student.last_login else None,
        "created_at": student.created_at.isoformat() if student.created_at else None,
    }
async def get_teacher_dashboard(
    current_user=Depends(require_teacher),
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
            func.count(func.distinct(ErrorRecord.student_id)).label("students"),
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
    current_user=Depends(require_teacher),
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
