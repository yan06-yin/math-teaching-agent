"""
OpenModel / OpenAI 兼容 API 调用服务
"""
import asyncio
import json
import logging
import os
import sys
import threading
from typing import Optional, TYPE_CHECKING

import aiohttp

from config import settings

if TYPE_CHECKING:
    from models import AIProvider

logger = logging.getLogger(__name__)


class OpenModelService:
    """AI API 客户端 — 从数据库动态读取配置，支持管理后台切换模型"""

    def __init__(self):
        self.api_key = settings.AGNES_API_KEY
        self.base_url = settings.AGNES_BASE_URL
        self.model = settings.AGNES_MODEL
        self._provider_id: Optional[int] = None
        self._fallback_api_key = settings.AGNES_API_KEY
        self._fallback_base_url = settings.AGNES_BASE_URL
        self._fallback_model = settings.AGNES_MODEL
        self._fallback_lock = threading.Lock()
        self._fallback_active = False
        # 共享 aiohttp 会话（连接池复用）
        self._session: Optional[aiohttp.ClientSession] = None
        self._session_lock = threading.Lock()

    def _get_session(self) -> aiohttp.ClientSession:
        """获取共享 aiohttp 会话（懒初始化，连接池复用，线程安全）"""
        if self._session is None or self._session.closed:
            with self._session_lock:
                if self._session is None or self._session.closed:
                    connector = aiohttp.TCPConnector(
                        limit=20,
                        limit_per_host=10,
                        ttl_dns_cache=300,
                    )
                    self._session = aiohttp.ClientSession(
                        connector=connector,
                        json_serialize=lambda x: json.dumps(x, ensure_ascii=True),
                    )
        return self._session

    def reload_from_db(self, db_session=None):
        """从数据库加载活跃的 AI 提供商配置"""
        close_session = False
        try:
            if db_session is None:
                from database import SessionLocal
                db_session = SessionLocal()
                close_session = True

            from models import AIProvider
            provider = db_session.query(AIProvider).filter(AIProvider.is_active == True).first()
            if provider:
                self.api_key = provider.api_key.strip() if provider.api_key else ""
                self.base_url = provider.base_url.rstrip("/")
                self.model = provider.model
                self._provider_id = provider.id
                logger.info(f"AI 配置已加载: {provider.name} ({provider.model}) key_len={len(self.api_key)}")
        except Exception as e:
            logger.warning(f"从数据库加载 AI 配置失败，使用默认配置: {e}")
        finally:
            if close_session and db_session is not None:
                try:
                    db_session.close()
                except Exception:
                    pass

    async def _chat(self, messages: list[dict], max_tokens: int = 2048, force_model: str = None, timeout: float = 120.0) -> dict:
        return await self._chat_with_fallback(messages, max_tokens, force_model, timeout=timeout)

    async def _chat_with_fallback(self, messages: list[dict], max_tokens: int = 2048,
                                    force_model: str = None, is_retry: bool = False,
                                    timeout: float = 120.0) -> dict:
        with self._fallback_lock:
            using_fallback = self._fallback_active or is_retry

        if using_fallback:
            api_key = self._fallback_api_key
            base_url = self._fallback_base_url
            model = force_model or self._fallback_model
        else:
            api_key = self.api_key
            base_url = self.base_url
            model = force_model or self.model

        url = f"{base_url.rstrip('/')}/chat/completions"
        payload = self._build_openai_payload(messages, max_tokens, model)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        model_label = "Agnes Flash(fallback)" if using_fallback else model
        logger.info(f"AI 请求: {model_label} -> {url[:50]}...")

        last_error = None
        for attempt in range(1):
            try:
                session = self._get_session()
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 503:
                        await asyncio.sleep(3)
                        last_error = RuntimeError("503 Service Unavailable")
                        continue
                    if resp.status == 401:
                        raise ValueError("API Key 无效 (401)")

                    data = await resp.json()
                    content = self._extract_content(data)

                    if not content:
                        logger.warning(f"API 返回空内容, status={resp.status}, data={json.dumps(data, ensure_ascii=True)[:500]}")
                        last_error = RuntimeError("empty response")
                        continue

                    result = self._parse_json_response(content)
                    if using_fallback:
                        result["_fallback_used"] = True
                    return result

            except Exception as e:
                last_error = e
                logger.warning(f"AI 请求失败 (attempt {attempt+1}): {e}")

        if not using_fallback and not is_retry:
            logger.warning(f"模型 {model} 请求失败，自动降级到 Agnes AI Flash")
            with self._fallback_lock:
                self._fallback_active = True
            try:
                return await self._chat_with_fallback(messages, max_tokens, force_model, is_retry=True, timeout=timeout)
            finally:
                with self._fallback_lock:
                    self._fallback_active = False

        raise ValueError(f"AI call failed (model={model_label}): {last_error}")

    def _build_openai_payload(self, messages, max_tokens, model):
        return {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
            "chat_template_kwargs": {"enable_thinking": False},
        }

    @staticmethod
    def _extract_content(data: dict) -> str:
        if "output" in data:
            for item in data["output"]:
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return c["text"]
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]
        if "content" in data and isinstance(data["content"], list):
            texts = [c["text"] for c in data["content"] if c.get("type") == "text"]
            if texts:
                return "\n".join(texts)
        if "content" in data and isinstance(data["content"], str):
            return data["content"]
        return ""

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        if not text:
            logger.warning("AI 返回空内容，无法解析 JSON")
            return {"_parse_error": "empty response", "raw": text}

        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        text_stripped = text.strip()
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text_stripped, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        start = text_stripped.find("{")
        end = text_stripped.rfind("}") + 1
        if start != -1 and end > start:
            candidate = text_stripped[start:end]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        logger.warning(f"AI 返回内容无法解析为 JSON: {text[:200]}...")
        return {"_parse_error": "json parse failed", "raw": text}

    async def grade_homework_with_image(self, student_name: str, school_level: str,
                                         image_base64: str, extra_context: str = "") -> dict:
        """用图片直接批改作业 — 强制使用多模态模型（Agnes AI），即使当前活跃的是 DeepSeek"""
        # 多模态批改强制走 Agnes Flash（始终支持图片）
        json_example = json.dumps({
            "score": 85,
            "correct_count": 4,
            "total_count": 5,
            "comments": "整体表现良好，但在...需要加强",
            "details": [
                {"question": "第1题：2x+3=7，求x", "correct": True, "feedback": "正确"},
                {"question": "第2题：x²-4x+3=0", "correct": False, "student_answer": "x=1", "correct_answer": "x=1或x=3", "feedback": "漏了一个解", "explanation": "因式分解为(x-1)(x-3)=0"}
            ]
        }, ensure_ascii=False)

        extra_section = f"\n\n补充信息：\n{extra_context}" if extra_context else ""

        prompt = f"""你是一位经验丰富的数学老师，请识别图片中的数学题目并进行批改。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}{extra_section}

请先读取图片中的所有数学题目，然后逐题批改。

直接返回纯 JSON（不要使用 markdown 代码块），格式如下：
{json_example}

注意：
- score 是 0-100 的整数
- correct_count 和 total_count 必须准确
- 每道题都要有 feedback
- 错题必须包含 student_answer、correct_answer、explanation
"""

        messages = [
            {"role": "system", "content": "你是一位专业的数学教师。必须从图片中识别题目并批改，以纯 JSON 格式回复。"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                ]
            },
        ]

        # 多模态始终用 Agnes Flash（底层）
        try:
            result = await self._chat_with_fallback(messages, max_tokens=4096,
                                                     force_model="agnes-2.0-flash", is_retry=False)
            if result.get("_fallback_used"):
                logger.info("多模态批改使用了回退模型 Agnes Flash")
            return result
        except Exception as e:
            logger.error(f"多模态批改全部失败: {e}")
            # 最后尝试用纯文本批改
            return await self.grade_homework(
                student_name=student_name,
                school_level=school_level,
                questions_and_answers=f"学生上传了作业图片，但多模型批改失败。请给出一般性评语。错误: {e}",
            )

    async def grade_homework(self, student_name: str, school_level: str,
                             questions_and_answers: str) -> dict:
        """批改作业"""
        json_example = json.dumps({
            "score": 85,
            "comments": "整体表现良好，但在...需要加强",
            "details": [
                {"question": "第1题：2x+3=7，求x", "correct": True, "feedback": "正确"},
                {"question": "第2题：x²-4x+3=0", "correct": False, "student_answer": "x=1", "correct_answer": "x=1或x=3", "feedback": "漏了一个解", "explanation": "因式分解为(x-1)(x-3)=0"}
            ]
        }, ensure_ascii=False)

        prompt = f"""你是一位经验丰富的数学老师，请批改以下数学作业。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}

作业内容：
{questions_and_answers}

请直接返回纯 JSON（不要使用 markdown 代码块），格式如下：
{json_example}

注意：
- score 是 0-100 的整数
- 每道题都要有 feedback
- 错题必须包含 student_answer、correct_answer、explanation
"""
        messages = [
            {"role": "system", "content": "你是一位专业的数学教师。必须以纯 JSON 格式回复，不要用 markdown。"},
            {"role": "user", "content": prompt},
        ]
        return await self._chat(messages)

    async def grade_subject_homework(self, student_name: str, school_level: str,
                                      subject: str, questions_and_answers: str = "",
                                      image_base64: str = "", extra_context: str = "") -> dict:
        """
        按学科批改作业（支持多学科）
        subject: math / chinese / english
        """
        from services.grading_engine import get_subject_prompts, Subject, parse_grading_result

        try:
            subject_enum = Subject(subject)
        except ValueError:
            logger.warning(f"不支持的学科: {subject}，默认使用数学")
            subject_enum = Subject.MATH

        prompts = get_subject_prompts(subject_enum)

        if image_base64:
            # 多模态批改（强制使用 Agnes Flash）
            prompt = prompts.image_grading_prompt(student_name, school_level, extra_context)
            json_example = json.dumps(prompts.json_output_example(), ensure_ascii=False)

            system_msg = prompts.system_prompt()

            messages = [
                {"role": "system", "content": system_msg},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                },
            ]

            try:
                result = await self._chat_with_fallback(messages, max_tokens=4096,
                                                         force_model="agnes-2.0-flash", is_retry=False)
                parsed = parse_grading_result(result, subject_enum)
                return {"score": parsed.score, "comments": parsed.comments,
                        "details": parsed.details, "correct_count": parsed.correct_count,
                        "total_count": parsed.total_count, "subject": subject}
            except Exception as e:
                logger.error(f"多模态批改失败 (subject={subject}): {e}")
                if not questions_and_answers:
                    questions_and_answers = f"学生上传了作业图片，但识别失败。请给出一般性评语。错误: {e}"
                # 降级到纯文本
                return await self._grade_subject_text(student_name, school_level,
                                                       subject_enum, questions_and_answers, prompts)
        else:
            return await self._grade_subject_text(student_name, school_level,
                                                   subject_enum, questions_and_answers, prompts)

    async def _grade_subject_text(self, student_name: str, school_level: str,
                                    subject_enum, questions_and_answers: str,
                                    prompts) -> dict:
        """按学科纯文本批改"""
        prompt = prompts.grading_prompt(student_name, school_level, questions_and_answers)
        messages = [
            {"role": "system", "content": prompts.system_prompt()},
            {"role": "user", "content": prompt},
        ]
        result = await self._chat(messages)
        parsed = parse_grading_result(result, subject_enum)
        return {"score": parsed.score, "comments": parsed.comments,
                "details": parsed.details, "correct_count": parsed.correct_count,
                "total_count": parsed.total_count, "subject": subject_enum.value}

    async def generate_exam(self, school_level: str, config: dict, subject: str = "math") -> dict:
        """根据配置生成试卷（出题用较长超时 + 快速降级）
        subject: math / chinese / english
        """
        subject_name = {"math": "数学", "chinese": "语文", "english": "英语"}.get(subject, "数学")
        subject_en = subject

        points_str = "、".join(config.get("knowledge_points", [])) or "综合"
        question_count = config.get("question_count", 10)
        with_images = config.get("with_images", True) and subject == "math"

        question_example = {
            "id": 1,
            "question": "题目内容",
            "knowledge_point": "知识点",
            "difficulty": 3,
            "answer": "答案",
            "explanation": "解析",
        }
        if with_images:
            question_example["image_prompt"] = "A geometric diagram showing a right triangle with labeled sides"

        json_example = json.dumps({
            "title": f"{subject_name}测试",
            "questions": [question_example]
        }, ensure_ascii=False)

        # 学科专属出题指引
        subject_guides = {
            "math": "数学题应包含计算、证明、应用等类型。",
            "chinese": "语文题可包含阅读理解、古诗词鉴赏、作文等题型。",
            "english": "英语题可包含语法填空、阅读理解、写作等题型。",
        }
        subject_guide = subject_guides.get(subject, subject_guides["math"])

        image_instruction = """
- **需要配图的题目**请输出 `image_prompt` 字段（英文描述词，描述这张图的样子）
- 以下题型应配图：
  - 几何题：三角形、圆、坐标系等示意图
  - 函数题：坐标系 + 函数图像
  - 统计题：柱状图、折线图""" if with_images else ""

        prompt = f"""你是{subject_name}教师，请生成 {question_count} 道{subject_name}题。

学段：{school_level}
重点知识点：{points_str}
难度：{config.get("difficulty", 3)}/5

出题指导：
{subject_guide}
{image_instruction}

直接返回纯 JSON（不要使用 markdown 代码块），格式如下：
{json_example}

要求：
- 由易到难，{question_count} 题
- 每道题都要有答案和解析
- 围绕 {points_str} 出题
"""
        system_content = f"你是一位专业的{subject_name}教师。必须返回纯 JSON 格式，不要用 markdown。"
        if with_images:
            system_content += " 需要配图的题请提供 `image_prompt` 英文描述词。"

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt},
        ]
        return await self._chat(messages, max_tokens=4096, timeout=180.0)

    async def generate_diagnostic_report(self, student_name: str,
                                         school_level: str,
                                         performance_data: str) -> dict:
        """生成诊断报告"""
        json_example = json.dumps({
            "strengths": ["优势1", "优势2"],
            "weaknesses": ["薄弱1", "薄弱2"],
            "trend": "rising",
            "score_analysis": {"avg": 78.5, "highest": 95, "lowest": 55},
            "recommendation": "学习建议..."
        }, ensure_ascii=False)

        prompt = f"""生成诊断报告。

学生：{student_name}（{school_level}）
表现：{performance_data}

直接返回纯 JSON：
{json_example}
"""
        messages = [
            {"role": "system", "content": "你是一位数学教育诊断师。必须以纯 JSON 回复。"},
            {"role": "user", "content": prompt},
        ]
        return await self._chat(messages)

    async def generate_learning_plan(self, student_name: str,
                                     school_level: str,
                                     weak_points: list[str],
                                     score: float = None) -> dict:
        """生成学习计划"""
        points_str = "\n".join(f"- {p}" for p in weak_points)

        json_example = json.dumps({
            "plan": [
                {"day": "第1天", "topic": "主题", "focus": "重点", "duration_minutes": 30, "exercises": 5}
            ],
            "milestones": ["目标1", "目标2"]
        }, ensure_ascii=False)

        score_context = ""
        if score is not None:
            if score >= 80:
                score_context = f"\n学生本次得分 {score} 分（优秀），计划应侧重巩固提升、拓展拔高、保持优势。"
            elif score >= 60:
                score_context = f"\n学生本次得分 {score} 分（中等），计划应重点查漏补缺、夯实薄弱知识点。"
            else:
                score_context = f"\n学生本次得分 {score} 分（待提升），计划应从基础开始、循序渐进、多练习巩固。"

        prompt = f"""制定两周学习计划。

学生：{student_name}（{school_level}）
薄弱知识点：
{points_str}{score_context}

直接返回纯 JSON：
{json_example}
"""
        messages = [
            {"role": "system", "content": "你是一位数学教育规划师。必须以纯 JSON 回复。"},
            {"role": "user", "content": prompt},
        ]
        return await self._chat(messages)


# 全局单例
open_model_service = OpenModelService()
