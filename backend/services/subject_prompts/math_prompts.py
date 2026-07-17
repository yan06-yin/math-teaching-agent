"""
数学学科评分提示词
"""
import json
from .base import BaseSubjectPrompts


class MathPrompts(BaseSubjectPrompts):
    """数学评分提示词"""

    def system_prompt(self) -> str:
        return "你是一位经验丰富的数学教师。必须以纯 JSON 格式回复，不要使用 markdown 代码块。"

    def json_output_example(self) -> dict:
        return {
            "score": 85,
            "correct_count": 4,
            "total_count": 5,
            "comments": "整体表现良好，但在代数运算方面需要加强。建议多练习一元二次方程的因式分解。",
            "details": [
                {
                    "question": "第1题：2x+3=7，求x",
                    "correct": True,
                    "feedback": "正确，解题步骤清晰。",
                    "student_answer": "x=2",
                    "correct_answer": "x=2",
                    "explanation": ""
                },
                {
                    "question": "第2题：x²-4x+3=0",
                    "correct": False,
                    "student_answer": "x=1",
                    "correct_answer": "x=1或x=3",
                    "feedback": "漏了一个解，注意因式分解要完整。",
                    "explanation": "因式分解为(x-1)(x-3)=0，所以x=1或x=3"
                }
            ]
        }

    def grading_prompt(self, student_name: str, school_level: str,
                       questions_and_answers: str = "",
                       extra_context: str = "") -> str:
        json_example = json.dumps(self.json_output_example(), ensure_ascii=False)
        extra_section = f"\n\n补充信息：\n{extra_context}" if extra_context else ""

        return f"""你是一位经验丰富的数学老师，请批改以下数学作业。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}{extra_section}

作业内容：
{questions_and_answers}

请逐题批改，注意：
- 对于有多步骤的题目，检查每个步骤的正确性，给予过程分
- 部分正确的解题过程应给予部分分数
- 计算错误与概念错误应区分对待

直接返回纯 JSON（不要使用 markdown 代码块），格式如下：
{json_example}"""

    def image_grading_prompt(self, student_name: str, school_level: str,
                              extra_context: str = "") -> str:
        json_example = json.dumps(self.json_output_example(), ensure_ascii=False)
        extra_section = f"\n\n补充信息：\n{extra_context}" if extra_context else ""

        return f"""你是一位经验丰富的数学老师，请识别图片中的数学题目并进行批改。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}{extra_section}

请先读取图片中的所有数学题目，然后逐题批改。

注意：
- 对于有多步骤的题目，检查每个步骤的正确性，给予过程分
- 部分正确的解题过程应给予部分分数
- score 是 0-100 的整数
- correct_count 和 total_count 必须准确

直接返回纯 JSON（不要使用 markdown 代码块），格式如下：
{json_example}"""