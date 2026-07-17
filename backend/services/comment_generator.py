"""
个性化评语生成器

基于学生画像和当前作业表现，生成因人而异的评语。
支持三种学生类型（学困生、中等生、优等生）的差异化策略。
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# 评语风格模板
COMMENT_STRATEGIES = {
    "struggling": {
        "tone": "鼓励为主，保护信心",
        "focus": "基础巩固，具体改进步骤",
        "length": "100-150字",
        "principles": [
            "先肯定具体进步（哪怕很小）",
            "只指出1-2个最关键的问题",
            "给出可操作的改进步骤",
            "结尾给予信心和期待",
        ],
    },
    "average": {
        "tone": "激励+方法指导",
        "focus": "查漏补缺，方法优化",
        "length": "80-120字",
        "principles": [
            "肯定做得好的方面",
            "指出最需要提升的1个方向",
            "提供具体的学习方法建议",
            "设定可实现的短期目标",
        ],
    },
    "advanced": {
        "tone": "肯定+挑战拓展",
        "focus": "思维深化，拓展提升",
        "length": "60-100字",
        "principles": [
            "肯定出色表现和具体亮点",
            "指出可优化的细节",
            "推荐拓展思考方向或进阶题",
        ],
    },
}


class CommentGenerator:
    """个性化评语生成器"""

    def __init__(self, model_service):
        self.model_service = model_service

    def _classify_student(self, score: float, avg_score: float) -> str:
        """根据分数和平均分判断学生类型"""
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
        """
        生成个性化评语

        Args:
            student_name: 学生姓名
            school_level: 学段
            subject: 学科
            score: 本次得分
            comments: AI 原始评语
            mistakes: 错题列表
            student_portrait: 学生画像字典
            avg_score: 该生历史平均分

        Returns:
            个性化评语文本
        """
        student_type = self._classify_student(score, avg_score)
        strategy = COMMENT_STRATEGIES[student_type]

        # 构建错题摘要
        mistake_summary = ""
        if mistakes:
            subjects = [m.get("question", "未知")[:30] for m in mistakes if not m.get("correct", True)]
            if subjects:
                mistake_summary = "主要错题：" + "；".join(subjects[:3])

        # 构建画像摘要
        portrait_summary = ""
        if student_portrait:
            weaks = student_portrait.get("weak_points", {}).get(subject, [])[:3]
            if weaks:
                weak_str = "、".join([w.get("point", "") for w in weaks])
                portrait_summary = f"历史薄弱点：{weak_str}"
            trend = student_portrait.get("trends", {}).get(subject, "")
            if trend:
                portrait_summary += f"；成绩趋势：{trend}"

        prompt = f"""你是一位有爱心、有经验的{'数学' if subject == 'math' else '语文' if subject == 'chinese' else '英语'}教师，正在给学生写个性化评语。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}
- 本次得分：{score}分
- 历史平均分：{avg_score:.1f}分

学生类型：{student_type}
- 语气风格：{strategy['tone']}
- 重点：{strategy['focus']}
- 字数：{strategy['length']}
- 写作原则：{', '.join(strategy['principles'])}

错题情况：
{mistake_summary}

学生画像：
{portrait_summary}

AI 原始评语参考：
{comments}

请以学生类型对应的风格写一段评语，直接返回评语文本（不要 JSON，不要 markdown）。
评语要：
1. 针对具体的错题或表现，而非泛泛而谈
2. 体现对学生的了解（利用画像信息）
3. 给出可操作的改进建议
4. 符合学生类型对应的语气风格
"""

        messages = [
            {"role": "system", "content": "你是一位有爱心、善于鼓励学生的教师。你写的评语因人而异，针对性强。"},
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

    async def generate_batch(self, students_data: list[dict]) -> list[str]:
        """
        批量生成评语

        Args:
            students_data: 每个元素含 student_name, subject, score, mistakes, portrait 等

        Returns:
            评语列表
        """
        comments = []
        for data in students_data:
            comment = await self.generate(
                student_name=data.get("student_name", ""),
                school_level=data.get("school_level", "初中"),
                subject=data.get("subject", "math"),
                score=data.get("score", 0),
                comments=data.get("comments", ""),
                mistakes=data.get("mistakes", []),
                student_portrait=data.get("portrait"),
                avg_score=data.get("avg_score", 70),
            )
            comments.append(comment)
        return comments


# 全局单例工厂
def create_comment_generator(model_service=None):
    """创建评语生成器实例"""
    if model_service is None:
        from services.open_model_service import open_model_service
        model_service = open_model_service
    return CommentGenerator(model_service)