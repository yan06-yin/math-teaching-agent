"""
OCR 文字提取服务
使用 PaddleOCR 提取图片中的文字
支持多学科：数学（公式）、语文（汉字）、英语（字母）
支持本地路径和网络 URL
"""
import logging
import re
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class OCRPipeline:
    """多学科 OCR 管线"""

    def __init__(self):
        self._ocr = None
        self._initialized = False

    def _init(self):
        if self._initialized:
            return
        try:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
            self._initialized = True
        except ImportError:
            logger.warning("PaddleOCR 未安装，OCR 功能不可用。安装：pip install paddlepaddle paddleocr")
            self._initialized = True
        except Exception as e:
            logger.warning(f"PaddleOCR 初始化失败: {e}，OCR 功能不可用")
            self._initialized = True

    def _is_url(self, path: str) -> bool:
        return path.startswith(("http://", "https://"))

    def _download_image(self, url: str) -> str:
        """下载网络图片到临时文件，返回本地路径"""
        import httpx
        suffix = Path(url).suffix or ".jpg"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            resp = client.get(url)
            resp.raise_for_status()
            tmp.write(resp.content)
            tmp.close()
        return tmp.name

    def extract_text(self, image_path: str) -> str:
        """从图片中提取文字（通用模式，不区分学科）。
        失败时抛 RuntimeError。"""
        self._init()
        if not self._ocr:
            raise RuntimeError("OCR 服务不可用（PaddleOCR 未安装或初始化失败）")

        local_path = image_path
        cleanup = False
        if self._is_url(image_path):
            try:
                local_path = self._download_image(image_path)
                cleanup = True
            except Exception as e:
                raise RuntimeError(f"图片下载失败: {e}") from e

        try:
            result = self._ocr.ocr(str(local_path), cls=True)
            lines = []
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]
                    confidence = line[1][1]
                    if confidence > 0.5:
                        lines.append(text)
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}", exc_info=True)
            raise RuntimeError(f"OCR 识别失败: {e}") from e
        finally:
            if cleanup:
                try:
                    Path(local_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def extract_with_subject(self, image_path: str, subject: str = "math") -> str:
        """
        按学科从图片中提取文字
        subject: math / chinese / english
        返回识别后的文本（不同学科有不同后处理）
        """
        raw_text = self.extract_text(image_path)

        if subject == "math":
            return self._postprocess_math(raw_text)
        elif subject == "chinese":
            return self._postprocess_chinese(raw_text)
        elif subject == "english":
            return self._postprocess_english(raw_text)
        return raw_text

    def _postprocess_math(self, text: str) -> str:
        """数学 OCR 后处理：保留数字、符号、公式结构"""
        # 去除无关空格但保留关键符号间距
        text = re.sub(r'\s+', ' ', text)
        # 标准化常见数学符号
        text = text.replace('×', 'x').replace('X', 'x')
        text = text.replace('÷', '/')
        # 修正常见 OCR 错误：字母 O 和数字 0
        text = re.sub(r'(?<!\d)O(?!\d)', '0', text)
        return text.strip()

    def _postprocess_chinese(self, text: str) -> str:
        """语文 OCR 后处理：保留汉字、标点"""
        # 去除多余空白
        text = re.sub(r'\s+', '', text)
        # 恢复基本标点（OCR 常丢失标点）
        return text.strip()

    def _postprocess_english(self, text: str) -> str:
        """英语 OCR 后处理：单词边界校正"""
        # 合并被错误分割的单词
        text = re.sub(r'(?<=[a-zA-Z])\s+(?=[a-zA-Z])', ' ', text)
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


# 全局单例
ocr_service = OCRPipeline()
