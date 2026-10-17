from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.ai.tools import (
    cancel_my_order,
    check_return_eligibility,
    compare_products,
    escalate_to_human,
    get_my_order,
    get_my_orders,
    get_order_status,
    list_products,
    place_customer_order,
    search_products,
    search_support_documents,
)

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=settings.OPENAI_API_KEY,
)

# Single source of truth: graph.py builds its tool_map from this list.
tools = [
    get_order_status,
    search_support_documents,
    search_products,
    list_products,
    compare_products,
    check_return_eligibility,
    escalate_to_human,
    place_customer_order,
    get_my_order,
    get_my_orders,
    cancel_my_order,
]
llm_with_tools = llm.bind_tools(tools)
