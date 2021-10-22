import warnings

from aiohttp import ClientSession, ClientTimeout

from ..config.http_clients import client_request_settings


class ClientSessionContextManager:
    #
    # NOTE: creating a session at every call is inneficient and a persistent session
    # per app is recommended.
    # This package has no app so session is passed as optional arguments
    # See https://github.com/ITISFoundation/osparc-simcore/issues/1098
    #
    def __init__(self, session=None):
        # We are interested in fast connections, if a connection is established
        # there is no timeout for file download operations

        self.active_session = session or ClientSession(
            timeout=ClientTimeout(
                total=None,
                connect=client_request_settings.aiohttp_connect_timeout,
                sock_connect=client_request_settings.aiohttp_sock_connect_timeout,
            )  # type: ignore
        )
        self.is_owned = self.active_session is not session

    async def __aenter__(self):
        return self.active_session

    async def __aexit__(self, exc_type, exc, tb):
        if self.is_owned:
            warnings.warn(
                "Optional session is not recommended, pass instead controled session (e.g. from app[APP_CLIENT_SESSION_KEY])",
                category=DeprecationWarning,
            )
            await self.active_session.close()
