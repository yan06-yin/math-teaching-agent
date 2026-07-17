"""
英语学科评分提示词
"""
import json
from .base import BaseSubjectPrompts


class EnglishPrompts(BaseSubjectPrompts):
    """英语评分提示词"""

    def system_prompt(self) -> str:
        return "You are an experienced middle school English teacher. You must respond in pure JSON format, without markdown code blocks."

    def json_output_example(self) -> dict:
        return {
            "score": 82,
            "total_score": 100,
            "grammar": {"score": 78, "feedback": "基本时态使用正确，但有个别主谓一致错误。建议复习第三人称单数的一般现在时变化。"},
            "vocabulary": {"score": 85, "feedback": "词汇使用较为丰富，能够运用一些高级词汇和短语，表达准确。"},
            "coherence": {"score": 80, "feedback": "文章结构清晰，使用了恰当的连接词，段落之间逻辑连贯。"},
            "comments": "Good job! Your writing is clear and well-organized. Focus on subject-verb agreement in simple present tense. Keep practicing!",
            "knowledge_point": "英语-写作",
            "details": [
                {
                    "dimension": "Grammar",
                    "score": 78,
                    "feedback": "Minor tense errors, check subject-verb agreement"
                },
                {
                    "dimension": "Vocabulary",
                    "score": 85,
                    "feedback": "Good word choice, try using more advanced vocabulary"
                },
                {
                    "dimension": "Coherence",
                    "score": 80,
                    "feedback": "Clear structure with good use of transition words"
                }
            ]
        }

    def grading_prompt(self, student_name: str, school_level: str,
                       questions_and_answers: str = "",
                       extra_context: str = "") -> str:
        json_example = json.dumps(self.json_output_example(), ensure_ascii=False)
        extra_section = f"\n\nAdditional context:\n{extra_context}" if extra_context else ""

        return f"""You are an experienced middle school English teacher grading a student's assignment.

Student Info:
- Name: {student_name}
- Grade Level: {school_level}{extra_section}

Assignment Content:
{questions_and_answers}

Please evaluate from three dimensions (each out of 100):
1. Grammar & Accuracy (tense, subject-verb agreement, articles, prepositions, spelling)
2. Vocabulary & Expression (word choice, variety, collocations, appropriateness)
3. Coherence & Organization (logical flow, paragraph structure, linking words)

Overall Score = Grammar×0.4 + Vocabulary×0.3 + Coherence×0.3

Return pure JSON (no markdown code blocks) in the following format:
{json_example}"""

    def image_grading_prompt(self, student_name: str, school_level: str,
                              extra_context: str = "") -> str:
        json_example = json.dumps(self.json_output_example(), ensure_ascii=False)
        extra_section = f"\n\nAdditional context:\n{extra_context}" if extra_context else ""

        return f"""You are an experienced middle school English teacher. Please read the image content and grade the student's English assignment.

Student Info:
- Name: {student_name}
- Grade Level: {school_level}{extra_section}

Read the image content carefully and evaluate from three dimensions (each out of 100):
1. Grammar & Accuracy (tense, subject-verb agreement, articles, prepositions, spelling)
2. Vocabulary & Expression (word choice, variety, collocations, appropriateness)
3. Coherence & Organization (logical flow, paragraph structure, linking words)

Overall Score = Grammar×0.4 + Vocabulary×0.3 + Coherence×0.3

Return pure JSON (no markdown code blocks) in the following format:
{json_example}"""