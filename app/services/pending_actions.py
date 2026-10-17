"""Order actions proposed by the AI that only run after the customer clicks Confirm."""
from datetime import datetime, timezone
from uuid import UUID

from app.db.config import admin_supabase

CANCELLABLE_STATUSES = {"placed", "confirmed"}


class ActionError(Exception):
    """Safe, customer-facing error message."""


def clean_order_items(items) -> list[dict]:
    if not isinstance(items, list) or not items:
        raise ActionError("Please specify at least one product.")
    if len(items) > 50:
        raise ActionError("Too many different items in one order.")

    merged: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ActionError("Invalid order item.")
        product_id = item.get("product_id")
        quantity = item.get("quantity")
        if (
            not isinstance(quantity, int)
            or isinstance(quantity, bool)
            or not 1 <= quantity <= 1000
        ):
            raise ActionError("Each item needs a positive whole-number quantity.")
        try:
            product_id = str(UUID(str(product_id)))
        except ValueError:
            raise ActionError(
                "Invalid product_id. Use the exact product_id UUID returned by search_products, not a SKU or name."
            )
        merged[product_id] = merged.get(product_id, 0) + quantity

    return [{"product_id": pid, "quantity": qty} for pid, qty in merged.items()]


def _insert(user_id: str, conversation_id: str, action_type: str, payload: dict, preview: dict) -> dict:
    result = admin_supabase.table("pending_actions").insert({
        "user_id": user_id,
        "conversation_id": conversation_id,
        "action_type": action_type,
        "payload": payload,
        "preview": preview,
    }).execute()
    return result.data[0]


def propose_place_order(user_id: str, conversation_id: str, items) -> dict:
    clean = clean_order_items(items)
    ids = [i["product_id"] for i in clean]

    products = (
        admin_supabase.table("products")
        .select("id,sku,name,price,stock_quantity")
        .in_("id", ids)
        .eq("is_active", True)
        .execute()
    ).data or []
    by_id = {str(p["id"]): p for p in products}

    lines, total = [], 0.0
    for item in clean:
        product = by_id.get(item["product_id"])
        if not product:
            raise ActionError("One of the products was not found or is no longer available.")
        if product["stock_quantity"] < item["quantity"]:
            raise ActionError(
                f"Only {product['stock_quantity']} units of {product['name']} are in stock."
            )
        line_total = round(float(product["price"]) * item["quantity"], 2)
        total += line_total
        lines.append({
            "product_id": item["product_id"],
            "sku": product["sku"],
            "name": product["name"],
            "unit_price": float(product["price"]),
            "quantity": item["quantity"],
            "line_total": line_total,
        })

    # Preview only; the RPC recalculates prices and stock atomically on confirm.
    preview = {"lines": lines, "estimated_total": round(total, 2)}
    row = _insert(user_id, conversation_id, "place_order", {"items": clean}, preview)
    return {"action_id": row["id"], "action_type": "place_order", "preview": preview}


def propose_cancel_order(user_id: str, conversation_id: str, order_number: str) -> dict:
    result = (
        admin_supabase.table("orders")
        .select("order_number,status,total_amount")
        .eq("order_number", order_number)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ActionError("Order not found.")
    order = result.data[0]
    if order["status"] not in CANCELLABLE_STATUSES:
        raise ActionError(
            f"Order {order_number} is '{order['status']}' and can no longer be cancelled."
        )

    preview = {
        "order_number": order["order_number"],
        "status": order["status"],
        "total_amount": float(order["total_amount"]),
    }
    row = _insert(user_id, conversation_id, "cancel_order", {"order_number": order_number}, preview)
    return {"action_id": row["id"], "action_type": "cancel_order", "preview": preview}


def _claim(action_id: str, user_id: str, new_status: str) -> dict | None:
    """Atomically move a pending, unexpired action owned by this user to new_status."""
    result = (
        admin_supabase.table("pending_actions")
        .update({"status": new_status})
        .eq("id", action_id)
        .eq("user_id", user_id)
        .eq("status", "pending")
        .gt("expires_at", datetime.now(timezone.utc).isoformat())
        .execute()
    )
    return result.data[0] if result.data else None


def _finish(action_id: str, status: str, result: dict):
    admin_supabase.table("pending_actions").update({
        "status": status,
        "result": result,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", action_id).execute()


def _say(conversation_id: str, content: str):
    admin_supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": "assistant",
        "content": content,
    }).execute()


def confirm_action(action_id: str, user_id: str) -> dict:
    action = _claim(action_id, user_id, "processing")
    if not action:
        raise ActionError("This request was already handled or has expired. Ask the assistant again.")

    try:
        if action["action_type"] == "place_order":
            rpc = admin_supabase.rpc(
                "place_customer_order",
                {"p_user_id": user_id, "p_items": action["payload"]["items"]},
            ).execute()
        else:
            rpc = admin_supabase.rpc(
                "cancel_customer_order",
                {"p_user_id": user_id, "p_order_number": action["payload"]["order_number"]},
            ).execute()
        order = rpc.data[0] if rpc.data else None
    except Exception as e:
        print(f"Confirm action failed: {type(e).__name__}")
        order = None

    if not order:
        _finish(action_id, "failed", {})
        message = (
            "The order could not be placed. Stock or availability may have changed."
            if action["action_type"] == "place_order"
            else "The order could not be cancelled. It may no longer be eligible."
        )
        _say(action["conversation_id"], message)
        return {"status": "failed", "message": message}

    _finish(action_id, "confirmed", order)
    if action["action_type"] == "place_order":
        message = f"Order {order.get('order_number')} placed. Total: ₹{order.get('total_amount')}."
    else:
        message = f"Order {order.get('order_number')} has been cancelled."
    _say(action["conversation_id"], message)
    return {"status": "confirmed", "message": message, "order": order}


def reject_action(action_id: str, user_id: str) -> dict:
    action = _claim(action_id, user_id, "rejected")
    if not action:
        raise ActionError("This request was already handled or has expired.")
    _finish(action_id, "rejected", {})
    message = (
        "Okay, I did not place the order."
        if action["action_type"] == "place_order"
        else "Okay, the order was not cancelled."
    )
    _say(action["conversation_id"], message)
    return {"status": "rejected", "message": message}
