"""
OCR 文字提取服务
使用 PaddleOCR 提取图片中的文字（支持中文和手写）
支持本地路径和网络 URL
"""
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class OCRService:
    """OCR 文字提取"""

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
        """从图片中提取文字（支持本地路径和 URL）"""
        self._init()
        if not self._ocr:
            return ""

        # 如果是 URL，先下载
        local_path = image_path
        cleanup = False
        if self._is_url(image_path):
            try:
                local_path = self._download_image(image_path)
                cleanup = True
            except Exception as e:
                logger.error(f"下载图片失败: {e}")
                return f"(图片下载失败: {e})"

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
            logger.error(f"OCR 识别失败: {e}")
            return ""
        finally:
            if cleanup:
                try:
                    Path(local_path).unlink(missing_ok=True)
                except Exception:
                    pass


ocr_service = OCRService()
