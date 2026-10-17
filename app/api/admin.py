from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.permissions import require_admin
from app.db.config import admin_supabase

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# Forward-only fulfilment flow. Cancellation goes through the cancel RPC so stock is restored.
NEXT_STATUS = {"placed": "confirmed", "confirmed": "shipped", "shipped": "delivered"}

OrderStatus = Literal["placed", "confirmed", "shipped", "delivered", "cancelled"]
TicketStatus = Literal["open", "in_progress", "resolved", "closed"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/products")
def all_products(admin=Depends(require_admin)):
    result = (
        admin_supabase.table("products")
        .select("id,sku,name,description,price,stock_quantity,image_url,is_active")
        .order("name")
        .execute()
    )
    return {"products": result.data or []}


@router.get("/products/{product_id}")
def one_product(product_id: UUID, admin=Depends(require_admin)):
    result = (
        admin_supabase.table("products")
        .select("id,sku,name,description,price,stock_quantity,image_url,is_active")
        .eq("id", str(product_id))
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Product not found")
    return result.data[0]


@router.get("/orders")
def all_orders(
    status: OrderStatus | None = Query(default=None),
    admin=Depends(require_admin),
):
    query = admin_supabase.table("orders").select(
        "order_number,status,total_amount,created_at,updated_at,cancelled_at,delivered_at,"
        "order_items(product_name,sku,quantity,line_total)"
    )
    if status:
        query = query.eq("status", status)
    result = query.order("created_at", desc=True).limit(200).execute()
    return {"orders": result.data or []}


class OrderStatusUpdate(BaseModel):
    status: Literal["confirmed", "shipped", "delivered"]


@router.patch("/orders/{order_number}/status")
def advance_order(order_number: str, payload: OrderStatusUpdate, admin=Depends(require_admin)):
    current = (
        admin_supabase.table("orders")
        .select("status")
        .eq("order_number", order_number)
        .limit(1)
        .execute()
    )
    if not current.data:
        raise HTTPException(status_code=404, detail="Order not found")

    from_status = current.data[0]["status"]
    if NEXT_STATUS.get(from_status) != payload.status:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move an order from '{from_status}' to '{payload.status}'.",
        )

    # The status filter makes this a compare-and-set, so two admins cannot both advance it.
    result = (
        admin_supabase.table("orders")
        .update({"status": payload.status, "updated_at": _now()})
        .eq("order_number", order_number)
        .eq("status", from_status)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=409, detail="The order changed. Refresh and try again.")
    return {"order": result.data[0]}


@router.get("/tickets")
def all_tickets(
    status: TicketStatus | None = Query(default=None),
    admin=Depends(require_admin),
):
    query = admin_supabase.table("support_tickets").select(
        "id,ticket_number,category,priority,summary,status,order_number,created_at,updated_at"
    )
    if status:
        query = query.eq("status", status)
    result = query.order("created_at", desc=True).limit(200).execute()
    return {"tickets": result.data or []}


class TicketUpdate(BaseModel):
    status: TicketStatus


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: UUID, payload: TicketUpdate, admin=Depends(require_admin)):
    result = (
        admin_supabase.table("support_tickets")
        .update({"status": payload.status, "updated_at": _now()})
        .eq("id", str(ticket_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"ticket": result.data[0]}
