import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel 
from app.db.config import supabase
from app.core.security import get_current_user
from app.ai.graph import generate_graph_response, stream_graph_events

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class ChatRequest(BaseModel):
    message : str
    conversation_id: str
    
@router.post("/")
def chat(request: ChatRequest, user=Depends(get_current_user)):
    try:
        conversations = (
            supabase.table("conversations")
            .select("id")
            .eq("id", request.conversation_id)
            .eq("user_id", user.id)
            .execute()
        )
        
        if not conversations.data:
            raise HTTPException(
                status_code=404,
                detail="conversations not found"
            )
        
        supabase.table("messages").insert({
            "conversation_id": request.conversation_id,
            "role": "user",
            "content": request.message
        }).execute()
    
        history = (
            supabase.table("messages")
            .select("role, content")
            .eq("conversation_id", request.conversation_id)
            .order("created_at")
            .execute()
        )
                
        answer = generate_graph_response(
            history.data,
            str(user.id),
        )
        
        supabase.table("messages").insert({
            "conversation_id": request.conversation_id,
            "role": "assistant",
            "content": answer
        }).execute()
        
        return {
            "answer": answer
        }
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        return {
            "error": str(e)
        }
        
    
def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


@router.post("/stream")
def chat_stream(request: ChatRequest, user=Depends(get_current_user)):
    owned = (
        supabase.table("conversations")
        .select("id")
        .eq("id", request.conversation_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not owned.data:
        raise HTTPException(status_code=404, detail="conversations not found")

    supabase.table("messages").insert({
        "conversation_id": request.conversation_id,
        "role": "user",
        "content": request.message,
    }).execute()

    history = (
        supabase.table("messages")
        .select("role, content")
        .eq("conversation_id", request.conversation_id)
        .order("created_at")
        .execute()
    ).data

    def event_stream():
        answer = ""
        try:
            for event in stream_graph_events(history, str(user.id)):
                if event["type"] == "final":
                    answer = event["content"]
                yield _sse(event)
            if answer:
                supabase.table("messages").insert({
                    "conversation_id": request.conversation_id,
                    "role": "assistant",
                    "content": answer,
                }).execute()
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
    response = supabase.table("conversations").insert({
        "user_id": user.id
    }).execute()

    return response.data[0]
    
@router.get("/conversation")
def list_conversations(user=Depends(get_current_user)):
    result = (
        supabase.table("conversations")
        .select("id,created_at")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []

