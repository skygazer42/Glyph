"""通用附件上传与下载接口"""

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from app.api.schemas import AttachmentUploadResponse

router = APIRouter()

ATTACHMENT_DIR = Path("uploads/attachments")
ATTACHMENT_DIR.mkdir(parents=True, exist_ok=True)


@router.post("", response_model=AttachmentUploadResponse)
async def upload_attachment(file: UploadFile = File(...)):
    """上传聊天或流程附件，返回可供 AgentService 读取的路径。"""
    try:
        extension = Path(file.filename).suffix
        stored_name = f"{uuid.uuid4().hex}{extension}"
        file_path = ATTACHMENT_DIR / stored_name

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return AttachmentUploadResponse(
            success=True,
            filename=file.filename,
            stored_filename=stored_name,
            path=str(file_path.resolve()),
            url=f"/api/uploads/{stored_name}",
            mime_type=file.content_type or "application/octet-stream",
            size=getattr(file, "size", None),
        )
    except Exception as exc:  # pragma: no cover - 防御性处理
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{filename}")
async def get_attachment(filename: str):
    """提供简单的文件下载/预览能力，便于前端查看上传内容。"""
    file_path = ATTACHMENT_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path)
