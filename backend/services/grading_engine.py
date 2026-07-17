import json
import logging
from enum import Enum
from typing import Optional, Type

from .subject_prompts.base import BaseSubjectPrompts
from .subject_prompts.math_prompts import MathPrompts
from .subject_prompts.chinese_prompts import ChinesePrompts
from .subject_prompts.english_prompts import EnglishPrompts

logger = logging.getLogger(__name__)


class Subject(str, Enum):
    MATH = "math"
    CHINESE = "chinese"
    ENGLISH = "english"


class GradingResult:
    def __init__(self, raw: dict, subject: Subject):
        self.subject = subject
        self.score = float(raw.get("score", 0))
        self.comments = raw.get("comments", "")
        self.details = raw.get("details", [])
        self.knowledge_point = raw.get("knowledge_point", "")
        self.raw = raw

    @property
    def correct_count(self) -> int:
        if self.subject == Subject.MATH:
            return int(self.raw.get("correct_count", 0))
        return int(self.raw.get("total_score", 100))

    @property
    def total_count(self) -> int:
        if self.subject == Subject.MATH:
            return int(self.raw.get("total_count", 0))
        return int(self.raw.get("total_score", 100))


_SUBJECT_PROMPT_REGISTRY: dict[Subject, Type[BaseSubjectPrompts]] = {
    Subject.MATH: MathPrompts,
    Subject.CHINESE: ChinesePrompts,
    Subject.ENGLISH: EnglishPrompts,
}


def get_subject_prompts(subject: Subject) -> BaseSubjectPrompts:
    cls = _SUBJECT_PROMPT_REGISTRY.get(subject)
    if not cls:
        logger.warning(f"学科 {subject} 无对应提示词，默认使用数学")
        cls = MathPrompts
    return cls()


def parse_grading_result(raw: dict, subject: Subject) -> GradingResult:
    if isinstance(raw, dict) and raw.get("_parse_error"):
        logger.warning(f"评分解析失败: {raw['_parse_error']}")
    return GradingResult(raw, subject)