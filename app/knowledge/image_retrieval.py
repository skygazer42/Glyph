"""
图片检索模块 - 支持从政策文档中检索图片（包括二维码）
无需 PyTorch 和图像模型，基于文本上下文实现
"""

import os
import re
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("警告: PIL 未安装，图片尺寸获取功能不可用")

try:
    import pyzbar.pyzbar as pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    print("提示: pyzbar 未安装，二维码识别功能不可用")


@dataclass
class ImageInfo:
    """图片信息"""
    image_id: str  # 图片唯一ID
    file_path: str  # 图片文件路径（绝对路径）
    relative_path: str  # 相对路径（Markdown中的路径）
    doc_id: str  # 所属文档ID
    section_id: str  # 所属章节ID

    # 图片元数据
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: int = 0
    file_hash: str = ""

    # 文本内容
    alt_text: str = ""  # 图片 alt 文本
    caption: str = ""  # 图片说明（从周围文本提取）
    context_before: str = ""  # 图片前的文本（100字）
    context_after: str = ""  # 图片后的文本（100字）

    # 特殊内容
    qr_content: Optional[str] = None  # 二维码内容（如果是二维码）
    is_qrcode: bool = False  # 是否包含二维码

    # 位置信息
    line_number: int = 0  # 在 Markdown 中的行号
    char_position: int = 0  # 在文档中的字符位置

    # 搜索相关
    embedding_text: str = ""  # 用于生成向量的组合文本


