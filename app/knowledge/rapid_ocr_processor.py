"""
RapidOCR 引擎 - 图片 OCR 文字识别

使用 RapidOCR (PP-OCRv4) 进行图片文字识别
主要用途:
1. 作为 MinerU 的 OCR 后端
2. 独立处理用户上传的图片
3. 对 MinerU 提取的图片进行文字识别

注意: 这是 OCR 引擎，不是文档解析器
- 不能替代 MinerU 的文档解析功能
- 无法提取表格、公式、图片
- 不能保留文档结构
"""

import os
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPIDOCR_AVAILABLE = True
except ImportError:
    RAPIDOCR_AVAILABLE = False
    RapidOCR = None


class OCRException(Exception):
    """OCR 处理异常"""

    def __init__(self, message: str, service_name: str, status: str):
        self.message = message
        self.service_name = service_name
        self.status = status
        super().__init__(self.message)


class RapidOCRProcessor:
    """RapidOCR 处理器 - 使用 ONNX 模型进行文字识别"""

    def __init__(
        self,
        det_box_thresh: float = 0.3,
        model_dir: Optional[str] = None
    ):
        """
        初始化 RapidOCR 处理器

        Args:
            det_box_thresh: 检测框阈值 (0-1)
            model_dir: 模型目录路径，默认从环境变量读取
        """
        if not RAPIDOCR_AVAILABLE:
            raise ImportError(
                "RapidOCR 未安装。请运行: pip install rapidocr-onnxruntime"
            )

        self.ocr = None
        self.det_box_thresh = det_box_thresh

        # 模型目录配置
        if model_dir:
            self.model_dir_root = model_dir
        else:
            self.model_dir_root = os.getenv("MODEL_DIR", "./models")
            if os.getenv("RUNNING_IN_DOCKER"):
                self.model_dir_root = os.getenv("MODEL_DIR_IN_DOCKER", "/models")

    def get_service_name(self) -> str:
        """获取服务名称"""
        return "rapid_ocr"

    def get_supported_extensions(self) -> List[str]:
        """获取支持的文件扩展名"""
        return [".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]

    def _get_model_paths(self) -> tuple[str, str, str]:
        """获取模型文件路径"""
        model_dir = os.path.join(self.model_dir_root, "SWHL/RapidOCR/PP-OCRv4")

        det_model_path = os.path.join(model_dir, "ch_PP-OCRv4_det_infer.onnx")
        rec_model_path = os.path.join(model_dir, "ch_PP-OCRv4_rec_infer.onnx")
        cls_model_path = os.path.join(model_dir, "ch_ppocr_mobile_v2.0_cls_infer.onnx")

        return det_model_path, rec_model_path, cls_model_path

    def check_health(self) -> Dict[str, Any]:
        """检查 RapidOCR 模型是否可用"""
        try:
            det_model_path, rec_model_path, cls_model_path = self._get_model_paths()
            model_dir = os.path.dirname(det_model_path)

            if not os.path.exists(model_dir):
                return {
                    "status": "unavailable",
                    "message": f"模型目录不存在: {model_dir}",
                    "details": {
                        "model_dir": model_dir,
                        "help": "请下载 PP-OCRv4 模型到指定目录"
                    },
                }

            missing_models = []
            if not os.path.exists(det_model_path):
                missing_models.append("检测模型")
            if not os.path.exists(rec_model_path):
                missing_models.append("识别模型")

            if missing_models:
                return {
                    "status": "unavailable",
                    "message": f"模型文件缺失: {', '.join(missing_models)}",
                    "details": {
                        "det_model": det_model_path,
                        "rec_model": rec_model_path,
                        "cls_model": cls_model_path
                    },
                }

            # 尝试加载模型
            try:
                test_ocr = RapidOCR(
                    det_box_thresh=self.det_box_thresh,
                    det_model_path=det_model_path,
                    rec_model_path=rec_model_path,
                    cls_model_path=cls_model_path if os.path.exists(cls_model_path) else None
                )
                del test_ocr  # 释放资源

                return {
                    "status": "healthy",
                    "message": "RapidOCR 模型可用",
                    "details": {
                        "det_model": det_model_path,
                        "rec_model": rec_model_path,
                        "cls_model": cls_model_path if os.path.exists(cls_model_path) else "未使用",
                        "det_thresh": self.det_box_thresh
                    },
                }

            except Exception as e:
                return {
                    "status": "error",
                    "message": f"模型加载失败: {str(e)}",
                    "details": {"error": str(e)}
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"健康检查失败: {str(e)}",
                "details": {"error": str(e)}
            }

    def _load_model(self):
        """延迟加载 OCR 模型"""
        if self.ocr is not None:
            return

        print(f"[RapidOCR] 加载模型...")

        # 先检查健康状态
        health = self.check_health()
        if health["status"] != "healthy":
            raise OCRException(health["message"], self.get_service_name(), health["status"])

        try:
            det_model_path, rec_model_path, cls_model_path = self._get_model_paths()

            self.ocr = RapidOCR(
                det_box_thresh=self.det_box_thresh,
                det_model_path=det_model_path,
                rec_model_path=rec_model_path,
                cls_model_path=cls_model_path if os.path.exists(cls_model_path) else None
            )

            print(f"[RapidOCR] 模型加载成功 (det_box_thresh={self.det_box_thresh})")

        except Exception as e:
            raise OCRException(
                f"RapidOCR 模型加载失败: {str(e)}",
                self.get_service_name(),
                "load_failed"
            )

    def process_image(
        self,
        image,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        处理单张图像并提取文本

        Args:
            image: 图像数据，支持:
                  - str: 图像文件路径
                  - PIL.Image: PIL 图像对象
                  - numpy.ndarray: numpy 图像数组
            params: 处理参数 (当前未使用)

        Returns:
            str: 提取的文本内容
        """
        self._load_model()

        try:
            # 处理不同类型的输入
            if isinstance(image, str):
                image_path = image
                cleanup_needed = False
            else:
                # 创建临时文件
                image_path = self._create_temp_image_file(image)
                cleanup_needed = True

            try:
                # 执行 OCR
                start_time = time.time()
                result, _ = self.ocr(image_path)
                processing_time = time.time() - start_time

                # 提取文本
                if result:
                    text = "\n".join([line[1] for line in result])
                    print(
                        f"[RapidOCR] 识别成功: "
                        f"{os.path.basename(image_path) if isinstance(image, str) else 'temp_image'} "
                        f"({processing_time:.2f}s, {len(text)} 字符)"
                    )
                    return text
                else:
                    print(f"[RapidOCR] 未识别到文本: {image_path}")
                    return ""

            finally:
                # 清理临时文件
                if cleanup_needed and os.path.exists(image_path):
                    try:
                        os.remove(image_path)
                    except Exception as e:
                        print(f"[警告] 临时文件清理失败: {image_path} - {e}")

        except Exception as e:
            error_msg = f"图像 OCR 处理失败: {str(e)}"
            print(f"[错误] {error_msg}")
            raise OCRException(error_msg, self.get_service_name(), "processing_failed")

    def _create_temp_image_file(self, image) -> str:
        """将图像数据保存为临时文件"""
        try:
            # 使用系统临时目录
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as tmp_file:
                temp_path = tmp_file.name

                if isinstance(image, Image.Image):
                    image.save(temp_path)
                elif isinstance(image, np.ndarray):
                    Image.fromarray(image).save(temp_path)
                else:
                    raise ValueError("不支持的图像类型，必须是 PIL.Image 或 numpy.ndarray")

                return temp_path

        except Exception as e:
            raise OCRException(
                f"临时图像文件创建失败: {str(e)}",
                self.get_service_name(),
                "temp_file_error"
            )

    def process_pdf(
        self,
        pdf_path: str,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        处理 PDF 文件并提取文本 (流式处理，避免内存占用)

        Args:
            pdf_path: PDF 文件路径
            params: 处理参数
                - zoom_x: 横向缩放 (默认 2)
                - zoom_y: 纵向缩放 (默认 2)
                - save_images: 是否保存图片 (默认 False)
                - images_dir: 图片保存目录 (默认 None)

        Returns:
            str: 提取的文本
        """
        if not os.path.exists(pdf_path):
            raise OCRException(
                f"PDF 文件不存在: {pdf_path}",
                self.get_service_name(),
                "file_not_found"
            )

        params = params or {}
        zoom_x = params.get("zoom_x", 2)
        zoom_y = params.get("zoom_y", 2)
        save_images = params.get("save_images", False)
        images_dir = params.get("images_dir")

        try:
            all_text = []
            pdf_doc = fitz.open(pdf_path)
            total_pages = pdf_doc.page_count

            print(f"[RapidOCR] 开始处理 PDF: {os.path.basename(pdf_path)} ({total_pages} 页)")

            # 如果需要保存图片，创建目录
            if save_images and images_dir:
                os.makedirs(images_dir, exist_ok=True)

            # 流式处理每一页，避免一次性加载所有图片到内存
            for page_num in range(total_pages):
                page = pdf_doc[page_num]

                # 转换为图像
                mat = fitz.Matrix(zoom_x, zoom_y)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # 保存图片（如果需要）
                if save_images and images_dir:
                    img_path = os.path.join(images_dir, f"page_{page_num + 1}.png")
                    img_pil.save(img_path)

                # 立即处理，不保存到列表
                text = self.process_image(img_pil)
                all_text.append(text)

                if (page_num + 1) % 10 == 0:
                    print(f"[RapidOCR] 已处理 {page_num + 1}/{total_pages} 页")

            pdf_doc.close()

            result_text = "\n\n".join(all_text)
            print(
                f"[RapidOCR] PDF OCR 完成: {os.path.basename(pdf_path)} - "
                f"{len(result_text)} 字符"
            )

            return result_text

        except OCRException:
            raise
        except Exception as e:
            error_msg = f"PDF OCR 处理失败: {str(e)}"
            print(f"[错误] {error_msg}")
            raise OCRException(error_msg, self.get_service_name(), "pdf_processing_failed")

    def process_file(
        self,
        file_path: str,
        params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        处理文件 (PDF 或图像)

        Args:
            file_path: 文件路径
            params: 处理参数

        Returns:
            str: 提取的文本
        """
        file_ext = Path(file_path).suffix.lower()

        if file_ext not in self.get_supported_extensions():
            raise OCRException(
                f"不支持的文件类型: {file_ext}",
                self.get_service_name(),
                "unsupported_file_type"
            )

        if file_ext == ".pdf":
            return self.process_pdf(file_path, params)
        else:
            return self.process_image(file_path, params)

    def supports_file_type(self, file_ext: str) -> bool:
        """检查是否支持指定的文件类型"""
        return file_ext.lower() in self.get_supported_extensions()


# 便捷函数
def create_processor(**kwargs) -> RapidOCRProcessor:
    """创建 RapidOCR 处理器"""
    return RapidOCRProcessor(**kwargs)
