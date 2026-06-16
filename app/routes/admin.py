"""Admin endpoints — audit log access."""

from fastapi import APIRouter, Depends, Query

from app.services.audit import get_audit_logs

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs")
async def list_audit_logs(
    conversation_id: str | None = Query(None),
    step: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Retrieve audit logs with optional filtering."""
    logs = await get_audit_logs(
        conversation_id=conversation_id,
        step=step,
        limit=limit,
    )
    return {"logs": logs, "count": len(logs)}
