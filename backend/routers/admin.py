"""
管理员路由 — 管理教师、班级、学生、作业、成绩
"""
from fastapi import APIRouter, Depends, HTTPException
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

    return {
        "teacher_count": teacher_count,
        "class_count": class_count,
        "student_count": student_count,
        "assignment_count": assignment_count,
        "homework_count": hw_count,
        "exam_count": exam_count,
        "avg_score": avg_score,
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

    db.delete(teacher)
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
):
    """查看所有学生"""
    students = db.query(Student).order_by(Student.created_at.desc()).all()
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
            "last_login": s.last_login.isoformat() if s.last_login else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return result


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
