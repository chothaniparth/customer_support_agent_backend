import hashlib
import json
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import add_messages

from app.ai.llm import llm_with_tools, tools
from app.ai.prompts import customer_support_prompt


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    conversation_id: str


# Tools that receive the authenticated user's ID from graph state (never from the model).
USER_SCOPED_TOOLS = {
    "get_order_status",
    "search_support_documents",
    "place_customer_order",
    "get_my_orders",
    "get_my_order",
    "cancel_my_order",
    "check_return_eligibility",
    "escalate_to_human",
}

# Tools that also receive the current conversation ID from graph state.
CONVERSATION_SCOPED_TOOLS = {
    "place_customer_order",
    "cancel_my_order",
    "escalate_to_human",
}

# Tools whose result is a proposal the customer must confirm in the UI.
APPROVAL_TOOLS = {"place_customer_order", "cancel_my_order"}

tool_map = {tool.name: tool for tool in tools}


def chatbot(state: ChatState):
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def tool_node(state: ChatState):
    results = []

    for tool_call in state["messages"][-1].tool_calls:
        tool_name = tool_call["name"]
        tool_args = dict(tool_call["args"])
        # Never let a model-supplied value stand in for trusted context.
        tool_args.pop("user_id", None)
        tool_args.pop("conversation_id", None)

        if tool_name in USER_SCOPED_TOOLS:
            tool_args["user_id"] = state["user_id"]
        if tool_name in CONVERSATION_SCOPED_TOOLS:
            tool_args["conversation_id"] = state["conversation_id"]

        tool = tool_map.get(tool_name)
        if tool is None:
            result = f"Unknown tool '{tool_name}'."
        else:
            try:
                result = tool.invoke(tool_args)
            except Exception as e:
                print(f"Tool {tool_name} failed: {type(e).__name__}")
                result = "The tool failed. Tell the customer the action could not be completed."

        results.append({
            "role": "tool",
            "content": str(result),
            "tool_call_id": tool_call["id"],
        })

    return {"messages": results}


def should_continue(state: ChatState):
    if state["messages"][-1].tool_calls:
        return "tools"
    return END


graph_builder = StateGraph(ChatState)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges("chatbot", should_continue)
graph_builder.add_edge("tools", "chatbot")
graph = graph_builder.compile()


def _run_config(user_id: str, conversation_id: str, mode: str) -> dict:
    # LangSmith trace labels. The user is a short hash, not the raw ID or email.
    return {
        "run_name": "customer_support_chat",
        "tags": ["nestora", mode],
        "metadata": {
            "conversation_id": conversation_id,
            "user_ref": hashlib.sha256(user_id.encode()).hexdigest()[:12],
        },
    }


def _initial_state(messages, user_id: str, conversation_id: str) -> dict:
    prompt = customer_support_prompt.invoke({"messages": messages})
    return {
        "messages": prompt.to_messages(),
        "user_id": user_id,
        "conversation_id": conversation_id,
    }


def generate_graph_response(messages, user_id: str, conversation_id: str):
    result = graph.invoke(
        _initial_state(messages, user_id, conversation_id),
        config=_run_config(user_id, conversation_id, "invoke"),
    )
    return result["messages"][-1].content


def stream_graph_events(messages, user_id: str, conversation_id: str):
    """Yield UI events: tool_start, tool_end, approval_required, token, final. user_id is never emitted."""
    final_answer = ""
    call_names = {}

    for mode, payload in graph.stream(
        _initial_state(messages, user_id, conversation_id),
        config=_run_config(user_id, conversation_id, "stream"),
        stream_mode=["updates", "messages"],
    ):
        if mode == "messages":
            chunk, meta = payload
            if meta.get("langgraph_node") == "chatbot" and chunk.content:
                yield {"type": "token", "content": chunk.content}
            continue

        for node, update in payload.items():
            for msg in (update or {}).get("messages", []):
                if node == "chatbot":
                    calls = getattr(msg, "tool_calls", None) or []
                    for call in calls:
                        call_names[call["id"]] = call["name"]
                        yield {
                            "type": "tool_start",
                            "id": call["id"],
                            "name": call["name"],
                            "args": {k: v for k, v in call["args"].items() if k not in ("user_id", "conversation_id")},
                        }
                    if not calls:
                        final_answer = msg.content
                elif node == "tools":
                    call_id = msg["tool_call_id"] if isinstance(msg, dict) else msg.tool_call_id
                    text = str(msg["content"] if isinstance(msg, dict) else msg.content)
                    yield {
                        "type": "tool_end",
                        "id": call_id,
                        "summary": text[:300] + ("…" if len(text) > 300 else ""),
                    }
                    if call_names.get(call_id) in APPROVAL_TOOLS:
                        approval = _parse_approval(text)
                        if approval:
                            yield {"type": "approval_required", **approval}

    yield {"type": "final", "content": final_answer}


def _parse_approval(text: str):
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or data.get("status") != "awaiting_customer_confirmation":
        return None
    return {
        "action_id": data["action_id"],
        "action_type": data["action_type"],
        "preview": data["preview"],
    }
