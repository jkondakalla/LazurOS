import os
import jwt
from fastapi import Depends, HTTPException, Cookie, Header
from typing import Annotated

JWT_SECRET = os.getenv("JWT_SECRET", "")


def get_current_user(
    ordeck_access: str | None = Cookie(None),
    authorization: str | None = Header(None),
):
    token = ordeck_access
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token or not JWT_SECRET:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer="ordeck-auth")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


CurrentUser = Annotated[dict, Depends(get_current_user)]
