from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db.config import admin_supabase
from app.services.pending_actions import ActionError, confirm_action, reject_action

router = APIRouter(tags=["Support"])


@router.post("/api/chat/actions/{action_id}/confirm")
def confirm(action_id: UUID, user=Depends(get_current_user)):
    try:
        return confirm_action(str(action_id), str(user.id))
    except ActionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/api/chat/actions/{action_id}/reject")
def reject(action_id: UUID, user=Depends(get_current_user)):
    try:
        return reject_action(str(action_id), str(user.id))
    except ActionError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/api/support/tickets")
def my_tickets(user=Depends(get_current_user)):
    result = (
        admin_supabase.table("support_tickets")
        .select("id,ticket_number,category,priority,summary,status,order_number,created_at,updated_at")
        .eq("user_id", str(user.id))
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return {"tickets": result.data or []}
