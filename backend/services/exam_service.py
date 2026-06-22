"""
出题服务 — 智能出题、组卷、诊断报告生成
使用 Agnes AI 替代 Coze
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import ExamAttempt, Student, ErrorRecord
from services.open_model_service import open_model_service
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
        # 每次调用前重新加载 AI 配置（解决多 worker 下配置不一致问题）
        open_model_service.reload_from_db()

        result = await open_model_service.generate_exam(
            school_level=config.get("school_level", "初中"),
            config=exam_config,
        )

        questions = result.get("questions", [])

        # 跳过图片生成（非 OpenAI 兼容接口不支持）
        # 如需配图可后续通过其他接口生成

        exam = ExamAttempt(
            student_id=student_id,
            exam_config_json=exam_config,
            questions_json=questions,
            student_answers=[],
        )
        db.add(exam)
        db.commit()
        db.refresh(exam)
        return exam

    except Exception as e:
        logger.error(f"出题失败: {e}")
        import traceback
        traceback.print_exc()
        raise


async def grade_exam(db: Session, exam_id: int, answers: list[dict]) -> tuple[ExamAttempt, list]:
    """批改考试并生成诊断报告，返回 (exam, details_list)"""
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

        result = await open_model_service.grade_homework(
            student_name=student.name if student else f"学生{exam.student_id}",
            school_level=student.school_level if student else "初中",
            questions_and_answers=f"题目:\n{questions_str}\n\n学生答案:\n{answers_str}",
        )

        exam.score = float(result.get("score", 0))
        details = result.get("details", [])
        correct_count = sum(1 for d in details if d.get("correct"))
        wrong_details = [d for d in details if not d.get("correct")]

        report_parts = [
            f"📊 诊断分析报告",
            f"",
            f"得分：{exam.score}分（共{len(details)}题，正确{correct_count}题，错误{len(wrong_details)}题）",
            f"",
            f"📝 教师评语：",
            f"{result.get('comments', '')}",
        ]

        if wrong_details:
            report_parts.extend(["", "❌ 错题分析："])
            for i, w in enumerate(wrong_details, 1):
                report_parts.append(f"")
                report_parts.append(f"第{i}题：{w.get('question', '')}")
                if w.get("student_answer"):
                    report_parts.append(f"  你的答案：{w['student_answer']}")
                if w.get("correct_answer"):
                    report_parts.append(f"  正确答案：{w['correct_answer']}")
                if w.get("explanation"):
                    report_parts.append(f"  💡 解析：{w['explanation']}")

        report_parts.extend(["", "💪 建议：", "根据本次答题情况，建议针对错题涉及的知识点进行复习。"])
        exam.diagnostic_report = "\n".join(report_parts)
        db.commit()

        # 记录错题到 ErrorRecord
        from datetime import datetime, timezone
        for detail in details:
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
            if details:
                weak_points = [d.get("explanation", d.get("question", "未分类")) for d in details if not d.get("correct", True)]
            if not weak_points:
                weak_points = ["综合基础"]
            plan = await open_model_service.generate_learning_plan(
                student_name=student.name if student else "该学生",
                school_level=student.school_level if student else "初中",
                weak_points=weak_points[:5],
            )
            exam.learning_plan = plan.get("plan", [])
            db.commit()

        db.refresh(exam)
        return exam, details

    except Exception as e:
        logger.error(f"考试批改失败: {e}")
        raise
