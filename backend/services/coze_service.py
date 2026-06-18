"""
Coze API 调用服务
负责与 Coze Bot 通信：批改作业、出题、诊断报告、学习方案
"""
import json
import logging
from typing import Any

import httpx
from config import settings

logger = logging.getLogger(__name__)


class CozeService:
    """Coze API 客户端"""

    def __init__(self):
        self.api_url = settings.COZE_API_URL
        self.bot_id = settings.COZE_BOT_ID
        self.token = settings.COZE_TOKEN

    async def _request(self, prompt: str, user: str = "student") -> dict:
        """向 Coze 发送请求（v3 API，需要轮询结果）"""
        import asyncio

        if not self.bot_id or not self.token:
            raise ValueError(
                "请先配置 COZE_BOT_ID 和 COZE_TOKEN 环境变量"
            )

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        payload = {
            "bot_id": self.bot_id,
            "user_id": user,
            "stream": False,
            "additional_messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "content_type": "text",
                }
            ],
        }

        async with httpx.AsyncClient(timeout=120) as client:
            # Step 1: Create chat
            resp = await client.post(self.api_url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise ValueError(f"Coze API error: {data}")

            chat_id = data["data"]["id"]
            conversation_id = data["data"]["conversation_id"]

            # Step 2: Poll for completion
            retry_count = 0
            max_retries = 60
            while retry_count < max_retries:
                await asyncio.sleep(1)
                status_resp = await client.get(
                    f"https://api.coze.cn/v3/chat/retrieve",
                    headers=headers,
                    params={"chat_id": chat_id, "conversation_id": conversation_id},
                )
                status_data = status_resp.json()
                if status_data.get("data", {}).get("status") == "completed":
                    # Step 3: Get messages
                    msg_resp = await client.get(
                        f"https://api.coze.cn/v3/chat/message/list",
                        headers=headers,
                        params={"chat_id": chat_id, "conversation_id": conversation_id},
                    )
                    msg_data = msg_resp.json()
                    messages = msg_data.get("data", [])
                    for msg in messages:
                        if msg.get("role") == "assistant" and msg.get("content"):
                            return self._parse_response(msg["content"])
                    raise ValueError(f"No assistant reply in messages: {msg_data}")
                retry_count += 1

            raise ValueError(f"Coze chat timeout after {max_retries * 2}s: {data}")

    @staticmethod
    def _parse_response(text: str) -> dict:
        """解析 Coze 返回的 JSON 文本"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass

        # 尝试提取 ```json ... ``` 中的 JSON
        import re
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试找第一个 { 到最后一个 }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # 最后退路：返回原始文本包装
        return {"raw": text}

    # ==================== 四大核心功能 ====================

    async def grade_homework(self, student_name: str, school_level: str,
                             questions_and_answers: str) -> dict:
        """批改作业"""
        prompt = f"""请批改以下数学作业。必须以 JSON 格式回复（用 ```json 包裹）。

学生信息：
- 姓名：{student_name}
- 学段：{school_level}

作业内容：
{questions_and_answers}

请返回以下 JSON 格式：
```json
{{
  "score": 85,
  "comments": "整体表现良好，但在应用题审题上需要加强...",
  "details": [
    {{
      "question": "第1题：计算 2x+3=7，求x",
      "correct": true,
      "feedback": "正确！解题步骤清晰。"
    }},
    {{
      "question": "第2题：解方程 x²-4x+3=0",
      "correct": false,
      "student_answer": "x=1",
      "correct_answer": "x=1 或 x=3",
      "feedback": "漏了一个解，一元二次方程要用因式分解或求根公式找出所有解。",
      "explanation": "x²-4x+3=0 可以因式分解为 (x-1)(x-3)=0，所以 x=1 或 x=3。"
    }}
  ]
}}
```"""
        return await self._request(prompt, student_name)

    async def generate_exam(self, school_level: str, config: dict) -> dict:
        """根据配置生成试卷"""
        points_str = "、".join(config.get("knowledge_points", [])) or "无特定要求"
        areas_str = "、".join(config.get("subject_areas", [])) or "不限"

        prompt = f"""请根据以下配置生成一份数学试卷。必须以 JSON 格式回复（用 ```json 包裹）。

学生信息：
- 学段：{school_level}

出题配置：
- 薄弱知识点：{points_str}（这些要多出题）
- 难度：{config.get("difficulty", 3)}/5
- 题目数量：{config.get("question_count", 10)}
- 学科领域：{areas_str}

请返回 JSON 格式：
```json
{{
  "title": "数学单元测试",
  "questions": [
    {{
      "id": 1,
      "question": "已知方程 2x²-5x+2=0，求 x 的值。",
      "knowledge_point": "一元二次方程",
      "difficulty": 3,
      "answer": "x=2 或 x=0.5",
      "explanation": "用求根公式..."
    }}
  ]
}}
```
题目要结合学生的薄弱知识点设计，由易到难。"""
        return await self._request(prompt, "exam-generator")

    async def generate_diagnostic_report(self, student_name: str,
                                         school_level: str,
                                         performance_data: str) -> dict:
        """生成诊断报告"""
        prompt = f"""请根据学生近期表现生成诊断报告。必须以 JSON 格式回复（用 ```json 包裹）。

学生：{student_name}（{school_level}）

最近表现数据：
{performance_data}

请返回：
```json
{{
  "strengths": ["优势知识点：一元二次方程解法扎实", "计算能力强"],
  "weaknesses": ["几何证明思路不够清晰", "概率计算容易漏情况"],
  "trend": "rising",  // rising / stable / falling
  "score_analysis": {{
    "avg": 78.5,
    "highest": 95,
    "lowest": 55,
    "improvement": "从65分提升到78分，进步明显"
  }},
  "recommendation": "建议重点加强几何证明和概率统计部分..."
}}
```"""
        return await self._request(prompt, student_name)

    async def generate_learning_plan(self, student_name: str,
                                     school_level: str,
                                     weak_points: list[str]) -> dict:
        """生成学习计划"""
        points_str = "\n".join(f"- {p}" for p in weak_points)
        prompt = f"""请根据学生薄弱知识点制定一个动态学习计划。必须以 JSON 格式回复（用 ```json 包裹）。

学生：{student_name}（{school_level}）
薄弱知识点：
{points_str}

请制定一个为期两周的学习计划：
```json
{{
  "plan": [
    {{
      "day": "周一",
      "topic": "一元二次方程",
      "focus": "因式分解法和求根公式",
      "duration_minutes": 30,
      "exercises": 5,
      "resources": "复习课本第45-48页例题"
    }}
  ],
  "milestones": [
    "一周内掌握一元二次方程的三种解法",
    "两周内能独立完成中等难度方程题目"
  ]
}}
```"""
        return await self._request(prompt, student_name)


coze_service = CozeService()
