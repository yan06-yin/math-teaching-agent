"""出题服务 — 智能出题、组卷、诊断报告生成（异步 SQLAlchemy）"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import ExamAttempt, Student, ErrorRecord
from services.open_model_service import open_model_service
from services.image_service import generate_exam_images
from utils.knowledge_mapper import normalize_knowledge_point

logger = logging.getLogger(__name__)


async def generate_and_save_exam(db: AsyncSession, student_id: int, config: dict, exam_id=None, subject: str = "math") -> ExamAttempt:
    """生成试卷并保存，支持多学科"""
    errors = (await db.execute(
        select(ErrorRecord).filter(ErrorRecord.student_id == student_id)
        .order_by(ErrorRecord.error_count.desc()).limit(10)
    )).scalars().all()

    weak_points = [e.knowledge_point for e in errors if e.error_count >= 2]
    all_points = list(set(config.get("knowledge_points", []) + weak_points))
    exam_config = {**config, "knowledge_points": all_points[:5], "subject": subject}

    try:
        open_model_service.reload_from_db()
        result = await open_model_service.generate_exam(
            school_level=config.get("school_level", "初中"),
            config=exam_config,
            subject=subject,
        )
        questions = result.get("questions", [])

        if config.get("with_images", True) and questions and subject == "math":
            try:
                questions = await generate_exam_images(questions)
            except Exception as e:
                logger.warning(f"图片生成失败，但试卷已生成: {e}")

        if exam_id:
            exam = await db.get(ExamAttempt, exam_id)
            if exam:
                exam.questions_json = questions
                exam.exam_config_json = exam_config
                await db.commit()
                await db.refresh(exam)
                return exam

        exam = ExamAttempt(
            student_id=student_id,
            exam_config_json=exam_config,
            questions_json=questions,
            student_answers=[],
            status="draft",
        )
        db.add(exam)
        await db.commit()
        await db.refresh(exam)
        return exam

    except Exception as e:
        logger.error(f"出题失败: {e}")
        import traceback
        traceback.print_exc()
        raise


async def grade_exam(db: AsyncSession, exam_id: int, answers: list, subject: str = "math") -> tuple[ExamAttempt, list]:
    """批改考试，支持多学科"""
    exam = await db.get(ExamAttempt, exam_id)
    if not exam:
        raise ValueError(f"考试记录不存在: exam_id={exam_id}")
    exam.student_answers = answers
    await db.commit()

    try:
        student = await db.get(Student, exam.student_id)
        questions_str = "\n".join(f"Q{i+1}: {q.get('question','')}\n答案: {q.get('answer','')}" for i, q in enumerate(exam.questions_json))
        answers_str = "\n".join(f"Q{i+1}: {a.get('answer','')}" for i, a in enumerate(answers))

        # 使用学科自适应评分
        result = await open_model_service.grade_subject_homework(
            student_name=student.name if student else f"学生{exam.student_id}",
            school_level=student.school_level if student else "初中",
            subject=subject,
            questions_and_answers=f"题目:\n{questions_str}\n\n学生答案:\n{answers_str}",
        )

        exam.score = float(result.get("score", 0))
        details = result.get("details", [])
        exam.details_json = details

        correct_count = sum(1 for d in details if d.get("correct"))
        wrong_details = [d for d in details if not d.get("correct")]

        subject_name = {"math": "数学", "chinese": "语文", "english": "英语"}.get(subject, "综合")

        report_parts = [
            f"📊 {subject_name}诊断分析报告", "",
            f"得分：{exam.score}分（共{len(details)}题，正确{correct_count}题，错误{len(wrong_details)}题）",
            "", f"📝 教师评语：", f"{result.get('comments', '')}",
        ]
        if wrong_details:
            report_parts.extend(["", "❌ 错题分析："])
            for i, w in enumerate(wrong_details, 1):
                report_parts.extend(["", f"第{i}题：{w.get('question','')}"])
                if w.get("student_answer"):
                    report_parts.append(f"  你的答案：{w['student_answer']}")
                if w.get("correct_answer"):
                    report_parts.append(f"  正确答案：{w['correct_answer']}")
                if w.get("explanation"):
                    report_parts.append(f"  💡 解析：{w['explanation']}")
        report_parts.extend(["", "💪 建议：", "根据本次答题情况，建议针对错题涉及的知识点进行复习。"])
        exam.diagnostic_report = json.dumps("\n".join(report_parts), ensure_ascii=False)
        await db.commit()

        # 更新错题记录 + 知识图谱
        from services.knowledge_graph_service import knowledge_graph_service
        kg = await knowledge_graph_service.load_from_db(exam.student_id, db)

        for detail in details:
            if not detail.get("correct", True):
                kp = normalize_knowledge_point(detail.get("question", "未分类")[:50], subject)
                existing = (await db.execute(
                    select(ErrorRecord).filter(ErrorRecord.student_id == exam.student_id, ErrorRecord.knowledge_point == kp)
                )).scalar_one_or_none()
                if existing:
                    existing.error_count += 1
                    existing.last_error_date = datetime.now(timezone.utc)
                else:
                    db.add(ErrorRecord(
                        student_id=exam.student_id, knowledge_point=kp, subject=subject,
                        question_text=detail.get("question", "")[:200],
                        student_answer=detail.get("student_answer", ""),
                        correct_answer=detail.get("correct_answer", ""),
                    ))
                kg.record_error(kp, subject=subject, level=student.school_level if student else "初中")

        await db.commit()

        # 生成学习计划（使用学科感知的提示词）
        weak_points = []
        if details:
            weak_points = [d.get("explanation", d.get("question", "未分类")) for d in details if not d.get("correct", True)]
        if not weak_points and exam.score >= 70:
            weak_points = ["综合巩固"]
        elif not weak_points:
            weak_points = ["综合基础"]

        plan = await open_model_service.generate_learning_plan(
            student_name=student.name if student else "该学生",
            school_level=student.school_level if student else "初中",
            weak_points=weak_points[:5], score=exam.score,
        )
        exam.learning_plan = plan.get("plan", [])
        exam.status = "graded"
        await db.commit()
        await db.refresh(exam)
        return exam, details

    except Exception as e:
        logger.error(f"考试批改失败: {e}", exc_info=True)
        try:
            exam = await db.get(ExamAttempt, exam_id)
            if exam:
                exam.status = "error"
                await db.commit()
        except Exception as mark_err:
            logger.error(f"标记考试 error 状态失败: {mark_err}", exc_info=True)
        raise
