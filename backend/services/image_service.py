"""
Agnes Image API 调用服务 — 为数学题生成配图
使用 agnes-image-2.1-flash 模型
"""
import asyncio
import json
import logging
from typing import Optional

import httpx

from config import settings
from services.open_model_service import open_model_service

logger = logging.getLogger(__name__)

IMAGE_API_URL = "https://apihub.agnes-ai.com/v1/images/generations"
IMAGE_MODEL = "agnes-image-2.1-flash"


def _get_image_api_key() -> str:
    """获取图片 API Key——优先用环境变量"""
    return settings.AGNES_API_KEY or ""


async def generate_image(prompt: str, size: str = "1024x768") -> Optional[str]:
    """
    调用 Agnes Image API 生成图片，返回图片 URL。
    失败时返回 None（不阻塞出题流程）。
    """
    payload = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "size": size,
        "extra_body": {
            "response_format": "url",
        },
    }
    headers = {
        "Authorization": f"Bearer {_get_image_api_key()}",
        "Content-Type": "application/json",
    }

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=30.0)) as client:
                resp = await client.post(IMAGE_API_URL, headers=headers, json=payload)

            if resp.status_code == 503:
                await asyncio.sleep(3)
                continue

            resp.raise_for_status()
            data = resp.json()
            image_url = data.get("data", [{}])[0].get("url")
            if image_url:
                logger.info(f"图片生成成功: {image_url[:60]}...")
                return image_url
            else:
                logger.warning(f"图片 API 返回无 url: {json.dumps(data)[:200]}")
                return None

        except Exception as e:
            logger.warning(f"图片生成失败 (attempt {attempt+1}/2): {e}")
            if attempt == 0:
                await asyncio.sleep(3)

    logger.error(f"图片生成最终失败, prompt: {prompt[:50]}...")
    return None


async def generate_exam_images(questions: list[dict]) -> list[dict]:
    """
    为题目列表生成配图。
    对每道有 image_prompt 的题，调用 Agnes Image API 生成图片。
    使用 task_indices 正确映射回原 questions 列表，避免索引错位。
    """
    tasks = []
    task_indices = []  # 记录每个 task 对应的 questions 索引
    for i, q in enumerate(questions):
        prompt = q.get("image_prompt", "").strip()
        if prompt:
            tasks.append(generate_image(prompt))
            task_indices.append(i)

    if not tasks:
        return questions

    logger.info(f"开始为 {len(tasks)} 道题生成配图...")
    urls = await asyncio.gather(*tasks)

    for j, url in enumerate(urls):
        if url:
            questions[task_indices[j]]["image_url"] = url

    logger.info(f"图片生成完成: {sum(1 for u in urls if u)}/{len(urls)} 成功")
    return questions
