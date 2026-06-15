"""Admin audit log query endpoints — search, filter, paginate, and export audit records."""

import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db_session, require_admin
from app.domain.identity.models import User

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])


# ── Schemas ──────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: int
    user_id: int | None = None
    action: str
    target_type: str | None = None
    target_id: int | None = None
    path: str
    method: str
    body_summary: dict | None = None
    ip_address: str | None = None
    created_at: str | None = None


class AuditListOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int


# ── List ─────────────────────────────────────────────────────────────────


@router.get("", response_model=AuditListOut, summary="查询审计日志")
async def list_audit_logs(
    user_id: int | None = Query(None, description="按用户 ID 筛选"),
    action: str | None = Query(None, description="按操作类型筛选 (e.g. POST:personas)"),
    path: str | None = Query(None, description="按路径筛选，支持前缀匹配"),
    start: str | None = Query(None, description="起始时间 ISO8601"),
    end: str | None = Query(None, description="截止时间 ISO8601"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> AuditListOut:
    """分页查询审计日志，支持按用户/操作/路径/时间范围筛选。"""
    conditions = []
    params: dict = {}

    if user_id:
        conditions.append("user_id = :user_id")
        params["user_id"] = user_id
    if action:
        conditions.append("action = :action")
        params["action"] = action
    if path:
        conditions.append("path LIKE :path")
        params["path"] = f"{path}%"
    if start:
        conditions.append("created_at >= :start")
        params["start"] = start
    if end:
        conditions.append("created_at <= :end")
        params["end"] = end

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    offset = (page - 1) * page_size

    result = await db.execute(
        text(
            f"SELECT id, user_id, action, target_type, target_id, path, method, "
            f"body_summary, ip_address, created_at "
            f"FROM audit_log {where_clause} ORDER BY created_at DESC "
            f"LIMIT :limit OFFSET :offset"
        ),
        {**params, "limit": page_size, "offset": offset},
    )
    rows = result.fetchall()

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM audit_log {where_clause}"),
        params,
    )
    total = count_result.scalar() or 0

    import json
    items = [
        AuditLogOut(
            id=r[0], user_id=r[1], action=r[2], target_type=r[3],
            target_id=r[4], path=r[5], method=r[6],
            body_summary=r[7] if isinstance(r[7], dict) else (json.loads(r[7]) if isinstance(r[7], str) else None),
            ip_address=r[8],
            created_at=str(r[9]) if r[9] else None,
        )
        for r in rows
    ]
    return AuditListOut(items=items, total=total, page=page, page_size=page_size)


# ── Export CSV ───────────────────────────────────────────────────────────


@router.get("/export", summary="导出审计日志 CSV")
async def export_audit_logs(
    start: str | None = Query(None, description="起始时间 ISO8601"),
    end: str | None = Query(None, description="截止时间 ISO8601"),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """导出审计日志为 CSV 文件。"""
    conditions = []
    params: dict = {}

    if start:
        conditions.append("created_at >= :start")
        params["start"] = start
    if end:
        conditions.append("created_at <= :end")
        params["end"] = end

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    result = await db.execute(
        text(
            f"SELECT id, user_id, action, target_type, target_id, path, method, "
            f"body_summary, ip_address, created_at "
            f"FROM audit_log {where_clause} ORDER BY created_at DESC LIMIT 10000"
        ),
        params,
    )
    rows = result.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_id", "action", "target_type", "target_id",
                      "path", "method", "body_summary", "ip_address", "created_at"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )
