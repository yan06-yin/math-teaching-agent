"""
分析路由 — 学生画像、成绩趋势
使用异步 SQLAlchemy
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Student, HomeworkSubmission, ExamAttempt, ErrorRecord
from schemas import StudentProfile
from utils.auth import require_student

router = APIRouter()


@router.get("/student/{student_id}")
async def get_student_profile(
    student_id: int,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """获取学生个人学习画像（只能查看自己的）"""
    auth_student_id = current_user[0].id
    if student_id != auth_student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的数据")

    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    # 作业统计
    homework_count = (await db.execute(
        select(func.count(HomeworkSubmission.id)).filter(
            HomeworkSubmission.student_id == student_id,
            HomeworkSubmission.is_deleted == False,
        )
    )).scalar() or 0

    exam_count = (await db.execute(
        select(func.count(ExamAttempt.id)).filter(
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_deleted == False,
        )
    )).scalar() or 0

    # 平均分
    avg_hw = (await db.execute(
        select(func.avg(HomeworkSubmission.score)).filter(
            HomeworkSubmission.student_id == student_id,
            HomeworkSubmission.is_deleted == False,
            HomeworkSubmission.status == "done",
        )
    )).scalar() or 0

    avg_exam = (await db.execute(
        select(func.avg(ExamAttempt.score)).filter(
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_deleted == False,
            ExamAttempt.status == "graded",
        )
    )).scalar() or 0

    hw_valid = (await db.execute(
        select(func.count(HomeworkSubmission.id)).filter(
            HomeworkSubmission.student_id == student_id,
            HomeworkSubmission.is_deleted == False,
            HomeworkSubmission.status == "done",
        )
    )).scalar() or 0

    exam_valid = (await db.execute(
        select(func.count(ExamAttempt.id)).filter(
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_deleted == False,
            ExamAttempt.status == "graded",
        )
    )).scalar() or 0

    total_score = float(avg_hw or 0) * hw_valid + float(avg_exam or 0) * exam_valid
    total_count = hw_valid + exam_valid
    avg_score = round(total_score / total_count, 1) if total_count > 0 else 0

    # 错题知识点统计
    errors = (await db.execute(
        select(ErrorRecord).filter(ErrorRecord.student_id == student_id)
        .order_by(ErrorRecord.error_count.desc())
    )).scalars().all()

    weak_points = [e.knowledge_point for e in errors[:5]] if errors else []
    # 优势知识点：错题记录中错误次数较低的知识点（仅错过 1 次，说明已基本掌握）
    # 注意：系统当前未独立记录"做对的知识点"，此处基于错题做推断：
    #       错过且只错过一次 → 视为已掌握。按 error_count 升序取前 5。
    #       旧实现要求 len(errors) > 5 才返回，导致大多数学生没有优势知识点（bug），已修复。
    strong_points = [e.knowledge_point for e in errors if e.error_count <= 1][:5] if errors else []

    # 趋势判断：比较前半段 vs 后半段，至少 2 条记录才判断
    scores = (await db.execute(
        select(HomeworkSubmission.score).filter(
            HomeworkSubmission.student_id == student_id,
            HomeworkSubmission.is_deleted == False,
            HomeworkSubmission.status == "done",
        ).order_by(HomeworkSubmission.created_at)
    )).scalars().all()

    if len(scores) >= 2:
        mid = len(scores) // 2
        older = scores[:mid] if mid > 0 else scores[:1]
        recent = scores[mid:]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        if recent_avg > older_avg * 1.05:
            trend = "rising"
        elif recent_avg < older_avg * 0.95:
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
    db: AsyncSession = Depends(get_db),
):
    """获取学生成绩趋势"""
    auth_student_id = current_user[0].id
    if student_id != auth_student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的数据")

    homeworks = (await db.execute(
        select(HomeworkSubmission.score, HomeworkSubmission.created_at).filter(
            HomeworkSubmission.student_id == student_id,
            HomeworkSubmission.is_deleted == False,
            HomeworkSubmission.status == "done",
        ).order_by(HomeworkSubmission.created_at)
    )).all()

    exams = (await db.execute(
        select(ExamAttempt.score, ExamAttempt.created_at).filter(
            ExamAttempt.student_id == student_id,
            ExamAttempt.is_deleted == False,
            ExamAttempt.status == "graded",
        ).order_by(ExamAttempt.created_at)
    )).all()

    all_scores = [
        {"date": h[1].isoformat(), "score": h[0], "type": "homework"} for h in homeworks
    ] + [
        {"date": e[1].isoformat(), "score": e[0], "type": "exam"} for e in exams
    ]
    all_scores.sort(key=lambda x: x["date"])
    return all_scores
