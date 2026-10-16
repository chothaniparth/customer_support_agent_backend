
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.db.config import admin_supabase

router = APIRouter(prefix="/api/orders", tags=["Orders"])


class OrderLine(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=1000)


class OrderCreate(BaseModel):
    items: list[OrderLine] = Field(min_length=1, max_length=50)


@router.post("", status_code=201)
def place_order(
    payload: OrderCreate,
    current_user=Depends(get_current_user),
):
    items = [
        {
            "product_id": str(item.product_id),
            "quantity": item.quantity,
        }
        for item in payload.items
    ]

    try:
        result = admin_supabase.rpc(
            "place_customer_order",
            {
                "p_user_id": str(current_user.id),
                "p_items": items,
            },
        ).execute()

        if not result.data:
            raise HTTPException(
                status_code=500,
                detail="Order was not created",
            )

        order = result.data[0]

        return {
            "message": "Order placed successfully",
            "order": order,
        }

    except HTTPException:
        raise
    except Exception as exc:
        # Keep database internals out of the public response.
        # Log the exception securely in production.
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not place order. "
                "Check product availability and try again."
            ),
        ) from exc


@router.get("")
def get_my_orders(
    current_user=Depends(get_current_user),
):
    result = (
        admin_supabase.table("orders")
        .select(
            "id,order_number,status,total_amount,created_at,"
            "updated_at,"
            "order_items(id,product_name,sku,quantity,unit_price,line_total)"
        )
        .eq("user_id", str(current_user.id))
        .order("created_at", desc=True)
        .execute()
    )

    return {"orders": result.data}


@router.get("/{order_number}")
def get_my_order(
    order_number: str,
    current_user=Depends(get_current_user),
):
    try:
        result = (
            admin_supabase.table("orders")
            .select(
                "id,order_number,status,total_amount,created_at,"
                "updated_at,cancelled_at,"
                "order_items(id,product_name,sku,quantity,unit_price,line_total)"
            )
            .eq("order_number", order_number)
            .eq("user_id", str(current_user.id))
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Order not found")

    if not result.data:
        raise HTTPException(status_code=404, detail="Order not found")

    return {"order": result.data[0]}

@router.post("/{order_number}/cancel")
def cancel_order(
    order_number: str,
    current_user=Depends(get_current_user),
):
    try:
        result = admin_supabase.rpc(
            "cancel_customer_order",
            {
                "p_user_id": str(current_user.id),
                "p_order_number": order_number,
            },
        ).execute()

        if not result.data:
            raise HTTPException(
                status_code=400,
                detail="Order could not be cancelled.",
            )

        return {
            "message": "Order cancelled successfully",
            "order": result.data[0],
        }

    except HTTPException:
        raise
    except Exception as exc:
        # Keep database details out of the public API response.
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not cancel this order. "
                "It may not exist, may belong to another customer, "
                "or may no longer be cancellable."
            ),
        ) from exc