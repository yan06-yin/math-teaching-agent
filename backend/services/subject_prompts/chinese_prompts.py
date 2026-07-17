"""
语文/作文学科评分提示词
"""
import json
from .base import BaseSubjectPrompts


class ChinesePrompts(BaseSubjectPrompts):
    """语文/作文评分提示词"""

    def system_prompt(self) -> str:
        return "你是一位经验丰富的初中语文教师，擅长作文评改。必须以纯 JSON 格式回复，不要使用 markdown 代码块。"

    def json_output_example(self) -> dict:
        return {
            "score": 78,
            "total_score": 100,
            "structure": {"score": 75, "feedback": "文章结构完整，有开头、主体和结尾，但段落之间的过渡可以更自然。"},
            "content": {"score": 80, "feedback": "中心思想明确，选材较有新意，对主题的挖掘有一定深度。"},
            "language": {"score": 70, "feedback": "语言通顺，用词基本准确，但句式变化较少，可适当运用修辞手法。"},
            "comments": "整体表现不错！建议在段落衔接和语言表达上多下功夫，多读优秀范文积累好词好句。",
            "knowledge_point": "作文-记叙文",
            "details": [
                {
                    "dimension": "结构",
                    "score": 75,
                    "feedback": "开头点题，结尾呼应，主体部分层次清晰"
                },
                {
                    "dimension": "内容",
                    "score": 80,
                    "feedback": "选取的事例真实感人，能围绕中心展开"
                },
                {
                    "dimension": "语言",
                    "score": 70,
                    "feedback": "语言朴实但缺乏文采，可增加比喻、排比等修辞"
                }
            ]
        }

    def grading_prompt(self, student_name: str, school_level: str,
                       questions_and_answers: str = "",
                       extra_context: str = "") -> str:
        json_example = json.dumps(self.json_output_example(), ensure_ascii=False)
        extra_section = f"\n\n补充信息：\n{extra_context}" if extra_context else ""

        return f"""你是一位经验丰富的初中语文教师，请批改以下语文作业。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}{extra_section}

作业内容：
{questions_and_answers}

请从以下三个维度评分（每项满分 100）：
1. 结构完整性（开头-主体-结尾、段落逻辑、衔接过渡）
2. 内容立意（中心思想明确度、材料新颖度、思想深度）
3. 语言文采（用词准确、句式变化、修辞手法、语言流畅度）

综合得分 = 结构×0.3 + 内容×0.4 + 语言×0.3

直接返回纯 JSON（不要使用 markdown 代码块），格式如下：
{json_example}"""

    def image_grading_prompt(self, student_name: str, school_level: str,
                              extra_context: str = "") -> str:
        json_example = json.dumps(self.json_output_example(), ensure_ascii=False)
        extra_section = f"\n\n补充信息：\n{extra_context}" if extra_context else ""

        return f"""你是一位经验丰富的初中语文教师，请识别图片中的语文/作文内容并进行批改。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}{extra_section}

请先读取图片中的作文内容，然后从以下三个维度评分（每项满分 100）：
1. 结构完整性（开头-主体-结尾、段落逻辑、衔接过渡）
2. 内容立意（中心思想明确度、材料新颖度、思想深度）
3. 语言文采（用词准确、句式变化、修辞手法、语言流畅度）

综合得分 = 结构×0.3 + 内容×0.4 + 语言×0.3

直接返回纯 JSON（不要使用 markdown 代码块），格式如下：
{json_example}"""