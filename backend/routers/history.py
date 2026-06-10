
from __future__ import annotations

import uuid

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_auth_if_enabled
from backend.models.audit_log import AuditLog
from backend.database import get_db
from backend.models.scan_result import ScanResult
from backend.models.user import User

router = APIRouter(prefix="/history", tags=["history"])




class ScanResultItem(BaseModel):
    id: str
    file_name: str
    predicted_label: str
    risk_score: float
    probabilities: dict
    image_features: dict | None = None
    model_name: str
    gradcam_generated: bool = False
    notes: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class ScanResultDetail(ScanResultItem):
    file_sha256: str
    model_architecture: str | None = None
    glioma_margin: float | None = None
    images: list[dict] = []


class HistoryPage(BaseModel):
    items: list[ScanResultItem]
    total: int
    page: int
    per_page: int


class NotesUpdate(BaseModel):
    notes: str


class RenameUpdate(BaseModel):
    file_name: str





@router.get("", response_model=HistoryPage)
async def list_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_auth_if_enabled),
) -> HistoryPage:
    base = select(ScanResult)
    if user is not None:
        base = base.where(ScanResult.user_id == user.id)
    else:
        base = base.where(ScanResult.user_id.is_(None))

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    q = base.order_by(ScanResult.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    rows = (await db.execute(q)).scalars().all()

    items = [
        ScanResultItem(
            id=str(r.id),
            file_name=r.file_name,
            predicted_label=r.predicted_label,
            risk_score=r.risk_score,
            probabilities=r.probabilities,
            image_features=r.image_features,
            model_name=r.model_name,
            gradcam_generated=r.gradcam_generated,
            notes=r.notes,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]

    return HistoryPage(items=items, total=total, page=page, per_page=per_page)


@router.get("/{result_id}", response_model=ScanResultDetail)
async def get_result(
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_auth_if_enabled),
) -> ScanResultDetail:
    result = await db.execute(select(ScanResult).where(ScanResult.id == result_id))
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan result not found")


    if user is not None and scan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    images = [
        {
            "id": str(img.id),
            "image_type": img.image_type,
            "storage_path": img.storage_path,
            "file_size_bytes": img.file_size_bytes,
            "mime_type": img.mime_type,
        }
        for img in scan.images
    ]

    return ScanResultDetail(
        id=str(scan.id),
        file_name=scan.file_name,
        file_sha256=scan.file_sha256,
        predicted_label=scan.predicted_label,
        risk_score=scan.risk_score,
        probabilities=scan.probabilities,
        image_features=scan.image_features,
        model_name=scan.model_name,
        model_architecture=scan.model_architecture,
        glioma_margin=scan.glioma_margin,
        gradcam_generated=scan.gradcam_generated,
        notes=scan.notes,
        created_at=scan.created_at.isoformat(),
        images=images,
    )


@router.patch("/{result_id}/notes", response_model=ScanResultDetail)
async def update_notes(
    result_id: uuid.UUID,
    body: NotesUpdate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_auth_if_enabled),
) -> ScanResultDetail:
    result = await db.execute(select(ScanResult).where(ScanResult.id == result_id))
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan result not found")

    if user is not None and scan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    scan.notes = body.notes
    await db.flush()

    return await get_result(result_id, db, user)

@router.patch("/{result_id}/rename", response_model=ScanResultDetail)
async def rename_result(
    result_id: uuid.UUID,
    body: RenameUpdate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_auth_if_enabled),
    request: Request = None,
) -> ScanResultDetail:
    result = await db.execute(select(ScanResult).where(ScanResult.id == result_id))
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan result not found")

    if user is not None and scan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    scan.file_name = body.file_name
    try:
        db.add(AuditLog(
            user_id=user.id if user else None,
            action="rename_scan",
            ip_address=request.client.host if request and request.client else None,
            details={"result_id": str(result_id), "new_file_name": body.file_name},
        ))
    except Exception:
        pass

    await db.flush()

    return await get_result(result_id, db, user)


@router.delete("/{result_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
async def delete_result(
    result_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(require_auth_if_enabled),
) -> None:
    result = await db.execute(select(ScanResult).where(ScanResult.id == result_id))
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan result not found")

    if user is not None and scan.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    await db.delete(scan)