class ImageExtractor:
    """从 Markdown 文档中提取图片信息"""

    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        # Markdown 图片正则
        self.image_pattern = re.compile(
            r'!\[([^\]]*)\]\(([^)]+)(?:\s+"([^"]+)")?\)',
            re.MULTILINE
        )
        # 图说明正则（匹配"图："、"图1："等）
        self.caption_pattern = re.compile(
            r'(?:图\s*[:：]\s*|图\s*\d+\s*[:：]\s*|Figure\s*\d*\s*[:：]\s*)(.+?)(?:\n|$)',
            re.IGNORECASE
        )

    def extract_images_from_markdown(self, md_path: str, md_content: str) -> List[ImageInfo]:
        """从 Markdown 文件中提取所有图片信息"""
        images = []
        md_path = Path(md_path)
        doc_id = hashlib.md5(str(md_path).encode()).hexdigest()[:16]

        # 按行分割，方便获取行号
        lines = md_content.split('\n')

        # 查找所有图片
        for match in self.image_pattern.finditer(md_content):
            alt_text = match.group(1) or ""
            image_path = match.group(2)
            title = match.group(3) or ""

            # 获取行号
            char_pos = match.start()
            line_num = md_content[:char_pos].count('\n') + 1

            # 构建绝对路径
            if not os.path.isabs(image_path):
                abs_path = (md_path.parent / image_path).resolve()
            else:
                abs_path = Path(image_path)

            # 创建图片信息
            image_info = ImageInfo(
                image_id=hashlib.md5(f"{doc_id}_{image_path}".encode()).hexdigest()[:16],
                file_path=str(abs_path),
                relative_path=image_path,
                doc_id=doc_id,
                section_id="",  # 后续更新
                alt_text=alt_text,
                line_number=line_num,
                char_position=char_pos
            )

            # 提取上下文
            self._extract_context(image_info, md_content, char_pos)

            # 提取图片说明
            self._extract_caption(image_info, lines, line_num)

            # 获取图片元数据
            self._get_image_metadata(image_info)

            # 检测二维码
            if PYZBAR_AVAILABLE:
                self._detect_qrcode(image_info)

            # 生成用于搜索的组合文本
            image_info.embedding_text = self._generate_embedding_text(image_info)

            images.append(image_info)

        return images

    def _extract_context(self, image_info: ImageInfo, content: str, position: int, context_size: int = 200):
        """提取图片前后的文本上下文"""
        # 前文
        start = max(0, position - context_size)
        image_info.context_before = content[start:position].strip()

        # 后文
        # 找到图片标记的结束位置
        end_match = self.image_pattern.match(content[position:])
        if end_match:
            end_pos = position + end_match.end()
            image_info.context_after = content[end_pos:min(len(content), end_pos + context_size)].strip()

    def _extract_caption(self, image_info: ImageInfo, lines: List[str], line_num: int):
        """提取图片说明（查找图片下方的"图："说明）"""
        # 检查图片下方的几行
        for i in range(line_num, min(line_num + 5, len(lines))):
            line = lines[i].strip()

            # 检查是否是图说明
            caption_match = self.caption_pattern.match(line)
            if caption_match:
                image_info.caption = caption_match.group(1).strip()
                break

            # 如果遇到新段落或新图片，停止查找
            if line.startswith('#') or line.startswith('![]'):
                break

            # 如果是紧跟的文本，也可能是说明
            if line and not image_info.caption and i == line_num:
                # 可能整行都是说明
                image_info.caption = line[:200]  # 限制长度

    def _get_image_metadata(self, image_info: ImageInfo):
        """获取图片文件的元数据"""
        try:
            file_path = Path(image_info.file_path)
            if file_path.exists():
                # 文件大小
                image_info.file_size = file_path.stat().st_size

                # 文件哈希
                with open(file_path, 'rb') as f:
                    image_info.file_hash = hashlib.md5(f.read()).hexdigest()

                # 图片尺寸
                if PIL_AVAILABLE:
                    try:
                        with Image.open(file_path) as img:
                            image_info.width = img.width
                            image_info.height = img.height
                    except:
                        pass
        except Exception as e:
            print(f"获取图片元数据失败 {image_info.file_path}: {e}")

    def _detect_qrcode(self, image_info: ImageInfo):
        """检测图片是否包含二维码"""
        if not PYZBAR_AVAILABLE or not PIL_AVAILABLE:
            return

        try:
            file_path = Path(image_info.file_path)
            if file_path.exists():
                with Image.open(file_path) as img:
                    # 检测二维码
                    qrcodes = pyzbar.decode(img)
                    if qrcodes:
                        image_info.is_qrcode = True
                        # 提取二维码内容
                        qr_contents = []
                        for qr in qrcodes:
                            try:
                                data = qr.data.decode('utf-8')
                                qr_contents.append(data)
                            except:
                                pass
                        if qr_contents:
                            image_info.qr_content = '\n'.join(qr_contents)
        except Exception as e:
            print(f"二维码检测失败 {image_info.file_path}: {e}")

    def _generate_embedding_text(self, image_info: ImageInfo) -> str:
        """生成用于向量化的文本"""
        parts = []

        # 文件名（可能包含有意义的信息）
        filename = Path(image_info.relative_path).stem
        if filename:
            parts.append(f"文件名: {filename}")

        # Alt 文本
        if image_info.alt_text:
            parts.append(f"图片描述: {image_info.alt_text}")

        # 图片说明
        if image_info.caption:
            parts.append(f"图片说明: {image_info.caption}")

        # 二维码内容
        if image_info.qr_content:
            parts.append(f"二维码内容: {image_info.qr_content}")

        # 上下文
        context = f"{image_info.context_before} {image_info.context_after}".strip()
        if context:
            parts.append(f"上下文: {context[:300]}")

        return " ".join(parts)


