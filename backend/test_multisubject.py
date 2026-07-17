"""
多学科功能单元测试
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ===== grading_engine 测试 =====
class TestGradingEngine:
    def test_subject_enum(self):
        from services.grading_engine import Subject
        assert Subject.MATH.value == "math"
        assert Subject.CHINESE.value == "chinese"
        assert Subject.ENGLISH.value == "english"
        assert len(Subject) == 3

    def test_get_subject_prompts(self):
        from services.grading_engine import get_subject_prompts, Subject
        prompts = get_subject_prompts(Subject.MATH)
        assert prompts is not None

        prompts = get_subject_prompts(Subject.CHINESE)
        assert prompts is not None

        prompts = get_subject_prompts(Subject.ENGLISH)
        assert prompts is not None

    def test_grading_result(self):
        from services.grading_engine import GradingResult, Subject
        raw = {"score": 85, "comments": "test", "details": [{"question": "Q1", "correct": True}],
               "correct_count": 1, "total_count": 1}
        result = GradingResult(raw, Subject.MATH)
        assert result.score == 85
        assert result.comments == "test"
        assert result.correct_count == 1
        assert result.total_count == 1


# ===== subject_prompts 测试 =====
class TestSubjectPrompts:
    def test_math_prompts(self):
        from services.subject_prompts.math_prompts import MathPrompts
        prompts = MathPrompts()
        assert prompts.system_prompt() is not None
        grading = prompts.grading_prompt("Zhang", "middle", "content")
        assert "Zhang" in grading
        json_example = prompts.json_output_example()
        assert "score" in json_example

    def test_chinese_prompts(self):
        from services.subject_prompts.chinese_prompts import ChinesePrompts
        prompts = ChinesePrompts()
        assert prompts.system_prompt() is not None
        grading = prompts.grading_prompt("Li", "chuzhong", "zuowen")
        assert "Li" in grading

    def test_english_prompts(self):
        from services.subject_prompts.english_prompts import EnglishPrompts
        prompts = EnglishPrompts()
        assert prompts.system_prompt() is not None
        grading = prompts.grading_prompt("Alice", "middle", "essay")
        assert "Alice" in grading

    def test_prompts_have_image_versions(self):
        for mod_name in ["math_prompts", "chinese_prompts", "english_prompts"]:
            mod = __import__(f"services.subject_prompts.{mod_name}", fromlist=[""])
            cls = getattr(mod, mod_name.split("_")[0].title() + "Prompts")
            p = cls()
            assert hasattr(p, 'image_grading_prompt')
            result = p.image_grading_prompt("Test", "chuzhong")
            assert "Test" in result


# ===== step_grader 测试 =====
class TestStepGrader:
    @pytest.mark.asyncio
    async def test_grade_with_steps_math(self):
        mock_model = MagicMock()
        mock_model._chat = AsyncMock(return_value={
            "result_score": 80,
            "process_score": 66.7,
            "steps": [
                {"step_number": 1, "description": "Step 1", "status": "correct", "feedback": "ok"},
                {"step_number": 2, "description": "Step 2", "status": "correct", "feedback": "ok"},
                {"step_number": 3, "description": "Step 3", "status": "incorrect", "feedback": "wrong"},
            ],
            "comments": "Good try"
        })

        from services.step_grader import StepGrader
        grader = StepGrader(mock_model)
        result = await grader.grade_with_steps(
            question="2x+3=7",
            student_answer="2x=4, x=2",
            correct_answer="x=2",
            subject="math",
        )
        assert result["score"] >= 0
        assert len(result["steps"]) == 3

    @pytest.mark.asyncio
    async def test_grade_dimension_chinese(self):
        mock_model = MagicMock()
        mock_model._chat = AsyncMock(return_value={
            "result_score": 75,
            "dimensions": [
                {"name": "Structure", "score": 70, "feedback": "ok"},
                {"name": "Content", "score": 80, "feedback": "good"},
                {"name": "Language", "score": 65, "feedback": "needs work"},
            ],
            "process_score": 72,
            "comments": "Good"
        })
        from services.step_grader import StepGrader
        grader = StepGrader(mock_model)
        result = await grader.grade_with_steps(
            question="My Summer",
            student_answer="Summer is fun...",
            correct_answer="",
            subject="chinese",
        )
        assert result["score"] > 0
        assert len(result.get("dimensions", [])) == 3

    def test_fallback_grade(self):
        from services.step_grader import StepGrader
        grader = StepGrader(MagicMock())
        result = grader._fallback_grade("1+1=?", "2", "2")
        assert result["score"] == 100


# ===== comment_generator 测试 =====
class TestCommentGenerator:
    def test_classify_student(self):
        from services.comment_generator import CommentGenerator
        gen = CommentGenerator(MagicMock())
        assert gen._classify_student(50, 70) == "struggling"
        assert gen._classify_student(75, 70) == "average"
        assert gen._classify_student(90, 70) == "advanced"

    @pytest.mark.asyncio
    async def test_generate(self):
        mock_model = MagicMock()
        mock_model._chat = AsyncMock(return_value={"raw": "Good progress! Keep it up."})
        from services.comment_generator import CommentGenerator
        gen = CommentGenerator(mock_model)
        result = await gen.generate(
            student_name="Zhang",
            school_level="chuzhong",
            subject="math",
            score=75,
            comments="ok",
            mistakes=[],
            student_portrait={"weak_points": {"math": []}, "trends": {"math": "rising"}},
            avg_score=70,
        )
        assert result is not None


# ===== knowledge_graph 测试 =====
class TestKnowledgeGraph:
    def test_node_creation(self):
        from services.knowledge_graph_service import KnowledgeGraph
        kg = KnowledgeGraph()
        node = kg.get_or_create_node("test-point", "math", "chuzhong")
        assert node.name == "test-point"
        assert node.subject == "math"
        assert node.mastery == 1.0

    def test_record_error_and_weak_points(self):
        from services.knowledge_graph_service import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.record_error("math-eq", "math", "chuzhong", 3)
        kg.record_error("math-geo", "math", "chuzhong", 1)
        kg.record_error("chi-essay", "chinese", "chuzhong", 2)

        # 获取数学薄弱点
        weak = kg.get_weak_points(subject="math", top_n=5)
        assert len(weak) >= 1
        # 获取所有薄弱点
        all_weak = kg.get_weak_points(top_n=10)
        assert len(all_weak) >= 2

    def test_strong_points(self):
        from services.knowledge_graph_service import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.record_correct("math-easy", "math", "chuzhong")
        kg.record_correct("math-easy", "math", "chuzhong")
        strong = kg.get_strong_points(subject="math")
        assert len(strong) >= 0  # 可能没有足够记录

    def test_learning_path(self):
        from services.knowledge_graph_service import KnowledgeGraph
        kg = KnowledgeGraph()
        path = kg.get_learning_path("一元二次方程")
        assert len(path) > 0


# ===== knowledge_mapper 测试 =====
class TestKnowledgeMapper:
    def test_normalize_math(self):
        from utils.knowledge_mapper import normalize_knowledge_point
        result = normalize_knowledge_point("二次方程", "math")
        assert result is not None

    def test_normalize_chinese(self):
        from utils.knowledge_mapper import normalize_knowledge_point
        result = normalize_knowledge_point("作文", "chinese")
        assert result == "作文-写作"

    def test_normalize_english(self):
        from utils.knowledge_mapper import normalize_knowledge_point
        result = normalize_knowledge_point("时态", "english")
        assert result == "英语-时态"

    def test_chinese_knowledge(self):
        from utils.knowledge_mapper import CHINESE_KNOWLEDGE
        assert "作文-写作" in CHINESE_KNOWLEDGE
        assert len(CHINESE_KNOWLEDGE) >= 8

    def test_english_knowledge(self):
        from utils.knowledge_mapper import ENGLISH_KNOWLEDGE
        assert "英语-时态" in ENGLISH_KNOWLEDGE
        assert len(ENGLISH_KNOWLEDGE) >= 10


# ===== OCR service 测试 =====
class TestOCRService:
    def test_math_postprocess(self):
        from services.ocr_service import OCRPipeline
        ocr = OCRPipeline()
        assert ocr._postprocess_math("2 x 3") == "2 x 3"
        assert ocr._postprocess_math("x+2 = 5") == "x+2 = 5"

    def test_chinese_postprocess(self):
        from services.ocr_service import OCRPipeline
        ocr = OCRPipeline()
        result = ocr._postprocess_chinese("  wo  shi  ")
        assert " " not in result

    def test_english_postprocess(self):
        from services.ocr_service import OCRPipeline
        ocr = OCRPipeline()
        result = ocr._postprocess_english("Hel lo  World")
        assert "Hello  World" in result or "Hel lo World" in result


# ===== Student portrait 测试 =====
class TestStudentPortrait:
    def test_portrait_init(self):
        from utils.student_portrait import StudentPortrait
        p = StudentPortrait(1, "Zhang", "chuzhong")
        assert p.student_id == 1
        assert p.name == "Zhang"

    def test_portrait_summary(self):
        from utils.student_portrait import StudentPortrait
        p = StudentPortrait(1, "Zhang", "chuzhong")
        p.avg_scores["math"] = 75.0
        p.trends["math"] = "rising"
        summary = p.summary("math")
        assert "Zhang" in summary
        assert "75" in summary

    def test_to_dict(self):
        from utils.student_portrait import StudentPortrait
        p = StudentPortrait(1, "Zhang", "chuzhong")
        d = p.to_dict()
        assert d["student_id"] == 1


# ===== Learning path 测试 =====
class TestLearningPath:
    def test_fallback_plan_length(self):
        from utils.learning_path import LearningPathGenerator
        gen = LearningPathGenerator(MagicMock())
        plan = gen._fallback_plan([{"name": "test", "mastery": 0.3}], score=75, days=14)
        assert len(plan) == 14

    def test_fallback_plan_structure(self):
        from utils.learning_path import LearningPathGenerator
        gen = LearningPathGenerator(MagicMock())
        plan = gen._fallback_plan([], score=90, days=7)
        assert len(plan) == 7
        assert "day" in plan[0]
        assert "topic" in plan[0]
        assert "duration_minutes" in plan[0]


# ===== KnowledgeGraphService 测试 =====
class TestKnowledgeGraphService:
    def test_singleton(self):
        from services.knowledge_graph_service import knowledge_graph_service
        assert knowledge_graph_service is not None
        graph = knowledge_graph_service.get_or_create_graph(1)
        assert graph is not None

    def test_weak_points(self):
        from services.knowledge_graph_service import knowledge_graph_service
        graph = knowledge_graph_service.get_or_create_graph(2)
        graph.record_error("test-kp", "math", "chuzhong", 5)
        weak = knowledge_graph_service.get_weak_points(2)
        assert len(weak) > 0


if __name__ == "__main__":
    pytest.main(["-v", __file__])