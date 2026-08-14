from uuid import UUID

from fastapi import Header

from studio.services.auth import decode_token

MOCK_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def get_current_user_id(authorization: str = Header(default="")) -> UUID:
    if authorization.startswith("Bearer "):
        payload = decode_token(authorization[7:])
        if payload and payload.get("type") == "access" and payload.get("sub"):
            try:
                return UUID(payload["sub"])
            except ValueError:
                pass
    return MOCK_USER_ID
