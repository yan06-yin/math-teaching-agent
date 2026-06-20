"""
出题服务 — 智能出题、组卷、诊断报告生成
使用 Agnes AI 替代 Coze
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import ExamAttempt, Student, ErrorRecord
from services.agnes_service import agences_service
from utils.knowledge_mapper import normalize_knowledge_point

logger = logging.getLogger(__name__)


async def generate_and_save_exam(db: Session, student_id: int,
                                  config: dict) -> ExamAttempt:
    """
    根据学生情况出题：
    1. 查询学生薄弱知识点
    2. 调用 Agnes AI 出题
    3. 保存试卷
    """
    # 查询薄弱知识点
    errors = db.query(ErrorRecord).filter(
        ErrorRecord.student_id == student_id
    ).order_by(ErrorRecord.error_count.desc()).limit(10).all()

    weak_points = [e.knowledge_point for e in errors if e.error_count >= 2]

    # 如果薄弱知识点不够，从配置中补充
    all_points = list(set(config.get("knowledge_points", []) + weak_points))

    exam_config = {
        **config,
        "knowledge_points": all_points[:5],  # 最多 5 个知识点
    }

    try:
        result = await agences_service.generate_exam(
            school_level=config.get("school_level", "初中"),
            config=exam_config,
        )

        exam = ExamAttempt(
            student_id=student_id,
            exam_config_json=exam_config,
            questions_json=result.get("questions", []),
            student_answers=[],
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)
        return exam

    except Exception as e:
        logger.error(f"出题失败: {e}")
        raise


async def grade_exam(db: Session, exam_id: int, answers: list[dict]) -> ExamAttempt:
    """批改考试并生成诊断报告"""
    exam = db.query(ExamAttempt).get(exam_id)
    exam.student_answers = answers
    db.commit()

    try:
        # 调用 Agnes AI 批改
        student = db.query(Student).get(exam.student_id)
        questions_str = "\n".join(
            f"Q{i+1}: {q.get('question', '')}\n答案: {q.get('answer', '')}"
            for i, q in enumerate(exam.questions_json)
        )
        answers_str = "\n".join(
            f"Q{i+1}: {a.get('answer', '')}"
            for i, a in enumerate(answers)
        )

        result = await agences_service.grade_homework(
            student_name=student.name if student else f"学生{exam.student_id}",
            school_level=student.school_level if student else "初中",
            questions_and_answers=f"题目:\n{questions_str}\n\n学生答案:\n{answers_str}",
        )

        exam.score = float(result.get("score", 0))
        exam.diagnostic_report = result
        db.commit()

        # 记录错题到 ErrorRecord
        from datetime import datetime, timezone
        for detail in result.get("details", []):
            if not detail.get("correct", True):
                kp = normalize_knowledge_point(
                    detail.get("question", "未分类")[:50]
                )
                existing = db.query(ErrorRecord).filter(
                    ErrorRecord.student_id == exam.student_id,
                    ErrorRecord.knowledge_point == kp,
                ).first()
                if existing:
                    existing.error_count += 1
                    existing.last_error_date = datetime.now(timezone.utc)
                else:
                    db.add(ErrorRecord(
                        student_id=exam.student_id,
                        knowledge_point=kp,
                        question_text=detail.get("question", "")[:200],
                        student_answer=detail.get("student_answer", ""),
                        correct_answer=detail.get("correct_answer", ""),
                    ))
        db.commit()

        # 生成学习计划（如果分数<70 并且有错题）
        if exam.score < 70:
            weak_points = []
            if result.get("details"):
                weak_points = [d.get("explanation", d.get("question", "未分类")) for d in result["details"] if not d.get("correct", True)]
            if not weak_points:
                weak_points = ["综合基础"]
            plan = await agences_service.generate_learning_plan(
                student_name=student.name if student else "该学生",
                school_level=student.school_level if student else "初中",
                weak_points=weak_points[:5],
            )
            exam.learning_plan = plan.get("plan", [])
            db.commit()

        db.refresh(exam)
        return exam

    except Exception as e:
        logger.error(f"考试批改失败: {e}")
        raise
