import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Public paths that don't require auth
PUBLIC_PATHS = {"/health", "/", "/static"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        api_key = os.environ.get("MINE_API_KEY", "")

        # Skip auth if no API key configured or path is public
        if not api_key:
            return await call_next(request)

        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in PUBLIC_PATHS):
            return await call_next(request)

        # Check API key in header or query param
        req_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if req_key != api_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        return await call_next(request)
