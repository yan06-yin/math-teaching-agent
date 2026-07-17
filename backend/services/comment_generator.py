import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


COMMENT_STRATEGIES = {
    "struggling": {
        "tone": "鼓励为主，保护信心",
        "focus": "基础巩固",
        "length": "100-150字",
        "principles": [
            "先肯定具体进步",
            "只指出1-2个最关键的问题",
            "给出可操作的改进步骤",
            "结尾给予信心",
        ],
    },
    "average": {
        "tone": "激励+方法指导",
        "focus": "查漏补缺",
        "length": "80-120字",
        "principles": [
            "肯定做得好的方面",
            "指出最需要提升的方向",
            "提供具体的学习方法建议",
            "设定可实现的短期目标",
        ],
    },
    "advanced": {
        "tone": "肯定+挑战拓展",
        "focus": "思维深化",
        "length": "60-100字",
        "principles": [
            "肯定出色表现",
            "指出可优化的细节",
            "推荐拓展思考方向",
        ],
    },
}


class CommentGenerator:
    def __init__(self, model_service):
        self.model_service = model_service

    def _classify_student(self, score: float, avg_score: float) -> str:
        if score < 60:
            return "struggling"
        elif score >= 85:
            return "advanced"
        else:
            return "average"

    async def generate(self, student_name: str, school_level: str,
                        subject: str, score: float, comments: str,
                        mistakes: list, student_portrait: Optional[dict] = None,
                        avg_score: float = 70) -> str:
        student_type = self._classify_student(score, avg_score)
        strategy = COMMENT_STRATEGIES[student_type]

        mistake_summary = ""
        if mistakes:
            subjects = [m.get("question", "未知")[:30] for m in mistakes if not m.get("correct", True)]
            if subjects:
                mistake_summary = "主要错题：" + "；".join(subjects[:3])

        portrait_summary = ""
        if student_portrait:
            weaks = student_portrait.get("weak_points", {}).get(subject, [])[:3]
            if weaks:
                weak_str = "、".join([w.get("point", "") for w in weaks])
                portrait_summary = f"历史薄弱点：{weak_str}"
            trend = student_portrait.get("trends", {}).get(subject, "")
            if trend:
                portrait_summary += f"；成绩趋势：{trend}"

        subject_name = "数学" if subject == "math" else "语文" if subject == "chinese" else "英语"

        prompt = f"""你是一位{subject_name}教师，正在给学生写个性化评语。

学生：{student_name}
学段：{school_level}
得分：{score}分 | 历史均分：{avg_score:.1f}分
学生类型：{student_type}（{strategy['tone']}，字数{strategy['length']}）

错题情况：{mistake_summary}
学生画像：{portrait_summary}
原始评语参考：{comments}

写一段评语，直接返回文本（不要 JSON，不要 markdown）。
要求：
- 针对具体错题或表现，而非泛泛而谈
- 体现对学生的了解
- 给出可操作的改进建议
- 符合学生类型对应的语气风格
"""

        messages = [
            {"role": "system", "content": "你是一位有爱心、善于鼓励学生的教师。"},
            {"role": "user", "content": prompt},
        ]

        try:
            result = await self.model_service._chat(messages, max_tokens=1024)
            if isinstance(result, dict):
                text = result.get("raw", "")
                if text:
                    return text.strip()
                return comments
            return result.strip()
        except Exception as e:
            logger.error(f"评语生成失败: {e}")
            return comments


def create_comment_generator(model_service=None):
    if model_service is None:
        from services.open_model_service import open_model_service
        model_service = open_model_service
    return CommentGenerator(model_service)