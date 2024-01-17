import aiohttp_session
from aiohttp import web
from aiohttp_session import Session


async def get_session(request: web.Request) -> Session:
    """Returns current session

    - A Session object has a dict-like interface

    Usage
    ```
        from .session.api import get_session

        async def my_handler(request)
            session = await get_session(request)
    ```
    """
    return await aiohttp_session.get_session(request)
