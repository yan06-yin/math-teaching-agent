"""
评分提示词基类
"""
from abc import ABC, abstractmethod


class BaseSubjectPrompts(ABC):
    """学科提示词基类，每个学科实现自己的评分提示词"""

    @abstractmethod
    def system_prompt(self) -> str:
        """系统提示词"""
        ...

    @abstractmethod
    def grading_prompt(self, student_name: str, school_level: str,
                       questions_and_answers: str = "",
                       extra_context: str = "") -> str:
        """评分提示词（纯文本模式）"""
        ...

    @abstractmethod
    def image_grading_prompt(self, student_name: str, school_level: str,
                              extra_context: str = "") -> str:
        """图片评分提示词（多模态模式）"""
        ...

    @abstractmethod
    def json_output_example(self) -> dict:
        """JSON 输出格式示例"""
        ...