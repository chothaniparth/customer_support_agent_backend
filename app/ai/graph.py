from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from typing import Annotated, TypedDict

from app.ai.llm import llm_with_tools
from app.ai.tools import get_order_status, search_support_documents, search_products, place_customer_order, get_my_order, get_my_orders, cancel_my_order
from app.ai.prompts import customer_support_prompt

class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    
tools = [get_order_status, search_support_documents, search_products, place_customer_order, get_my_order, get_my_orders, cancel_my_order]


USER_SCOPED_TOOLS = {
    "get_order_status",
    "search_support_documents",
    "place_customer_order",
    "get_my_orders",
    "get_my_order",
    "cancel_my_order",
}

tool_map = {
    tool.name : tool for tool in tools
}

def chatbot(state:ChatState):
    response = llm_with_tools.invoke(state["messages"])
    
    return {
        "messages": [response]
    }
    

def tool_node(state: ChatState):
    messages = state["messages"]
    last_message = messages[-1]
    results = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = dict(tool_call["args"])

        # Inject the authenticated user's ID into user-scoped tools.
        if tool_name in USER_SCOPED_TOOLS:
            print(f"tool name called : {tool_name}")
            tool_args["user_id"] = state["user_id"]

        tool = tool_map[tool_name]
        result = tool.invoke(tool_args)

        results.append({
            "role": "tool",
            "content": str(result),
            "tool_call_id": tool_call["id"],
        })

    return {"messages": results}
    
def should_continue(state: ChatState):
    last_message = state["messages"][-1]

    if last_message.tool_calls:
        print("")
        return "tools"

    return END

graph_builder = StateGraph(ChatState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)

graph_builder.add_edge(START, "chatbot")

graph_builder.add_conditional_edges(
    "chatbot",
    should_continue
)

graph_builder.add_edge("tools", "chatbot")

graph = graph_builder.compile()

def generate_graph_response(messages, user_id: str):
    prompt = customer_support_prompt.invoke(
        {"messages": messages}
    )

    result = graph.invoke({
        "messages": prompt.to_messages(),
        "user_id": user_id,
    })

    return result["messages"][-1].content