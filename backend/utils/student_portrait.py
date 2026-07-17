"""
学生多维画像构建器

从学生的历史作业数据、考试数据、错题记录中提取特征，
构建学生画像，用于个性化评语生成和学情分析。
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class StudentPortrait:
    """学生多维画像"""

    def __init__(self, student_id: int, name: str, school_level: str = "初中"):
        self.student_id = student_id
        self.name = name
        self.school_level = school_level

        # 各学科成绩
        self.scores: dict[str, list[float]] = {"math": [], "chinese": [], "english": []}
        # 各学科平均分
        self.avg_scores: dict[str, float] = {}
        # 成绩趋势
        self.trends: dict[str, str] = {}  # rising / stable / falling
        # 薄弱知识点（按学科）
        self.weak_points: dict[str, list[dict]] = {"math": [], "chinese": [], "english": []}
        # 优势知识点
        self.strong_points: dict[str, list[str]] = {"math": [], "chinese": [], "english": []}
        # 上次评语关注点
        self.last_comment_focus: Optional[str] = None
        # 学习风格预估
        self.learning_style: str = "常规"
        # 班级排名上下文
        self.class_rank_context: str = ""

    def to_dict(self) -> dict:
        """转为字典"""
        return {
            "student_id": self.student_id,
            "name": self.name,
            "school_level": self.school_level,
            "avg_scores": self.avg_scores,
            "trends": self.trends,
            "weak_points": {k: v[:5] for k, v in self.weak_points.items()},
            "strong_points": {k: v[:3] for k, v in self.strong_points.items()},
            "learning_style": self.learning_style,
            "last_comment_focus": self.last_comment_focus,
        }

    def summary(self, subject: Optional[str] = None) -> str:
        """生成画像摘要文本（用于评语提示词上下文）"""
        if subject:
            parts = [
                f"该生{self.name}，{self.school_level}学段",
            ]
            avg = self.avg_scores.get(subject, 0)
            if avg:
                parts.append(f"{subject}学科历史平均分：{avg:.1f}")
            trend = self.trends.get(subject, "")
            if trend:
                parts.append(f"成绩趋势：{trend}")
            weaks = self.weak_points.get(subject, [])[:3]
            if weaks:
                weak_str = "、".join([w.get("point", "") for w in weaks])
                parts.append(f"常见薄弱点：{weak_str}")
            strongs = self.strong_points.get(subject, [])[:2]
            if strongs:
                parts.append(f"优势：{'、'.join(strongs)}")
            if self.last_comment_focus:
                parts.append(f"上次评语关注方向：{self.last_comment_focus}")
            return "；".join(parts)

        # 全学科摘要
        lines = [f"学生{self.name}（{self.school_level}）整体画像："]
        for subj in ["math", "chinese", "english"]:
            avg = self.avg_scores.get(subj, 0)
            trend = self.trends.get(subj, "")
            if avg or trend:
                subj_name = {"math": "数学", "chinese": "语文", "english": "英语"}.get(subj, subj)
                lines.append(f"- {subj_name}：均分{avg:.1f}，趋势{trend}")
        return "\n".join(lines)


class StudentPortraitBuilder:
    """从数据库构建学生画像"""

    def __init__(self, db_session):
        self.db = db_session

    async def build_portrait(self, student_id: int, name: str,
                              school_level: str = "初中") -> StudentPortrait:
        """构建学生完整画像"""
        from models import HomeworkSubmission, ErrorRecord, ExamAttempt
        from sqlalchemy import select, func

        portrait = StudentPortrait(student_id, name, school_level)

        # 1. 收集各学科成绩
        for subject in ["math", "chinese", "english"]:
            scores = []
            # 从作业中获取成绩
            result = await self.db.execute(
                select(HomeworkSubmission.score)
                .filter(
                    HomeworkSubmission.student_id == student_id,
                    HomeworkSubmission.subject == subject,
                    HomeworkSubmission.status == "done",
                    HomeworkSubmission.is_deleted == False,
                    HomeworkSubmission.score > 0,
                )
                .order_by(HomeworkSubmission.created_at.desc())
                .limit(20)
            )
            scores.extend([r[0] for r in result.fetchall() if r[0] and r[0] > 0])

            portrait.scores[subject] = scores

            if scores:
                portrait.avg_scores[subject] = sum(scores) / len(scores)
                portrait.trends[subject] = self._compute_trend(scores)
            else:
                portrait.avg_scores[subject] = 0
                portrait.trends[subject] = "stable"

        # 2. 收集错题知识点
        for subject in ["math", "chinese", "english"]:
            # 直接查 ErrorRecord，按知识点分组统计错误次数
            all_errors = await self.db.execute(
                select(ErrorRecord.knowledge_point, func.sum(ErrorRecord.error_count))
                .filter(
                    ErrorRecord.student_id == student_id,
                )
                .group_by(ErrorRecord.knowledge_point)
                .order_by(func.sum(ErrorRecord.error_count).desc())
                .limit(10)
            )
            errors = []
            strongs = []
            for row in all_errors.fetchall():
                kp = row[0]
                count = row[1] or 1
                # 简化：暂时无法区分学科，全部加入
                errors.append({"point": kp, "count": count})
                if count <= 1:
                    strongs.append(kp)

            # 将错误按规律分类（简单启发式）
            for err in errors:
                subj = self._guess_subject(err["point"])
                if subj == subject:
                    portrait.weak_points[subject].append(err)

            portrait.strong_points[subject] = strongs[:3]

        return portrait

    def _compute_trend(self, scores: list[float]) -> str:
        """计算成绩趋势"""
        if len(scores) < 3:
            return "stable"
        # 比较前半段和后半段的平均分
        mid = len(scores) // 2
        first_half = sum(scores[:mid]) / mid if mid > 0 else 0
        second_half = sum(scores[mid:]) / (len(scores) - mid) if (len(scores) - mid) > 0 else 0
        diff = second_half - first_half
        if diff > 5:
            return "rising"
        elif diff < -5:
            return "falling"
        return "stable"

    def _guess_subject(self, knowledge_point: str) -> str:
        """根据知识点名称猜测学科"""
        math_keywords = ["方程", "函数", "几何", "三角", "代数", "概率", "统计",
                         "勾股", "向量", "数列", "导数", "积分", "不等式"]
        chinese_keywords = ["作文", "阅读", "文言", "古诗", "修辞", "病句",
                            "成语", "字音", "字形", "文学", "默写"]
        english_keywords = ["时态", "语态", "从句", "非谓语", "词汇", "写作",
                            "完形", "阅读", "语法", "英语-"]

        lower = knowledge_point.lower()
        for kw in math_keywords:
            if kw in lower:
                return "math"
        for kw in chinese_keywords:
            if kw in lower:
                return "chinese"
        for kw in english_keywords:
            if kw in lower:
                return "english"
        return "math"  # 默认数学


# 全局单例
_portrait_builder_instance = None


def get_portrait_builder(db_session=None):
    """获取画像构建器实例"""
    global _portrait_builder_instance
    if db_session:
        _portrait_builder_instance = StudentPortraitBuilder(db_session)
    return _portrait_builder_instance