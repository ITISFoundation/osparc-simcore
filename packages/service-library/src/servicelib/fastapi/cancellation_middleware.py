from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class CancellationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception as e:
            if "Client disconnected" in str(e):
                # Handle client disconnection
                return Response(status_code=499, content="Client disconnected")
            raise
        return response
