"""
OpenModel / OpenAI 兼容 API 调用服务
支持任何兼容 OpenAI Chat Completions API 的模型提供商
默认使用 Agnes AI Flash（便宜、支持多模态图片识别）
可在管理后台切换为 DeepSeek、OpenAI 等其他模型
"""
import asyncio
import json
import logging
from typing import Optional, TYPE_CHECKING

import httpx

from config import settings

if TYPE_CHECKING:
    from models import AIProvider

logger = logging.getLogger(__name__)


class OpenModelService:
    """AI API 客户端 — 从数据库动态读取配置，支持管理后台切换模型"""

    def __init__(self):
        # 从环境变量读取默认值（首次启动时无数据库配置时使用）
        self.api_key = settings.AGNES_API_KEY
        self.base_url = settings.AGNES_BASE_URL
        self.model = settings.AGNES_MODEL
        self._provider_id: Optional[int] = None

    def reload_from_db(self, db_session=None):
        """从数据库加载活跃的 AI 提供商配置"""
        try:
            if db_session is None:
                from database import SessionLocal
                db_session = SessionLocal()
                close_session = True
            else:
                close_session = False

            from models import AIProvider
            provider = db_session.query(AIProvider).filter(AIProvider.is_active == True).first()
            if provider:
                self.api_key = provider.api_key
                self.base_url = provider.base_url
                self.model = provider.model
                self._provider_id = provider.id
                logger.info(f"AI 模型配置已切换: {provider.name} ({provider.model})")
            if close_session:
                db_session.close()
        except Exception as e:
            logger.warning(f"从数据库加载 AI 配置失败，使用默认配置: {e}")

    async def _chat(self, messages: list[dict], max_tokens: int = 2048) -> dict:
        """调用 OpenAI 兼容聊天接口，带重试"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        url = f"{self.base_url.rstrip('/')}/chat/completions"

        # 最多重试 3 次
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
                    resp = await client.post(url, headers=headers, json=payload)

                if resp.status_code == 503:
                    wait = (attempt + 1) * 3
                    logger.warning(f"503 限流，{wait}s 后重试 ({attempt+1}/3)")
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code == 401:
                    raise ValueError(f"API Key 无效（401）: 请检查管理后台的 AI 模型配置")

                resp.raise_for_status()
                data = resp.json()

                # 兼容不同响应格式
                content = ""
                if "choices" in data and len(data["choices"]) > 0:
                    choice = data["choices"][0]
                    if "message" in choice and "content" in choice["message"]:
                        content = choice["message"]["content"]
                    elif "delta" in choice and "content" in choice.get("delta", {}):
                        content = choice["delta"]["content"]
                    elif "text" in choice:
                        content = choice["text"]
                elif "content" in data:
                    content = data["content"]

                if not content:
                    logger.warning(f"API 返回空内容: {json.dumps(data)[:300]}")
                    return {"raw": json.dumps(data, ensure_ascii=False)}

                return self._parse_json_response(content)

            except httpx.TimeoutException:
                if attempt < 2:
                    wait = (attempt + 1) * 5
                    logger.warning(f"请求超时，{wait}s 后重试 ({attempt+1}/3)")
                    await asyncio.sleep(wait)
                    continue
                raise
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                if attempt < 2:
                    wait = (attempt + 1) * 3
                    logger.warning(f"请求异常: {e}，{wait}s 后重试 ({attempt+1}/3)")
                    await asyncio.sleep(wait)
                    continue
                raise
            except ValueError:
                raise
            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 2
                    logger.warning(f"未知错误: {e}，{wait}s 后重试 ({attempt+1}/3)")
                    await asyncio.sleep(wait)
                    continue
                raise

        raise ValueError("AI 请求多次重试后仍然失败")

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """从模型回复中提取 JSON"""
        if not text:
            return {"raw": text}

        # 1. 尝试直接解析
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        text_stripped = text.strip()

        # 2. 尝试提取 ```json ... ``` 中的 JSON
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text_stripped, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3. 尝试找第一个 { 到最后一个 }
        start = text_stripped.find("{")
        end = text_stripped.rfind("}") + 1
        if start != -1 and end > start:
            candidate = text_stripped[start:end]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 4. 最后退路
        return {"raw": text}

    async def grade_homework_with_image(self, student_name: str, school_level: str,
                                         image_base64: str) -> dict:
        """用图片直接批改作业（跳过OCR）"""
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

        prompt = f"""你是一位经验丰富的数学老师，请识别图片中的数学题目并进行批改。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}

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
        return await self._chat(messages, max_tokens=4096)

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

    async def generate_exam(self, school_level: str, config: dict) -> dict:
        """根据配置生成试卷"""
        points_str = "、".join(config.get("knowledge_points", [])) or "综合"
        question_count = config.get("question_count", 10)

        json_example = json.dumps({
            "title": "数学测试",
            "questions": [
                {"id": 1, "question": "题目内容", "knowledge_point": "知识点", "difficulty": 3, "answer": "答案", "explanation": "解析"}
            ]
        }, ensure_ascii=False)

        prompt = f"""你是数学教师，请生成 {question_count} 道数学题。

学段：{school_level}
重点知识点：{points_str}
难度：{config.get("difficulty", 3)}/5

直接返回纯 JSON（不要使用 markdown 代码块），格式如下：
{json_example}

要求：
- 由易到难，{question_count} 题
- 每道题都要有答案和解析
- 围绕 {points_str} 出题
"""
        messages = [
            {"role": "system", "content": "你是一位专业的数学教师。必须返回纯 JSON 格式，不要用 markdown。"},
            {"role": "user", "content": prompt},
        ]
        return await self._chat(messages, max_tokens=4096)

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
                                     weak_points: list[str]) -> dict:
        """生成学习计划"""
        points_str = "\n".join(f"- {p}" for p in weak_points)

        json_example = json.dumps({
            "plan": [
                {"day": "第1天", "topic": "主题", "focus": "重点", "duration_minutes": 30, "exercises": 5}
            ],
            "milestones": ["目标1", "目标2"]
        }, ensure_ascii=False)

        prompt = f"""制定两周学习计划。

学生：{student_name}（{school_level}）
薄弱知识点：
{points_str}

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
