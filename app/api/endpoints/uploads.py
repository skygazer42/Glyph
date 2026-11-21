"""Consultation attachments, with separate public and staff storage."""

import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.schemas import AttachmentUploadResponse
from app.core.access import ChatAccess, require_staff

router = APIRouter()
logger = logging.getLogger(__name__)
ATTACHMENT_DIR = Path("uploads/attachments")
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".pdf", ".doc", ".docx", ".xls", ".xlsx"}


def attachment_directory(access: ChatAccess) -> Path:
    """按访问身份选择公共附件目录或当前工作人员目录，不创建目录。"""
    if access.is_staff:
        return ATTACHMENT_DIR / "staff" / access.namespace.split(":")[1]
    return ATTACHMENT_DIR / "public"


def _save_attachment(file: UploadFile, access: ChatAccess) -> AttachmentUploadResponse:
    """独占创建随机文件并分块写入，超过 10 MB 返回 413；写入异常时尝试删除残留，再返回上传元数据。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="上传文件缺少文件名")
    extension = Path(file.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持图片、PDF、Word 与 Excel 附件")
    stored_name = f"{uuid.uuid4().hex}{extension}"
    directory = attachment_directory(access)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / stored_name
    size = 0
    # Exclusive creation prevents overwriting another upload even on a name collision.
    with file_path.open("xb") as buffer:
        try:
            while chunk := file.file.read(64 * 1024):
                size += len(chunk)
                if size > MAX_ATTACHMENT_BYTES:
                    raise HTTPException(status_code=413, detail="附件大小不能超过 10 MB")
                buffer.write(chunk)
        except Exception:
            buffer.close()
            try:
                file_path.unlink()
            except OSError:
                logger.exception("未完整写入的附件清理失败")
            raise

    url_prefix = "/api/uploads/staff" if access.is_staff else "/api/uploads"
    return AttachmentUploadResponse(
        success=True,
        filename=file.filename,
        stored_filename=stored_name,
        path=str(file_path.resolve()),
        url=f"{url_prefix}/{stored_name}",
        mime_type=file.content_type or "application/octet-stream",
        size=size,
    )


def _attachment_response(filename: str, access: ChatAccess) -> FileResponse:
    """只返回指定身份目录内现有附件的下载响应；路径无效或文件缺失均返回 404。"""
    directory = attachment_directory(access).resolve()
    file_path = (directory / filename).resolve()
    if (
        Path(filename).name != filename
        or not file_path.is_relative_to(directory)
        or not file_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        file_path,
        filename=filename,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.post("", response_model=AttachmentUploadResponse)
def upload_attachment(file: Annotated[UploadFile, File()]) -> AttachmentUploadResponse:
    """上传公共咨询附件并返回保存路径、下载地址和大小；不解析正文或执行嵌入。"""
    return _save_attachment(file, ChatAccess())


@router.post("/staff", response_model=AttachmentUploadResponse)
def upload_staff_attachment(
    file: Annotated[UploadFile, File()], access: Annotated[ChatAccess, Depends(require_staff)]
) -> AttachmentUploadResponse:
    """将附件保存到已登录工作人员自己的目录，并返回上传元数据。"""
    return _save_attachment(file, access)


@router.get("/staff/{filename}")
def get_staff_attachment(
    filename: str, access: Annotated[ChatAccess, Depends(require_staff)]
) -> FileResponse:
    """下载当前工作人员目录内的附件；其他目录或缺失文件返回 404。"""
    return _attachment_response(filename, access)


@router.get("/{filename}")
def get_attachment(filename: str) -> FileResponse:
    """下载公共咨询目录内的附件；路径无效或文件缺失返回 404。"""
    return _attachment_response(filename, ChatAccess())
