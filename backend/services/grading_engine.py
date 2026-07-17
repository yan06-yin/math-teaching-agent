"""
学科自适应评分引擎

使用策略模式（Strategy Pattern）实现不同学科的自适应评分。
每个学科有自己的评分策略，通过 Subject 枚举选择。
"""

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
    """支持的学科"""
    MATH = "math"
    CHINESE = "chinese"
    ENGLISH = "english"


class GradingResult:
    """评分结果"""
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


# 学科提示词注册表
_SUBJECT_PROMPT_REGISTRY: dict[Subject, Type[BaseSubjectPrompts]] = {
    Subject.MATH: MathPrompts,
    Subject.CHINESE: ChinesePrompts,
    Subject.ENGLISH: EnglishPrompts,
}


def get_subject_prompts(subject: Subject) -> BaseSubjectPrompts:
    """获取学科对应的提示词实例"""
    prompt_cls = _SUBJECT_PROMPT_REGISTRY.get(subject)
    if not prompt_cls:
        logger.warning(f"未找到学科 {subject} 的提示词，默认使用数学")
        prompt_cls = MathPrompts
    return prompt_cls()


def parse_grading_result(raw: dict, subject: Subject) -> GradingResult:
    """解析评分结果"""
    if isinstance(raw, dict) and raw.get("_parse_error"):
        logger.warning(f"评分结果解析失败: {raw['_parse_error']}")
    return GradingResult(raw, subject)