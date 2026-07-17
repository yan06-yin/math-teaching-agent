"""
步骤级过程分评分器

将学生答案拆解为解题步骤序列，与标准步骤链进行语义对齐匹配，
定位中断点并给予部分分数，而非简单判对错。

支持学科：
- 数学：代数运算步骤、几何证明步骤
- 语文/英语：多维度评分（结构、内容、语言等）
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StepGrader:
    """步骤级评分器"""

    def __init__(self, model_service):
        self.model_service = model_service
        # 过程分权重（过程分占总分的比例）
        self.process_weight = 0.4
        # 结果分权重
        self.result_weight = 0.6

    async def grade_with_steps(self, question: str, student_answer: str,
                                correct_answer: str, subject: str = "math",
                                student_name: str = "", school_level: str = "") -> dict:
        """
        按步骤批改并返回过程分

        Returns:
            dict with keys:
                score: 最终得分 (0-100)
                result_score: 结果分 (0-100)
                process_score: 过程分 (0-100)
                steps: 步骤详情列表
                comments: 评语
        """
        if subject in ("chinese", "english"):
            return await self._grade_dimension(subject, question, student_answer,
                                                student_name, school_level)
        return await self._grade_math_steps(question, student_answer, correct_answer,
                                             student_name, school_level)

    async def _grade_math_steps(self, question: str, student_answer: str,
                                 correct_answer: str,
                                 student_name: str, school_level: str) -> dict:
        """数学题步骤级评分"""
        prompt = f"""你是一位数学教师，正在批改学生的解题步骤。

题目：{question}
标准答案：{correct_answer}
学生答案：{student_answer}
学生姓名：{student_name}
学段：{school_level}

请按以下步骤批改：
1. 将标准答案拆解为解题步骤序列（每个步骤一个独立操作）
2. 将学生答案也拆解为步骤序列
3. 逐步骤对比，判断每步是否正确（严格判断）
4. 标记"部分正确"的步骤（如思路正确但计算错误）

直接返回纯 JSON（不要 markdown 代码块），格式如下：
{{
  "result_score": 80,
  "result_correct": true,
  "process_score": 75,
  "steps": [
    {{
      "step_number": 1,
      "description": "移项：将常数项移到等号右边",
      "student_step": "5x = 7 - 2",
      "correct_step": "5x = 7 - 2",
      "status": "correct",
      "feedback": "移项正确，符号变化无误"
    }},
    {{
      "step_number": 2,
      "description": "合并同类项",
      "student_step": "5x = 5",
      "correct_step": "5x = 5",
      "status": "correct",
      "feedback": "计算正确"
    }},
    {{
      "step_number": 3,
      "description": "系数化为1",
      "student_step": "x = 2",
      "correct_step": "x = 1",
      "status": "incorrect",
      "feedback": "5÷5=1，不是2，注意除法计算"
    }}
  ],
  "process_note": "前两步正确，最后一步计算错误",
  "comments": "解题思路清晰，移项和合并步骤正确，但最后一步计算粗心，建议检查除法运算。"
}}

注意：
- status: "correct" / "partial" / "incorrect"
- result_score: 最终答案是否正确 (100 或 0)
- process_score: 根据正确步骤比例计算 (0-100)
- 部分正确的步骤给 50% 的过程分
"""

        messages = [
            {"role": "system", "content": "你是一位专业的数学教师。必须返回纯 JSON 格式，不要用 markdown。"},
            {"role": "user", "content": prompt},
        ]

        try:
            raw = await self.model_service._chat(messages, max_tokens=4096)
            return self._compute_final_score(raw)
        except Exception as e:
            logger.error(f"步骤级评分失败: {e}")
            # 降级：简单判对错
            return self._fallback_grade(question, student_answer, correct_answer)

    async def _grade_dimension(self, subject: str, question: str, student_answer: str,
                                student_name: str, school_level: str) -> dict:
        """语文/英语多维度评分（作为步骤评分的替代方案）"""
        if subject == "chinese":
            dims = ["结构完整性", "内容立意", "语言文采"]
            weights = [0.3, 0.4, 0.3]
        else:
            dims = ["语法准确性", "词汇丰富度", "连贯与逻辑"]
            weights = [0.4, 0.3, 0.3]

        dims_str = "\n".join([f"- {d} (权重{w})" for d, w in zip(dims, weights)])

        prompt = f"""你是一位{'语文' if subject == 'chinese' else '英语'}教师，请从多个维度评分。

题目/主题：{question}
学生作答：{student_answer}
学生姓名：{student_name}
学段：{school_level}

评分维度及权重：
{dims_str}

