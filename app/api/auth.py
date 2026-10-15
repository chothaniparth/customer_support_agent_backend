from fastapi import APIRouter
from pydantic import BaseModel
from app.db.config import supabase
from fastapi import Depends
from app.core.security import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class SignupRequest(BaseModel):
    email: str
    password: str

class SigninRequest(BaseModel):
    email: str
    password: str
    
@router.post("/signup")
def signup(data: SignupRequest):
    response = supabase.auth.sign_up({
        "email": data.email,
        "password": data.password
    })
    
    return response
    
@router.post("/signin")
def signin(data: SigninRequest):
    try:
            
        response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })
        
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": response.user 
        }
    except Exception as e:
        print("Error during sign-in:", e)
        return {"error": str(e)}
    

@router.get("/me")
def get_me(user=Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email
    }