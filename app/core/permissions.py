from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.security import get_current_user


def is_admin_user(user) -> bool:
    admin_ids = {
        item.strip()
        for item in settings.ADMIN_USER_IDS.split(",")
        if item.strip()
    }
    return bool(admin_ids) and str(user.id) in admin_ids


def require_admin(user=Depends(get_current_user)):
    if not is_admin_user(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user
