
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from backend.config import settings

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/{filename:path}")
async def serve_image(filename: str) -> FileResponse:
    file_path = settings.upload_path / filename

    try:
        file_path = file_path.resolve()
        settings.upload_path.resolve()
        if not str(file_path).startswith(str(settings.upload_path.resolve())):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

    return FileResponse(file_path)
