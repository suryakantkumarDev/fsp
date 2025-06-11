from fastapi import HTTPException, Depends
from typing import Dict, Any
from routers.auth import get_current_user

async def verify_email_required(current_user: Dict[str, Any] = Depends(get_current_user)):
    if not current_user.get("is_verified"):
        raise HTTPException(
            status_code=403,
            detail="Email verification required. Please verify your email to access this feature."
        )
    return current_user
