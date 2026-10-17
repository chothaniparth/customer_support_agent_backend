import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ai.graph import generate_graph_response, stream_graph_events
from app.core.security import get_current_user
from app.db.config import admin_supabase

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str


def _require_conversation(conversation_id: str, user_id: str):
    result = (
        admin_supabase.table("conversations")
        .select("id")
        .eq("id", conversation_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Conversation not found")


def _save_message(conversation_id: str, role: str, content: str):
    admin_supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
    }).execute()


def _history(conversation_id: str):
    return (
        admin_supabase.table("messages")
        .select("role, content")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    ).data or []


@router.post("/")
def chat(request: ChatRequest, user=Depends(get_current_user)):
    user_id = str(user.id)
    _require_conversation(request.conversation_id, user_id)
    _save_message(request.conversation_id, "user", request.message)

    try:
        answer = generate_graph_response(
            _history(request.conversation_id), user_id, request.conversation_id
        )
    except Exception as e:
        print(f"Error in chat endpoint: {type(e).__name__}")
        raise HTTPException(status_code=502, detail="The assistant is unavailable. Please try again.")

    _save_message(request.conversation_id, "assistant", answer)
    return {"answer": answer}


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@router.post("/stream")
def chat_stream(request: ChatRequest, user=Depends(get_current_user)):
    user_id = str(user.id)
    _require_conversation(request.conversation_id, user_id)
    _save_message(request.conversation_id, "user", request.message)
    history = _history(request.conversation_id)

    def event_stream():
        answer = ""
        try:
            for event in stream_graph_events(history, user_id, request.conversation_id):
                if event["type"] == "final":
                    answer = event["content"]
                yield _sse(event)
            if answer:
                _save_message(request.conversation_id, "assistant", answer)
        except Exception as e:
            print(f"Error in chat stream: {type(e).__name__}")
            yield _sse({"type": "error", "message": "Something went wrong. Please try again."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/conversation")
def create_conversation(user=Depends(get_current_user)):
    response = admin_supabase.table("conversations").insert({
        "user_id": str(user.id)
    }).execute()

    return response.data[0]


@router.get("/conversation")
def list_conversations(user=Depends(get_current_user)):
    result = (
        admin_supabase.table("conversations")
        .select("id,created_at")
        .eq("user_id", str(user.id))
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []
