import os
from fastapi import Depends, HTTPException, Header
from typing import Annotated

LAZUROS_TOKEN = os.getenv("LAZUROS_TOKEN", "")


def get_current_user(authorization: str | None = Header(None)):
    if not LAZUROS_TOKEN:
        # No token configured — open access; ensure port 8080 is firewalled from WAN
        return {}
    bearer = None
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization[7:]
    if bearer != LAZUROS_TOKEN:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {}


CurrentUser = Annotated[dict, Depends(get_current_user)]
