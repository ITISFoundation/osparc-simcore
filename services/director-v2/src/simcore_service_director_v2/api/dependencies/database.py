from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncEngine


def get_db_engine(request: Request) -> AsyncEngine:
    assert request.app.state.engine  # nosec
    engine: AsyncEngine = request.app.state.engine
    return engine