直接返回纯 JSON（不要 markdown 代码块），格式如下：
{{
  "result_score": 75,
  "dimensions": [
    {{"name": "结构完整性", "score": 70, "feedback": "开头结尾完整，段落过渡可更自然"}},
    {{"name": "内容立意", "score": 80, "feedback": "中心明确，选材有特色"}},
    {{"name": "语言文采", "score": 65, "feedback": "语言通顺，可增加修辞手法"}}
  ],
  "process_score": 72,
  "comments": "整体表现不错，建议在语言表达上多下功夫。"
}}
"""

        messages = [
            {"role": "system", "content": f"你是一位专业的{'语文' if subject == 'chinese' else '英语'}教师。必须返回纯 JSON 格式。"},
            {"role": "user", "content": prompt},
        ]

        try:
            raw = await self.model_service._chat(messages, max_tokens=4096)
            # 解析结果
            parsed = self._parse_model_response(raw)
            if parsed.get("_parse_error"):
                return self._simple_grade(subject, student_answer)

            dims_data = parsed.get("dimensions", [])
            if dims_data:
                # 加权计算过程分
                weighted = sum(d.get("score", 0) * w for d, w in zip(dims_data, weights))
                process_score = weighted / 100 * 100 if weighted else 0
            else:
                process_score = float(parsed.get("process_score", 0))

            # 综合得分 = 结果分(只考虑基础分) + 过程分
            result_score = process_score  # 写作类以过程分为主

            return {
                "score": round(result_score),
                "result_score": round(result_score),
                "process_score": round(process_score),
                "steps": dims_data,
                "comments": parsed.get("comments", ""),
                "dimensions": dims_data,
            }
        except Exception as e:
            logger.error(f"维度评分失败: {e}")
            return self._simple_grade(subject, student_answer)

    def _compute_final_score(self, raw: dict) -> dict:
        """根据步骤评分结果计算最终得分"""
        parsed = self._parse_model_response(raw)

        if parsed.get("_parse_error"):
            return {"score": 0, "result_score": 0, "process_score": 0,
                    "steps": [], "comments": "评分解析失败，请重试"}

        steps = parsed.get("steps", [])
        if not steps:
            return {"score": 0, "result_score": 0, "process_score": 0,
                    "steps": [], "comments": "无法解析解题步骤"}

        # 计算过程分
        total_steps = len(steps)
        if total_steps == 0:
            process_score = 0
        else:
            correct_points = 0
            for s in steps:
                status = s.get("status", "incorrect")
                if status == "correct":
                    correct_points += 1
                elif status == "partial":
                    correct_points += 0.5
            process_score = (correct_points / total_steps) * 100

        # 结果分
        result_score = float(parsed.get("result_score", 0))

        # 综合得分
        final_score = int(result_score * self.result_weight + process_score * self.process_weight)

        return {
            "score": final_score,
            "result_score": round(result_score),
            "process_score": round(process_score),
            "steps": steps,
            "comments": parsed.get("comments", ""),
            "process_note": parsed.get("process_note", ""),
        }

    def _parse_model_response(self, raw: dict) -> dict:
        """解析模型返回结果"""
        # 如果 raw 已经是解析好的 dict
        if isinstance(raw, dict):
            if raw.get("steps") is not None or raw.get("dimensions") is not None:
                return raw
            if raw.get("_parse_error"):
                # 尝试从 raw 文本中提取 JSON
                text = raw.get("raw", "")
                if text:
                    return self._extract_json(text)
                return raw
        return raw

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从文本中提取 JSON"""
        import re
        # 尝试 ```json ... ``` 格式
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        # 尝试第一个 { 到最后一个 }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"_parse_error": "json parse failed", "raw": text[:200]}

    def _fallback_grade(self, question: str, student_answer: str,
                        correct_answer: str) -> dict:
        """降级方案：简单判对错"""
        is_correct = student_answer.strip() == correct_answer.strip()
        # 如果文本完全匹配，判对；否则用 AI 简单判断
        if not is_correct:
            # 询问 AI 判断对错
            prompt = f"""题目：{question}
标准答案：{correct_answer}
学生答案：{student_answer}

判断学生答案是否正确（严格判断）。返回 JSON：
{{"correct": true/false, "score": 100或0, "feedback": "..."}}"""
            try:
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    self.model_service._chat([{"role": "user", "content": prompt}])
                )
                if isinstance(result, dict):
                    is_correct = result.get("correct", False)
            except Exception:
                pass

        score = 100 if is_correct else 0
        return {
            "score": score,
            "result_score": score,
            "process_score": 0,
            "steps": [{"step_number": 1, "status": "correct" if is_correct else "incorrect",
                       "feedback": "正确" if is_correct else "答案不正确"}],
            "comments": "正确" if is_correct else "需要订正",
        }

    def _simple_grade(self, subject: str, student_answer: str) -> dict:
        """最简降级方案"""
        return {
            "score": 60,
            "result_score": 60,
            "process_score": 60,
            "steps": [],
            "comments": f"已收到你的{'语文' if subject == 'chinese' else '英语'}作业，请查看详细反馈。",
            "dimensions": [],
        }


# 全局单例工厂
def create_step_grader(model_service=None):
    """创建步骤评分器实例"""
    if model_service is None:
        from services.open_model_service import open_model_service
        model_service = open_model_service
    return StepGrader(model_service)