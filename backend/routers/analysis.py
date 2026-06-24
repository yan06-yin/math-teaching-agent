"""
分析路由 — 学生画像、班级分析
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Student, HomeworkSubmission, ExamAttempt, ErrorRecord
from schemas import StudentProfile
from utils.auth import require_student

router = APIRouter()


@router.get("/student/{student_id}")
async def get_student_profile(
    student_id: int,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """获取学生个人学习画像（只能查看自己的）"""
    auth_student_id = current_user[0].id
    if student_id != auth_student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的数据")

    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 作业统计（仅未删除的）
    homework_count = db.query(func.count(HomeworkSubmission.id)).filter(
        HomeworkSubmission.student_id == student_id,
        HomeworkSubmission.is_deleted == False,
    ).scalar() or 0

    # 考试统计（仅未删除的）
    exam_count = db.query(func.count(ExamAttempt.id)).filter(
        ExamAttempt.student_id == student_id,
        ExamAttempt.is_deleted == False,
    ).scalar() or 0

    # 平均分（仅已批改的）
    avg_hw = db.query(func.avg(HomeworkSubmission.score)).filter(
        HomeworkSubmission.student_id == student_id,
        HomeworkSubmission.is_deleted == False,
        HomeworkSubmission.status == "done",
    ).scalar() or 0

    avg_exam = db.query(func.avg(ExamAttempt.score)).filter(
        ExamAttempt.student_id == student_id,
        ExamAttempt.is_deleted == False,
        ExamAttempt.student_answers != None,
    ).scalar() or 0

    # 平均分：已批改记录加权平均
    hw_valid = db.query(func.count(HomeworkSubmission.id)).filter(
        HomeworkSubmission.student_id == student_id,
        HomeworkSubmission.is_deleted == False,
        HomeworkSubmission.status == "done",
    ).scalar() or 0
    exam_valid = db.query(func.count(ExamAttempt.id)).filter(
        ExamAttempt.student_id == student_id,
        ExamAttempt.is_deleted == False,
        ExamAttempt.student_answers != None,
    ).scalar() or 0
    total_score = float(avg_hw or 0) * hw_valid + float(avg_exam or 0) * exam_valid
    total_count = hw_valid + exam_valid
    avg_score = round(total_score / total_count, 1) if total_count > 0 else 0

    # 错题知识点统计
    errors = db.query(ErrorRecord).filter(
        ErrorRecord.student_id == student_id
    ).order_by(ErrorRecord.error_count.desc()).all()

    weak_points = [e.knowledge_point for e in errors[:5]] if errors else []
    strong_points = [e.knowledge_point for e in errors[-5:][::-1]] if len(errors) > 5 else []

    # 趋势判断（仅已批改且未删除的）
    scores = (
        db.query(HomeworkSubmission.score)
        .filter(
            HomeworkSubmission.student_id == student_id,
            HomeworkSubmission.is_deleted == False,
            HomeworkSubmission.status == "done",
        )
        .order_by(HomeworkSubmission.created_at)
        .all()
    )
    if len(scores) >= 3:
        recent = [s[0] for s in scores[-3:]]
        older = [s[0] for s in scores[:3]]
        if sum(recent) / len(recent) > sum(older) / len(older) * 1.05:
            trend = "rising"
        elif sum(recent) / len(recent) < sum(older) / len(older) * 0.95:
            trend = "falling"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return StudentProfile(
        total_homework=homework_count,
        total_exams=exam_count,
        avg_score=round(avg_score, 1),
        strengths=strong_points,
        weaknesses=weak_points,
        trend=trend,
    )


@router.get("/class/{student_id}/trends")
async def get_score_trends(
    student_id: int,
    current_user=Depends(require_student),
    db: Session = Depends(get_db),
):
    """获取学生成绩趋势（用于前端折线图，只能查看自己的）"""
    auth_student_id = current_user[0].id
    if student_id != auth_student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的数据")

    homeworks = (
        db.query(HomeworkSubmission.score, HomeworkSubmission.created_at)
        .filter(
            HomeworkSubmission.student_id == student_id,
            HomeworkSubmission.is_deleted == False,
            HomeworkSubmission.status == "done",
        )
        .order_by(HomeworkSubmission.created_at)
        .all()
    )
    exams = (
        db.query(ExamAttempt.score, ExamAttempt.created_at)
        .filter(
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_deleted == False,
        )
        .order_by(ExamAttempt.created_at)
        .all()
    )

    all_scores = [
        {"date": h[1].isoformat(), "score": h[0], "type": "homework"}
        for h in homeworks
    ] + [
        {"date": e[1].isoformat(), "score": e[0], "type": "exam"}
        for e in exams
    ]
    all_scores.sort(key=lambda x: x["date"])

    return all_scores
