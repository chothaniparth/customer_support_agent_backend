from langchain_core.tools import tool, InjectedToolArg
from typing import Annotated
from app.ai.retriever import retriever as global_retriever, get_user_retriever
import json
from datetime import datetime, timezone
from app.db.config import admin_supabase
from app.services.pending_actions import ActionError, propose_cancel_order, propose_place_order

@tool
def get_order_status(
    order_number: str,
    user_id: Annotated[str, InjectedToolArg],
) -> str:
    """Get the current status of a specific order belonging to the authenticated customer."""
    try:
        result = (
            admin_supabase.table("orders")
            .select("order_number,status,total_amount,created_at")
            .eq("order_number", order_number)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return "Order not found."
        order = result.data[0]
        return (
            f"Order {order['order_number']}: status is '{order['status']}', "
            f"total {order['total_amount']}, placed on {order['created_at']}."
        )
    except Exception:
        return "Could not retrieve order status right now."

@tool
def search_support_documents(question: str, user_id: Annotated[str, InjectedToolArg]):
    """Search support documents for FAQs, product manuals, and store policies."""

    # Try user-scoped docs first (uploaded by this user), then fall back to
    # global public docs (FAQs, manuals, policies ingested via ingest.py).
    docs = get_user_retriever(user_id).invoke(question)
    if not docs:
        docs = global_retriever.invoke(question)

    if not docs:
        return "No relevant support documents were found."

    results = []
    for doc in docs:
        source = doc.metadata.get("source", "Unknown source")
        results.append(f"Source: {source}\nContent: {doc.page_content}")

    return "\n\n".join(results)

@tool
def search_products(query: str) -> str:
    """Search the live store product catalog in Supabase.

    MUST use this tool when a customer asks about:
    - Product availability or whether an item is in stock
    - Current stock quantity
    - Product price or cost
    - Product names, SKUs, or catalog listings
    - Whether a specific product such as NK-500 is available
    
    RULES in Query parameter for product name:
    - Only send product name
    - Don't add other details with product like usage and type

    This tool returns live product data, including SKU, price, product_id (id),
    and stock_quantity. Do not use support-document search for
    current inventory or pricing."""
    try:
        # Try the full query against SKU first (exact pattern match).
        result = (
            admin_supabase.table("products")
            .select("id,sku,name,description,price,stock_quantity")
            .eq("is_active", True)
            .ilike("sku", f"%{query}%")
            .limit(10)
            .execute()
        )
        products = result.data or []

        # Try the full query against product name.
        if not products:
            result = (
                admin_supabase.table("products")
                .select("id,sku,name,description,price,stock_quantity")
                .eq("is_active", True)
                .ilike("name", f"%{query}%")
                .limit(10)
                .execute()
            )
            products = result.data or []

        # Word-by-word fallback: search each token against SKU then name.
        # Handles queries like "NK-500 kettle" where words are split.
        if not products:
            tokens = [t for t in query.replace("-", " ").split() if len(t) >= 2]
            seen_ids = set()
            for token in tokens:
                for field in ("sku", "name"):
                    r = (
                        admin_supabase.table("products")
                        .select("id,sku,name,description,price,stock_quantity")
                        .eq("is_active", True)
                        .ilike(field, f"%{token}%")
                        .limit(10)
                        .execute()
                    )
                    for p in (r.data or []):
                        if p["id"] not in seen_ids:
                            seen_ids.add(p["id"])
                            products.append(p)

        if not products:
            return "No matching active products found."

        # Explicitly distinguish UUID from SKU for the AI.
        formatted_products = [
            {
                "product_id": str(product["id"]),
                "sku": product["sku"],
                "name": product["name"],
                "description": product.get("description"),
                "price": float(product["price"]),
                "stock_quantity": product["stock_quantity"],
            }
            for product in products
        ]
        # print(f"products : {formatted_products}")
        return json.dumps(
            {"products": formatted_products},
            default=str,
        )
    except Exception:
        return "Product search failed. Please try again."

@tool
def place_customer_order(
    items_json: str,
    user_id: Annotated[str, InjectedToolArg],
    conversation_id: Annotated[str, InjectedToolArg],
) -> str:
    """Propose an order for the authenticated customer. This does NOT place the order:
    it shows the customer a Confirm / Cancel card, and the order is placed only when they click Confirm.

    `items_json` must be a JSON array of the exact `product_id` UUIDs returned by
    `search_products` or `list_products`, with quantities, e.g.
    `[{"product_id":"the-real-uuid-returned-by-search_products","quantity":2}]`

    Rules:
    * Look up the products first and copy the real `product_id` exactly.
    * Never use placeholder text, a SKU, a product name or an order number as `product_id`.
    * Only call this when the customer clearly says they want to buy (not for general interest).
    * After calling, tell the customer to review and click Confirm. Never say the order was placed.
    """
    try:
        items = json.loads(items_json)
    except (TypeError, ValueError):
        return "items_json is not valid JSON."
    try:
        proposal = propose_place_order(user_id, conversation_id, items)
    except ActionError as e:
        return str(e)
    except Exception as e:
        print(f"place order proposal failed: {type(e).__name__}")
        return "The order request could not be prepared right now."
    return json.dumps({
        "status": "awaiting_customer_confirmation",
        **proposal,
        "instruction": "Show the summary and ask the customer to click Confirm. The order is NOT placed yet.",
    }, default=str)

@tool
def get_my_orders(
    user_id: Annotated[str, InjectedToolArg],
    status: str | None = None,
) -> str:
    """List all orders (up to 50, newest first) belonging to the authenticated customer.

    Optionally pass `status` (placed, confirmed, shipped, delivered, cancelled)
    to only return orders in that status."""
    try:
        query = (
            admin_supabase.table("orders")
            .select(
                "order_number,status,total_amount,created_at,"
                "order_items(product_name,sku,quantity,unit_price,line_total)"
            )
            .eq("user_id", user_id)
        )
        if status:
            query = query.eq("status", status.strip().lower())
        result = query.order("created_at", desc=True).limit(50).execute()
        return json.dumps(
            {"count": len(result.data or []), "orders": result.data or []},
            default=str,
        )
    except Exception:
        return "Could not retrieve your orders right now."

@tool
def get_my_order(
    order_number: str,
    user_id: Annotated[str, InjectedToolArg],
) -> str:
    """Get the status and items for one of the authenticated customer's orders."""
    try:
        result = (
            admin_supabase.table("orders")
            .select(
                "order_number,status,total_amount,created_at,updated_at,"
                "cancelled_at,"
                "order_items(product_name,sku,quantity,unit_price,line_total)"
            )
            .eq("order_number", order_number)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return "Order not found."
        return json.dumps({"order": result.data[0]}, default=str)
    except Exception:
        return "Could not retrieve that order right now."

@tool
def cancel_my_order(
    order_number: str,
    user_id: Annotated[str, InjectedToolArg],
    conversation_id: Annotated[str, InjectedToolArg],
) -> str:
    """Propose cancelling one of the authenticated customer's orders. This does NOT cancel it:
    the customer sees a Confirm / Cancel card and the order is cancelled only when they click Confirm.
    Only orders in status 'placed' or 'confirmed' can be cancelled.
    After calling, tell the customer to click Confirm. Never say the order was cancelled."""
    try:
        proposal = propose_cancel_order(user_id, conversation_id, order_number.strip())
    except ActionError as e:
        return str(e)
    except Exception as e:
        print(f"cancel proposal failed: {type(e).__name__}")
        return "The cancellation request could not be prepared right now."
    return json.dumps({
        "status": "awaiting_customer_confirmation",
        **proposal,
        "instruction": "Ask the customer to click Confirm to cancel. The order is NOT cancelled yet.",
    }, default=str)


@tool
def list_products() -> str:
    """List every active product in the store catalog with live price and stock.

    Use when the customer asks to see all products, browse the catalog, or asks
    "what do you sell?". For a specific product use search_products instead."""
    try:
        result = (
            admin_supabase.table("products")
            .select("id,sku,name,description,price,stock_quantity")
            .eq("is_active", True)
            .order("name")
            .limit(100)
            .execute()
        )
        products = [
            {
                "product_id": str(p["id"]),
                "sku": p["sku"],
                "name": p["name"],
                "description": p.get("description"),
                "price": float(p["price"]),
                "stock_quantity": p["stock_quantity"],
            }
            for p in (result.data or [])
        ]
        if not products:
            return "The catalog has no active products."
        return json.dumps({"count": len(products), "products": products}, default=str)
    except Exception:
        return "Could not load the product catalog right now."


@tool
def compare_products(identifiers: list[str]) -> str:
    """Compare 2 to 4 products side by side using live catalog data.

    `identifiers` is a list of product names or SKUs, e.g. ["SB-001", "NK-500"].
    Returns price, stock and description for each so you can explain the differences."""
    if not isinstance(identifiers, list) or not 2 <= len(identifiers) <= 4:
        return "Please provide between 2 and 4 products to compare."

    found, missing = [], []
    for ident in identifiers:
        raw = search_products.invoke({"query": str(ident)[:100]})
        try:
            matches = json.loads(raw).get("products", [])
        except (ValueError, AttributeError):
            matches = []
        if matches:
            found.append(matches[0])
        else:
            missing.append(str(ident))

    if len(found) < 2:
        return f"Could not find enough products to compare. Not found: {missing}"
    return json.dumps({"products": found, "not_found": missing}, default=str)


@tool
def check_return_eligibility(
    order_number: str,
    user_id: Annotated[str, InjectedToolArg],
) -> str:
    """Get the facts needed to judge whether one of the customer's orders can be returned or refunded.

    Returns the order status, and days since it was placed and delivered.
    This tool does NOT decide eligibility: also call search_support_documents for
    the refund/return policy and compare the policy window against these facts."""
    try:
        result = (
            admin_supabase.table("orders")
            .select("order_number,status,total_amount,created_at,delivered_at,cancelled_at")
            .eq("order_number", order_number)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return "Order not found."
        order = result.data[0]
        now = datetime.now(timezone.utc)

        def days_since(value):
            if not value:
                return None
            return (now - datetime.fromisoformat(value.replace("Z", "+00:00"))).days

        return json.dumps(
            {
                "order_number": order["order_number"],
                "status": order["status"],
                "total_amount": order["total_amount"],
                "days_since_order_placed": days_since(order["created_at"]),
                "delivered": order["delivered_at"] is not None,
                "days_since_delivery": days_since(order["delivered_at"]),
            },
            default=str,
        )
    except Exception:
        return "Could not check that order right now."


ESCALATION_CATEGORIES = {"order", "refund", "product", "technical", "other"}


@tool
def escalate_to_human(
    category: str,
    summary: str,
    user_id: Annotated[str, InjectedToolArg],
    conversation_id: Annotated[str, InjectedToolArg],
    priority: str = "normal",
    order_number: str | None = None,
) -> str:
    """Create a support ticket so a human agent follows up with the customer.

    Use when the customer asks for a human, is upset, or the problem cannot be solved
    with the other tools (damaged item, missing delivery, payment issue, unclear policy).
    - category: one of order, refund, product, technical, other
    - summary: 1-3 sentences describing the problem in your own words
    - priority: low, normal or high (high only for damaged/missing goods or payment problems)
    - order_number: include if the issue is about a specific order
    Tell the customer the ticket number that is returned."""
    category = (category or "").strip().lower()
    if category not in ESCALATION_CATEGORIES:
        category = "other"
    priority = (priority or "normal").strip().lower()
    if priority not in {"low", "normal", "high"}:
        priority = "normal"
    summary = (summary or "").strip()[:2000]
    if len(summary) < 5:
        return "Please describe the problem before creating a ticket."

    try:
        if order_number:
            owned = (
                admin_supabase.table("orders")
                .select("order_number")
                .eq("order_number", order_number.strip())
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            order_number = owned.data[0]["order_number"] if owned.data else None

        result = admin_supabase.table("support_tickets").insert({
            "user_id": user_id,
            "conversation_id": conversation_id,
            "order_number": order_number,
            "category": category,
            "priority": priority,
            "summary": summary,
        }).execute()
        ticket = result.data[0]
        return json.dumps({
            "message": "Support ticket created",
            "ticket_number": ticket["ticket_number"],
            "status": ticket["status"],
            "priority": ticket["priority"],
        })
    except Exception as e:
        print(f"escalate_to_human failed: {type(e).__name__}")
        return "The support ticket could not be created right now."
