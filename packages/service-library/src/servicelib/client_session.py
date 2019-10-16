""" async client session


    SEE https://docs.aiohttp.org/en/latest/client_advanced.html#persistent-session
"""
from aiohttp import ClientSession, web

from .application_keys import APP_CLIENT_SESSION_KEY


def get_client_session(app: web.Application) -> ClientSession:
    """ Lazy initialization of ClientSession

    Ensures unique session
    """
    session = app.get(APP_CLIENT_SESSION_KEY)
    if session is None or session.closed:
        app[APP_CLIENT_SESSION_KEY] = session = ClientSession()
    return session


async def persistent_client_session(app: web.Application):
    """ Ensures a single client session per application

    IMPORTANT: Use this function ONLY in cleanup context , i.e.
        app.cleanup_ctx.append(persistent_client_session)

    SEE https://docs.aiohttp.org/en/latest/client_advanced.html#aiohttp-persistent-session
    """
    session = get_client_session(app)

    yield

    await session.close()

# FIXME: if get_client_session upon startup fails and session is NOT closed. Implement some kind of gracefull shutdonw https://docs.aiohttp.org/en/latest/client_advanced.html#graceful-shutdown
# TODO: add some tests


__all__ = [
    'APP_CLIENT_SESSION_KEY',
    'get_client_session',
    'persistent_client_session'
]
