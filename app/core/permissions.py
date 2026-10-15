
from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.security import get_current_user


def require_admin(user=Depends(get_current_user)):
    admin_ids = {
        item.strip()
        for item in settings.ADMIN_USER_IDS.split(",")
        if item.strip()
    }

    if not admin_ids or str(user.id) not in admin_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user