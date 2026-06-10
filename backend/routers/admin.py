
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import require_admin
from backend.database import get_db
from backend.models.audit_log import AuditLog
from backend.models.scan_result import ScanResult
from backend.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

ROOT_DIR = Path(__file__).resolve().parents[2]
METRICS_PATH = ROOT_DIR / "models" / "metrics.json"
CLASSES_PATH = ROOT_DIR / "models" / "classes.json"
MODEL_PATH = ROOT_DIR / "models" / "brain_tumor_resnet18.pt"





class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_scans: int
    scans_today: int
    diagnosis_distribution: dict[str, int]
    scans_by_day: list[dict]
    recent_scans: list[dict]


class UserListItem(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: str
    scan_count: int


class UserListPage(BaseModel):
    items: list[UserListItem]
    total: int
    page: int
    per_page: int


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class ScanListItem(BaseModel):
    id: str
    file_name: str
    predicted_label: str
    risk_score: float
    model_name: str
    user_email: str | None = None
    session_id: str | None = None
    created_at: str


class ScanListPage(BaseModel):
    items: list[ScanListItem]
    total: int
    page: int
    per_page: int


class ScanDetail(BaseModel):
    id: str
    file_name: str
    file_sha256: str
    predicted_label: str
    risk_score: float
    probabilities: dict
    image_features: dict | None = None
    model_name: str
    model_architecture: str | None = None
    glioma_margin: float | None = None
    gradcam_generated: bool
    notes: str | None = None
    user_email: str | None = None
    session_id: str | None = None
    created_at: str
    images: list[dict] = []


class AuditListItem(BaseModel):
    id: int
    user_email: str | None = None
    action: str
    ip_address: str | None = None
    details: dict | None = None
    created_at: str


class AuditListPage(BaseModel):
    items: list[AuditListItem]
    total: int
    page: int
    per_page: int


class ModelInfo(BaseModel):
    model_name: str
    architecture: str | None = None
    image_size: int | None = None
    classes: list[str] = []
    glioma_margin: float = 0.0
    metrics: dict | None = None
    file_size_bytes: int | None = None





@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    period_start = now - timedelta(days=days)


    total_users = (await db.execute(
        select(func.count(User.id)).where(User.role != "admin")
    )).scalar() or 0
    active_users = (await db.execute(
        select(func.count(User.id)).where(User.is_active.is_(True)).where(User.role != "admin")
    )).scalar() or 0


    total_scans = (await db.execute(select(func.count(ScanResult.id)))).scalar() or 0
    scans_today = (await db.execute(
        select(func.count(ScanResult.id)).where(ScanResult.created_at >= today_start)
    )).scalar() or 0


    diag_q = (
        select(ScanResult.predicted_label, func.count(ScanResult.id))
        .group_by(ScanResult.predicted_label)
    )
    diag_rows = (await db.execute(diag_q)).all()
    diagnosis_distribution = {label: count for label, count in diag_rows}


    day_q = (
        select(
            cast(ScanResult.created_at, Date).label("day"),
            func.count(ScanResult.id).label("count"),
        )
        .where(ScanResult.created_at >= period_start)
        .group_by("day")
        .order_by("day")
    )
    day_rows = (await db.execute(day_q)).all()
    scans_by_day = [{"date": str(row.day), "count": row.count} for row in day_rows]


    recent_q = (
        select(ScanResult)
        .order_by(ScanResult.created_at.desc())
        .limit(5)
    )
    recent_rows = (await db.execute(recent_q)).scalars().all()
    recent_scans = [
        {
            "id": str(r.id),
            "file_name": r.file_name,
            "predicted_label": r.predicted_label,
            "risk_score": r.risk_score,
            "created_at": r.created_at.isoformat(),
        }
        for r in recent_rows
    ]

    return DashboardStats(
        total_users=total_users,
        active_users=active_users,
        total_scans=total_scans,
        scans_today=scans_today,
        diagnosis_distribution=diagnosis_distribution,
        scans_by_day=scans_by_day,
        recent_scans=recent_scans,
    )





@router.get("/users", response_model=UserListPage)
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
) -> UserListPage:
    base = select(User)
    if search:
        pattern = f"%{search}%"
        base = base.where(User.email.ilike(pattern) | User.full_name.ilike(pattern))
    if role:
        base = base.where(User.role == role)
    if is_active is not None:
        base = base.where(User.is_active == is_active)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    q = base.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    users = (await db.execute(q)).scalars().all()

    items = []
    for u in users:
        scan_count = (await db.execute(
            select(func.count(ScanResult.id)).where(ScanResult.user_id == u.id)
        )).scalar() or 0
        items.append(UserListItem(
            id=str(u.id),
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at.isoformat(),
            scan_count=scan_count,
        ))

    return UserListPage(items=items, total=total, page=page, per_page=per_page)


