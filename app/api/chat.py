from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel 
from app.db.config import supabase
from app.core.security import get_current_user
from app.ai.graph import generate_graph_response

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

