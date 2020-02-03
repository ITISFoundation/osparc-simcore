""" async client session


    SEE https://docs.aiohttp.org/en/latest/client_advanced.html#persistent-session
"""
import logging

from aiohttp import ClientSession, web

from .application_keys import APP_CLIENT_SESSION_KEY

log = logging.getLogger(__name__)

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
    # lazy creation and holds reference to session at this point
    session = get_client_session(app)
    log.info("Starting session %s", session)

    yield

    # closes held session
    if session is not app.get(APP_CLIENT_SESSION_KEY):
        log.error("Unexpected client session upon cleanup! expected %s, got %s",
            session,
            app.get(APP_CLIENT_SESSION_KEY))

    await session.close()
    log.info("Session is actually closed? %s", session.closed)

# FIXME: if get_client_session upon startup fails and session is NOT closed. Implement some kind of gracefull shutdonw https://docs.aiohttp.org/en/latest/client_advanced.html#graceful-shutdown
# TODO: add some tests


__all__ = [
    'APP_CLIENT_SESSION_KEY',
    'get_client_session',
    'persistent_client_session'
]