@router.patch("/users/{user_id}", response_model=UserListItem)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> UserListItem:
    if user_id == current_admin.id:
        if body.is_active is False or (body.role is not None and body.role != "admin"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself or change your own role")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.flush()

    scan_count = (await db.execute(
        select(func.count(ScanResult.id)).where(ScanResult.user_id == user.id)
    )).scalar() or 0

    return UserListItem(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        scan_count=scan_count,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
async def delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> None:
    if user_id == current_admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)





@router.get("/scans", response_model=ScanListPage)
async def list_scans(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    label: str | None = None,
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> ScanListPage:
    base = select(ScanResult)
    if label:
        base = base.where(ScanResult.predicted_label == label)
    if user_id:
        try:
            uid = uuid.UUID(user_id)
            base = base.where(ScanResult.user_id == uid)
        except ValueError:
            pass

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    q = base.order_by(ScanResult.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    scans = (await db.execute(q)).scalars().all()

    items = []
    for s in scans:
        user_email = None
        if s.user_id:
            u_result = await db.execute(select(User.email).where(User.id == s.user_id))
            user_email = u_result.scalar_one_or_none()
        items.append(ScanListItem(
            id=str(s.id),
            file_name=s.file_name,
            predicted_label=s.predicted_label,
            risk_score=s.risk_score,
            model_name=s.model_name,
            user_email=user_email,
            session_id=s.session_id,
            created_at=s.created_at.isoformat(),
        ))

    return ScanListPage(items=items, total=total, page=page, per_page=per_page)


@router.get("/scans/{scan_id}", response_model=ScanDetail)
async def get_scan(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScanDetail:
    result = await db.execute(select(ScanResult).where(ScanResult.id == scan_id))
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    user_email = None
    if scan.user_id:
        u_result = await db.execute(select(User.email).where(User.id == scan.user_id))
        user_email = u_result.scalar_one_or_none()

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

    return ScanDetail(
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
        user_email=user_email,
        session_id=scan.session_id,
        created_at=scan.created_at.isoformat(),
        images=images,
    )


@router.delete("/scans/{scan_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
async def delete_scan(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(ScanResult).where(ScanResult.id == scan_id))
    scan = result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    await db.delete(scan)





@router.get("/audit", response_model=AuditListPage)
async def list_audit(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    action: str | None = None,
    user_id: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> AuditListPage:
    base = select(AuditLog)
    if action:
        base = base.where(AuditLog.action == action)
    if user_id:
        try:
            uid = uuid.UUID(user_id)
            base = base.where(AuditLog.user_id == uid)
        except ValueError:
            pass

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    q = base.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    entries = (await db.execute(q)).scalars().all()

    items = []
    for e in entries:
        user_email = None
        if e.user_id:
            u_result = await db.execute(select(User.email).where(User.id == e.user_id))
            user_email = u_result.scalar_one_or_none()
        items.append(AuditListItem(
            id=e.id,
            user_email=user_email,
            action=e.action,
            ip_address=e.ip_address,
            details=e.details,
            created_at=e.created_at.isoformat(),
        ))

    return AuditListPage(items=items, total=total, page=page, per_page=per_page)





@router.get("/model-info", response_model=ModelInfo)
async def model_info() -> ModelInfo:
    classes: list[str] = []
    if CLASSES_PATH.exists():
        classes = json.loads(CLASSES_PATH.read_text(encoding="utf-8"))

    metrics_data: dict | None = None
    glioma_margin = 0.0
    architecture = None
    image_size = None

    if METRICS_PATH.exists():
        metrics_data = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
        glioma_margin = float(metrics_data.get("best_glioma_margin", 0.0))


    if MODEL_PATH.exists():
        try:
            import torch
            state = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
            architecture = state.get("architecture", "unknown")
            image_size = state.get("image_size", 224)
        except Exception:
            pass

    file_size = MODEL_PATH.stat().st_size if MODEL_PATH.exists() else None

    return ModelInfo(
        model_name=MODEL_PATH.name if MODEL_PATH.exists() else "not found",
        architecture=architecture,
        image_size=image_size,
        classes=classes,
        glioma_margin=glioma_margin,
        metrics=metrics_data,
        file_size_bytes=file_size,
    )