class ImageIndexer:
    """图片索引器 - 将图片信息加入到分级索引中"""

    def __init__(self):
        self.extractor = ImageExtractor()
        self.image_store = {}  # image_id -> ImageInfo

    def process_markdown_with_images(self, md_path: str, md_content: str) -> Tuple[List[ImageInfo], List[Dict]]:
        """处理 Markdown 文档，提取图片并创建图片节点"""

        # 提取图片
        images = self.extractor.extract_images_from_markdown(md_path, md_content)

        # 创建图片节点（用于加入向量索引）
        image_nodes = []
        for img in images:
            # 将图片作为特殊的 chunk
            node = {
                'id': f"img_{img.image_id}",
                'content': img.embedding_text,
                'metadata': {
                    'type': 'image',
                    'content_type': 'image',
                    'image_id': img.image_id,
                    'file_path': img.file_path,
                    'relative_path': img.relative_path,
                    'doc_id': img.doc_id,
                    'is_qrcode': img.is_qrcode,
                    'qr_content': img.qr_content,
                    'caption': img.caption,
                    'alt_text': img.alt_text,
                    'width': img.width,
                    'height': img.height
                }
            }
            image_nodes.append(node)

            # 存储图片信息
            self.image_store[img.image_id] = img

        return images, image_nodes

    def search_images(self, query: str, retrieved_nodes: List) -> List[ImageInfo]:
        """从检索结果中筛选出图片"""
        image_results = []

        for node in retrieved_nodes:
            # 检查是否是图片节点
            if hasattr(node, 'metadata'):
                metadata = node.metadata
            elif isinstance(node, dict):
                metadata = node.get('metadata', {})
            else:
                continue

            if metadata.get('content_type') == 'image':
                image_id = metadata.get('image_id')
                if image_id and image_id in self.image_store:
                    image_results.append(self.image_store[image_id])

        return image_results

    def format_image_results(self, images: List[ImageInfo]) -> str:
        """格式化图片搜索结果"""
        if not images:
            return "未找到相关图片"

        results = []
        for i, img in enumerate(images, 1):
            result = f"\n**图片 {i}**\n"
            result += f"- 路径: `{img.relative_path}`\n"

            if img.caption:
                result += f"- 说明: {img.caption}\n"

            if img.is_qrcode and img.qr_content:
                result += f"- 二维码内容: {img.qr_content}\n"

            if img.width and img.height:
                result += f"- 尺寸: {img.width}x{img.height}\n"

            if img.alt_text:
                result += f"- Alt文本: {img.alt_text}\n"

            results.append(result)

        return "\n".join(results)

    def save_index(self, save_path: str):
        """保存图片索引到文件"""
        data = {
            'images': [
                {
                    'image_id': img.image_id,
                    'file_path': img.file_path,
                    'relative_path': img.relative_path,
                    'doc_id': img.doc_id,
                    'caption': img.caption,
                    'is_qrcode': img.is_qrcode,
                    'qr_content': img.qr_content,
                    'embedding_text': img.embedding_text
                }
                for img in self.image_store.values()
            ]
        }

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_index(self, load_path: str):
        """从文件加载图片索引"""
        with open(load_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.image_store = {}
        for item in data['images']:
            img = ImageInfo(
                image_id=item['image_id'],
                file_path=item['file_path'],
                relative_path=item['relative_path'],
                doc_id=item['doc_id'],
                section_id="",
                caption=item.get('caption', ''),
                is_qrcode=item.get('is_qrcode', False),
                qr_content=item.get('qr_content'),
                embedding_text=item.get('embedding_text', '')
            )
            self.image_store[img.image_id] = img


# 使用示例
if __name__ == "__main__":
    # 测试图片提取
    extractor = ImageExtractor()

    test_md = """
# 政策文档

这是一个包含图片的政策文档。

![二维码](images/qrcode.jpg)
扫描上方二维码申请补贴

![流程图](images/process.png "申请流程")
图1：补贴申请流程说明，包含三个步骤

具体步骤如下：
1. 提交申请
2. 审核材料
3. 发放补贴
    """

    images = extractor.extract_images_from_markdown("test.md", test_md)

    for img in images:
        print(f"图片ID: {img.image_id}")
        print(f"路径: {img.relative_path}")
        print(f"说明: {img.caption}")
        print(f"上下文: {img.context_before[:50]}...{img.context_after[:50]}")
        print(f"搜索文本: {img.embedding_text}")
        print("-" * 50)