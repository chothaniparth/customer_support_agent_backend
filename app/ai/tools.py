from langchain_core.tools import tool, InjectedToolArg
from typing import Annotated
from app.ai.retriever import retriever as global_retriever, get_user_retriever
import json
from app.db.config import admin_supabase

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
            .maybe_single()
            .execute()
        )
        if not result.data:
            return "Order not found."
        order = result.data
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
) -> str:
    """Place an order for the authenticated customer.

    `items_json` must be a JSON array containing the exact `product_id` UUID returned by `search_products` and the requested quantity.

    Example format:
    `[{"product_id":"the-real-uuid-returned-by-search_products","quantity":2}]`

    Rules:

    * Always call `search_products` before placing an order.
    * Copy the actual `product_id` from its result exactly.
    * Never use placeholder text, SKU, product name, or order number as `product_id`.
    * Before placing the order, show the customer the product, price, quantity, and total, and obtain explicit confirmation.
    * Only call this tool after the customer confirms the order.
    """
    try:
        # print(f"item info : {items_json}")
        items = json.loads(items_json)
        if not isinstance(items, list) or not items:
            return "Please specify at least one product."

        if len(items) > 50:
            return "Too many different items in one order."

        clean_items = []
        for item in items:
            # print(f"item in loop start : {item}")
            if not isinstance(item, dict):
                return "Invalid order item."
            product_id = item.get("product_id")
            quantity = item.get("quantity")
            if (
                not isinstance(product_id, str)
                or not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or quantity < 1
                or quantity > 1000
            ):
                return "Each item needs a product ID and a positive quantity."
            clean_items.append({
                "product_id": product_id,
                "quantity": quantity,
            })
        # print(f"clean item : {clean_items}")
        result = admin_supabase.rpc(
            "place_customer_order",
            {
                "p_user_id": user_id,
                "p_items": clean_items,
            },
        ).execute()

        if not result.data:
            return "The order could not be created."

        return json.dumps(
            {"message": "Order placed", "order": result.data[0]},
            default=str,
        )
    except Exception as e:
        print(f"place order tool error : {e}")
        return (
            "The order could not be placed. Stock may be insufficient, "
            "or a product may be unavailable. Please check and try again."
        )

@tool
def get_my_orders(
    user_id: Annotated[str, InjectedToolArg],
) -> str:
    """List recent orders belonging to the authenticated customer."""
    try:
        result = (
            admin_supabase.table("orders")
            .select(
                "order_number,status,total_amount,created_at,"
                "order_items(product_name,sku,quantity,unit_price,line_total)"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return json.dumps(
            {"orders": result.data or []},
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
) -> str:
    """Cancel an eligible order belonging to the authenticated customer.
    Before calling, confirm which order the customer wants to cancel."""
    try:
        result = admin_supabase.rpc(
            "cancel_customer_order",
            {
                "p_user_id": user_id,
                "p_order_number": order_number,
            },
        ).execute()

        if not result.data:
            return "The order could not be cancelled."
        return json.dumps(
            {"message": "Order cancelled", "order": result.data[0]},
            default=str,
        )
    except Exception:
        return (
            "Cancellation failed. The order may not exist, may belong "
            "to another customer, or may already be processing or shipped."
        )