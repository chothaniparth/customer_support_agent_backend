from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client

from app.core.config import settings
from app.core.permissions import is_admin_user
from app.core.security import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str
    password: str


class SigninRequest(BaseModel):
    email: str
    password: str


def _auth_client():
    # A fresh client per request: sign-in stores the session on the client,
    # so a shared client would leak one user's session into other requests.
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


@router.post("/signup")
def signup(data: SignupRequest):
    try:
        response = _auth_client().auth.sign_up({
            "email": data.email,
            "password": data.password,
        })
    except Exception as e:
        print(f"Signup failed: {type(e).__name__}")
        raise HTTPException(status_code=400, detail="Could not create the account. Check the email and password.")

    return {"user": {"id": response.user.id, "email": response.user.email} if response.user else None}


@router.post("/signin")
def signin(data: SigninRequest):
    try:
        response = _auth_client().auth.sign_in_with_password({
            "email": data.email,
            "password": data.password,
        })
    except Exception as e:
        print(f"Sign-in failed: {type(e).__name__}")
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "user": {"id": response.user.id, "email": response.user.email},
    }


@router.get("/me")
def get_me(user=Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": is_admin_user(user),
    }
