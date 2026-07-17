"""
分析路由 — 学生画像、成绩趋势、跨学科分析
使用异步 SQLAlchemy
"""
from fastapi import APIRouter, Depends, HTTPException, Query
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
    """获取学生个人学习画像（支持多学科）"""
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

    # 错题知识点统计（按学科分组）
    errors = (await db.execute(
        select(ErrorRecord).filter(ErrorRecord.student_id == student_id)
        .order_by(ErrorRecord.error_count.desc())
    )).scalars().all()

    weak_points = [e.knowledge_point for e in errors[:5]] if errors else []
    strong_points = [e.knowledge_point for e in errors if e.error_count <= 1][:5] if errors else []

    # 按学科分组的薄弱点
    weak_by_subject = {"math": [], "chinese": [], "english": []}
    for e in errors:
        subj = getattr(e, "subject", "math") or "math"
        if subj in weak_by_subject:
            weak_by_subject[subj].append(e.knowledge_point)

    # 趋势判断
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
        weak_by_subject=weak_by_subject,
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
        select(HomeworkSubmission.score, HomeworkSubmission.created_at, HomeworkSubmission.subject).filter(
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
        {"date": h[1].isoformat(), "score": h[0], "type": "homework", "subject": h[2] or "math"}
        for h in homeworks
    ] + [
        {"date": e[1].isoformat(), "score": e[0], "type": "exam", "subject": "math"} for e in exams
    ]
    all_scores.sort(key=lambda x: x["date"])
    return all_scores


@router.get("/student/{student_id}/comprehensive")
async def get_comprehensive_report(
    student_id: int,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """
    获取综合学情报告（跨学科）
    返回各学科的平均分、薄弱点、趋势等
    """
    auth_student_id = current_user[0].id
    if student_id != auth_student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的数据")

    subjects = ["math", "chinese", "english"]
    subject_names = {"math": "数学", "chinese": "语文", "english": "英语"}

    report = {
        "student_id": student_id,
        "subjects": {},
        "overall_avg": 0,
    }

    total_score_sum = 0
    total_count = 0

    for subject in subjects:
        # 各学科平均分
        hw_scores = (await db.execute(
            select(HomeworkSubmission.score).filter(
                HomeworkSubmission.student_id == student_id,
                HomeworkSubmission.subject == subject,
                HomeworkSubmission.status == "done",
                HomeworkSubmission.is_deleted == False,
                HomeworkSubmission.score > 0,
            )
        )).scalars().all()

        scores_list = [s for s in hw_scores if s]
        avg = round(sum(scores_list) / len(scores_list), 1) if scores_list else 0
        total_score_sum += avg * len(scores_list)
        total_count += len(scores_list)

        # 各学科错题
        errors = (await db.execute(
            select(ErrorRecord).filter(
                ErrorRecord.student_id == student_id,
            ).order_by(ErrorRecord.error_count.desc())
            .limit(10)
        )).scalars().all()

        # 按学科过滤知识点
        from utils.knowledge_mapper import get_knowledge_info
        subject_errors = []
        for e in errors:
            info = get_knowledge_info(e.knowledge_point, "", subject)
            if info.get("tags") and any(subject in " ".join(info["tags"]).lower() for subject in ["math", "chinese", "english"]):
                subject_errors.append({
                    "point": e.knowledge_point,
                    "count": e.error_count,
                })

        # 趋势
        if len(scores_list) >= 3:
            mid = len(scores_list) // 2
            first_half = sum(scores_list[:mid]) / mid if mid > 0 else 0
            second_half = sum(scores_list[mid:]) / (len(scores_list) - mid) if (len(scores_list) - mid) > 0 else 0
            diff = second_half - first_half
            trend = "rising" if diff > 5 else ("falling" if diff < -5 else "stable")
        else:
            trend = "stable"

        report["subjects"][subject] = {
            "name": subject_names.get(subject, subject),
            "avg_score": avg,
            "trend": trend,
            "scores_count": len(scores_list),
            "weak_points": subject_errors[:5],
        }

    report["overall_avg"] = round(total_score_sum / total_count, 1) if total_count > 0 else 0

    # 跨学科分析洞察
    try:
        from services.knowledge_graph_service import knowledge_graph_service
        await knowledge_graph_service.load_from_db(student_id, db)
        cross_insights = knowledge_graph_service.get_cross_subject_insights(student_id)
        report["cross_subject_insights"] = cross_insights
    except Exception as e:
        report["cross_subject_insights"] = []

    return report


@router.get("/student/{student_id}/knowledge-graph")
async def get_knowledge_graph(
    student_id: int,
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """获取学生知识图谱"""
    auth_student_id = current_user[0].id
    if student_id != auth_student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的数据")

    try:
        from services.knowledge_graph_service import knowledge_graph_service
        graph = await knowledge_graph_service.load_from_db(student_id, db)
        return graph.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"知识图谱加载失败: {e}")


@router.get("/student/{student_id}/learning-path")
async def get_learning_path(
    student_id: int,
    subject: str = Query("math", pattern="^(math|chinese|english)$"),
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """获取学习路径推荐"""
    auth_student_id = current_user[0].id
    if student_id != auth_student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的数据")

    try:
        from services.knowledge_graph_service import knowledge_graph_service
        await knowledge_graph_service.load_from_db(student_id, db)

        weak_points = knowledge_graph_service.get_weak_points(student_id, subject=subject, top_n=5)
        return {
            "student_id": student_id,
            "subject": subject,
            "weak_points": weak_points,
            "learning_path": weak_points,  # 薄弱点本身就是学习路径
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"学习路径生成失败: {e}")


@router.post("/student/{student_id}/generate-learning-plan")
async def generate_learning_plan(
    student_id: int,
    subject: str = Query("math", pattern="^(math|chinese|english)$"),
    days: int = Query(14, ge=7, le=30),
    current_user=Depends(require_student),
    db: AsyncSession = Depends(get_db),
):
    """手动生成学习计划：分析学生所有数据，调用 AI 生成"""
    auth_student_id = current_user[0].id
    if student_id != auth_student_id:
        raise HTTPException(status_code=403, detail="只能查看自己的数据")

    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    try:
        errors = (await db.execute(
            select(ErrorRecord).filter(ErrorRecord.student_id == student_id)
            .order_by(ErrorRecord.error_count.desc()).limit(10)
        )).scalars().all()

        hw_scores = (await db.execute(
            select(HomeworkSubmission.score).filter(
                HomeworkSubmission.student_id == student_id,
                HomeworkSubmission.subject == subject,
                HomeworkSubmission.status == "done",
                HomeworkSubmission.is_deleted == False,
            )
        )).scalars().all()

        avg_score = round(sum(hw_scores) / len(hw_scores), 1) if hw_scores else 70
        weak_points = [{"name": e.knowledge_point, "mastery": max(0, 1 - e.error_count * 0.2)}
                       for e in errors[:5]] if errors else []

        from services.open_model_service import open_model_service
        from utils.learning_path import LearningPathGenerator
        gen = LearningPathGenerator(open_model_service)
        plan = await gen.generate(
            student_name=student.name,
            school_level=student.school_level,
            weak_points=weak_points,
            strong_points=[],
            subject=subject,
            score=avg_score,
            days=days,
        )

        return {"student_id": student_id, "subject": subject, "avg_score": avg_score,
                "weak_points": [e.knowledge_point for e in errors[:5]], "plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"学习计划生成失败: {e}")