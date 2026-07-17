import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class StepGrader:
    """步骤级评分：把学生答案拆成步骤，和标准步骤对比，按步给分"""

    def __init__(self, model_service):
        self.model_service = model_service
        self.process_weight = 0.4
        self.result_weight = 0.6

    async def grade_with_steps(self, question: str, student_answer: str,
                                correct_answer: str, subject: str = "math",
                                student_name: str = "", school_level: str = "") -> dict:
        if subject in ("chinese", "english"):
            return await self._grade_dimension(subject, question, student_answer,
                                                student_name, school_level)
        return await self._grade_math_steps(question, student_answer, correct_answer,
                                             student_name, school_level)

    async def _grade_math_steps(self, question: str, student_answer: str,
                                 correct_answer: str,
                                 student_name: str, school_level: str) -> dict:
        prompt = f"""你是一位数学教师，正在批改学生的解题步骤。

题目：{question}
标准答案：{correct_answer}
学生答案：{student_answer}
学生姓名：{student_name}
学段：{school_level}

请按以下步骤批改：
1. 将标准答案拆解为解题步骤序列
2. 将学生答案也拆解为步骤序列
3. 逐步骤对比，判断每步是否正确
4. 标记"部分正确"的步骤（如思路正确但计算错误）

直接返回纯 JSON（不要 markdown 代码块），格式如下：
{{
  "result_score": 80,
  "result_correct": true,
  "process_score": 75,
  "steps": [
    {{"step_number": 1, "description": "移项", "student_step": "5x = 7 - 2", "correct_step": "5x = 7 - 2", "status": "correct", "feedback": "移项正确"}},
    {{"step_number": 2, "description": "合并同类项", "student_step": "5x = 5", "correct_step": "5x = 5", "status": "correct", "feedback": "计算正确"}},
    {{"step_number": 3, "description": "系数化为1", "student_step": "x = 2", "correct_step": "x = 1", "status": "incorrect", "feedback": "5÷5=1，不是2"}}
  ],
  "process_note": "前两步正确，最后一步计算错误",
  "comments": "思路清晰，但最后一步计算粗心"
}}

注意：
- status: "correct" / "partial" / "incorrect"
- result_score: 最终答案是否正确 (100 或 0)
- process_score: 根据正确步骤比例计算 (0-100)
- 部分正确的步骤给 50% 的过程分
"""

        messages = [
            {"role": "system", "content": "你是一位数学教师。返回纯 JSON，不要 markdown。"},
            {"role": "user", "content": prompt},
        ]

        try:
            raw = await self.model_service._chat(messages, max_tokens=4096)
            return self._compute_final_score(raw)
        except Exception as e:
            logger.error(f"步骤评分失败: {e}")
            return self._fallback_grade(question, student_answer, correct_answer)

    async def _grade_dimension(self, subject: str, question: str, student_answer: str,
                                student_name: str, school_level: str) -> dict:
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
    {{"name": "结构完整性", "score": 70, "feedback": "段落过渡可更自然"}},
    {{"name": "内容立意", "score": 80, "feedback": "中心明确，选材有特色"}},
    {{"name": "语言文采", "score": 65, "feedback": "语言通顺，可增加修辞手法"}}
  ],
  "process_score": 72,
  "comments": "整体不错，建议在语言表达上多下功夫。"
}}
"""

        messages = [
            {"role": "system", "content": f"你是一位{'语文' if subject == 'chinese' else '英语'}教师。返回纯 JSON 格式。"},
            {"role": "user", "content": prompt},
        ]

        try:
            raw = await self.model_service._chat(messages, max_tokens=4096)
            parsed = self._parse_model_response(raw)
            if parsed.get("_parse_error"):
                return self._simple_grade(subject, student_answer)

            dims_data = parsed.get("dimensions", [])
            if dims_data:
                weighted = sum(d.get("score", 0) * w for d, w in zip(dims_data, weights))
                process_score = weighted / 100 * 100 if weighted else 0
            else:
                process_score = float(parsed.get("process_score", 0))

            result_score = process_score

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
        parsed = self._parse_model_response(raw)

        if parsed.get("_parse_error"):
            return {"score": 0, "result_score": 0, "process_score": 0,
                    "steps": [], "comments": "评分解析失败"}

        steps = parsed.get("steps", [])
        if not steps:
            return {"score": 0, "result_score": 0, "process_score": 0,
                    "steps": [], "comments": "无法解析解题步骤"}

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

        result_score = float(parsed.get("result_score", 0))
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
        if isinstance(raw, dict):
            if raw.get("steps") is not None or raw.get("dimensions") is not None:
                return raw
            if raw.get("_parse_error"):
                text = raw.get("raw", "")
                if text:
                    return self._extract_json(text)
                return raw
        return raw

    @staticmethod
    def _extract_json(text: str) -> dict:
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
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
        is_correct = student_answer.strip() == correct_answer.strip()
        if not is_correct:
            prompt = f"""题目：{question}
标准答案：{correct_answer}
学生答案：{student_answer}
判断学生答案是否正确。返回 JSON：{{"correct": true/false, "score": 100或0, "feedback": "..."}}"""
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
        return {
            "score": 60,
            "result_score": 60,
            "process_score": 60,
            "steps": [],
            "comments": "已收到作业，请查看详细反馈。",
            "dimensions": [],
        }


def create_step_grader(model_service=None):
    if model_service is None:
        from services.open_model_service import open_model_service
        model_service = open_model_service
    return StepGrader(model_service)