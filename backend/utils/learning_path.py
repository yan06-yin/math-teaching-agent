"""
自适应学习路径推荐

根据学生知识图谱和薄弱点，生成个性化的自适应学习路径。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LearningPathGenerator:
    """学习路径生成器"""

    def __init__(self, model_service):
        self.model_service = model_service

    async def generate(self, student_name: str, school_level: str,
                        weak_points: list[dict], strong_points: list[dict],
                        subject: str = "math", score: float = None,
                        days: int = 14) -> list[dict]:
        """
        生成自适应学习计划

        Args:
            student_name: 学生姓名
            school_level: 学段
            weak_points: 薄弱知识点列表
            strong_points: 优势知识点列表
            subject: 学科
            score: 最近得分
            days: 计划天数

        Returns:
            学习计划列表
        """
        points_str = "\n".join(f"- {p.get('name', '')} (掌握度: {p.get('mastery', 0)})"
                               for p in weak_points[:5])
        strong_str = "\n".join(f"- {p.get('name', '')}" for p in strong_points[:3])

        score_context = ""
        if score is not None:
            if score >= 80:
                score_context = f"\n学生本次得分 {score} 分（优秀），计划应侧重巩固提升、拓展拔高。"
            elif score >= 60:
                score_context = f"\n学生本次得分 {score} 分（中等），计划应重点查漏补缺、夯实薄弱知识点。"
            else:
                score_context = f"\n学生本次得分 {score} 分（待提升），计划应从基础开始、循序渐进。"

        subject_name = {"math": "数学", "chinese": "语文", "english": "英语"}.get(subject, subject)

        prompt = f"""你是一位{subject_name}教育规划师，请为以下学生制定{days}天的个性化学习计划。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}{score_context}

薄弱知识点（按优先级排序）：
{points_str}

优势知识点：
{strong_str}

要求：
1. 每天安排一个主题，从基础到进阶循序渐进
2. 针对最薄弱的知识点安排更多练习时间
3. 每天包含：学习主题、重点内容、时长（分钟）、练习题数量
4. 每7天安排一次阶段性回顾

直接返回纯 JSON（不要 markdown 代码块），格式如下：
{{
  "plan": [
    {{
      "day": 1,
      "topic": "主题名称",
      "focus": "重点内容",
      "duration_minutes": 30,
      "exercises": 5,
      "weak_point_target": "针对的薄弱知识点"
    }}
  ],
  "milestones": ["第7天目标：掌握...", "第14天目标：..."],
  "total_hours": 7.0
}}

注意：
- 计划必须针对具体的薄弱知识点，不能泛泛而谈
- 每天的难度要适当，确保学生能跟上
- 天数从1开始，连续{days}天
- total_hours 是总学习时长（小时）
"""

        messages = [
            {"role": "system", "content": f"你是一位{subject_name}教育规划师。必须以纯 JSON 回复。"},
            {"role": "user", "content": prompt},
        ]

        try:
            result = await self.model_service._chat(messages, max_tokens=4096, timeout=180.0)
            if isinstance(result, dict):
                plan = result.get("plan", [])
                if plan:
                    return plan
            return self._fallback_plan(weak_points, score, days)
        except Exception as e:
            logger.error(f"学习计划生成失败: {e}")
            return self._fallback_plan(weak_points, score, days)

    def _fallback_plan(self, weak_points: list[dict], score: float = None,
                       days: int = 14) -> list[dict]:
        """降级方案：生成简单的学习计划模板"""
        plan = []
        weak_names = [p.get("name", "综合") for p in weak_points[:5]]

        if score is not None and score < 60:
            # 基础薄弱，从基础开始
            topics = ["基础回顾", "概念理解", "基础练习", "错题分析", "巩固提升",
                      "基础测试", "阶段性回顾", "进阶学习", "综合练习", "强化训练",
                      "模拟测试", "查漏补缺", "总复习", "结业评估"]
        elif score is not None and score >= 80:
            topics = ["拓展提升", "综合题训练", "思维拓展", "创新应用", "高阶练习",
                      "专题研究", "阶段性回顾", "挑战题", "跨学科应用", "综合模拟",
                      "弱点攻克", "实战演练", "深度思考", "总结提升"]
        else:
            topics = ["查漏补缺", "基础巩固", "专题训练", "错题回顾", "方法指导",
                      "综合练习", "阶段性回顾", "重点突破", "专项提升", "实战模拟",
                      "弱项强化", "系统复习", "模拟测试", "总结评估"]

        for i in range(days):
            day_num = i + 1
            weak_idx = i % max(len(weak_names), 1)
            plan.append({
                "day": day_num,
                "topic": topics[i % len(topics)],
                "focus": f"重点攻克：{weak_names[weak_idx]}" if weak_names else "综合练习",
                "duration_minutes": 30 if score and score >= 80 else 45,
                "exercises": 8 if score and score >= 80 else 5,
                "weak_point_target": weak_names[weak_idx] if weak_names else "",
            })

        return plan


# 全局单例工厂
def create_learning_path_generator(model_service=None):
    """创建学习路径生成器实例"""
    if model_service is None:
        from services.open_model_service import open_model_service
        model_service = open_model_service
    return LearningPathGenerator(model_service)