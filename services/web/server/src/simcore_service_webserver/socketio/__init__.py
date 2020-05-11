""" socketio subsystem based on socket-io
    and https://github.com/miguelgrinberg/python-socketio

"""
import logging

from aiohttp import web
from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.application_setup import ModuleCategory, app_module_setup
from socketio import AsyncServer

from . import handlers, handlers_utils
from .config import APP_CLIENT_SOCKET_SERVER_KEY, CONFIG_SECTION_NAME


log = logging.getLogger(__name__)


def monkey_patch_engineio():
    # pylint: disable=too-many-statements
    """Adrsses an issue where cookies containing '=' signs in the value fail to be parsed"""
    REQUIRED_ENGINEIO_VERSION = '3.12.1'
    from engineio.__init__ import __version__

    if __version__ != REQUIRED_ENGINEIO_VERSION:
        raise RuntimeError(f"The engineio version required for this monkey patch is {REQUIRED_ENGINEIO_VERSION}\n"
                            "Please check if the new release includes the following"
                            "PR [#175](https://github.com/miguelgrinberg/python-engineio/pull/175)")

    from engineio.asyncio_client import AsyncClient

    import ssl

    try:
        import aiohttp
    except ImportError:  # pragma: no cover
        aiohttp = None

    from engineio import client
    from engineio import exceptions
    from engineio import packet

    async def _connect_websocket(self, url, headers, engineio_path):
        # pylint: disable=protected-access,no-else-return,broad-except,too-many-return-statements,too-many-branches
        """Establish or upgrade to a WebSocket connection with the server."""
        if aiohttp is None:  # pragma: no cover
            self.logger.error('aiohttp package not installed')
            return False
        websocket_url = self._get_engineio_url(url, engineio_path,
                                               'websocket')
        if self.sid:
            self.logger.info(
                'Attempting WebSocket upgrade to ' + websocket_url)
            upgrade = True
            websocket_url += '&sid=' + self.sid
        else:
            upgrade = False
            self.base_url = websocket_url
            self.logger.info(
                'Attempting WebSocket connection to ' + websocket_url)

        if self.http is None or self.http.closed:  # pragma: no cover
            self.http = aiohttp.ClientSession()

        # extract any new cookies passed in a header so that they can also be
        # sent the the WebSocket route
        cookies = {}
        for header, value in headers.items():
            if header.lower() == 'cookie':
                cookies = dict(
                    [cookie.split('=', 1) for cookie in value.split('; ')])
                del headers[header]
                break
        self.http.cookie_jar.update_cookies(cookies)

        try:
            if not self.ssl_verify:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                ws = await self.http.ws_connect(
                    websocket_url + self._get_url_timestamp(),
                    headers=headers, ssl=ssl_context)
            else:
                ws = await self.http.ws_connect(
                    websocket_url + self._get_url_timestamp(),
                    headers=headers)
        except (aiohttp.client_exceptions.WSServerHandshakeError,
                aiohttp.client_exceptions.ServerConnectionError):
            if upgrade:
                self.logger.warning(
                    'WebSocket upgrade failed: connection error')
                return False
            else:
                raise exceptions.ConnectionError('Connection error')
        if upgrade:
            p = packet.Packet(packet.PING, data='probe').encode(
                always_bytes=False)
            try:
                await ws.send_str(p)
            except Exception as e:  # pragma: no cover
                self.logger.warning(
                    'WebSocket upgrade failed: unexpected send exception: %s',
                    str(e))
                return False
            try:
                p = (await ws.receive()).data
            except Exception as e:  # pragma: no cover
                self.logger.warning(
                    'WebSocket upgrade failed: unexpected recv exception: %s',
                    str(e))
                return False
            pkt = packet.Packet(encoded_packet=p)
            if pkt.packet_type != packet.PONG or pkt.data != 'probe':
                self.logger.warning(
                    'WebSocket upgrade failed: no PONG packet')
                return False
            p = packet.Packet(packet.UPGRADE).encode(always_bytes=False)
            try:
                await ws.send_str(p)
            except Exception as e:  # pragma: no cover
                self.logger.warning(
                    'WebSocket upgrade failed: unexpected send exception: %s',
                    str(e))
                return False
            self.current_transport = 'websocket'
            self.logger.info('WebSocket upgrade was successful')
        else:
            try:
                p = (await ws.receive()).data
            except Exception as e:  # pragma: no cover
                raise exceptions.ConnectionError(
                    'Unexpected recv exception: ' + str(e))
            open_packet = packet.Packet(encoded_packet=p)
            if open_packet.packet_type != packet.OPEN:
                raise exceptions.ConnectionError('no OPEN packet')
            self.logger.info(
                'WebSocket connection accepted with ' + str(open_packet.data))
            self.sid = open_packet.data['sid']
            self.upgrades = open_packet.data['upgrades']
            self.ping_interval = open_packet.data['pingInterval'] / 1000.0
            self.ping_timeout = open_packet.data['pingTimeout'] / 1000.0
            self.current_transport = 'websocket'

            self.state = 'connected'
            client.connected_clients.append(self)
            await self._trigger_event('connect', run_async=False)

        self.ws = ws
        self.ping_loop_task = self.start_background_task(self._ping_loop)
        self.write_loop_task = self.start_background_task(self._write_loop)
        self.read_loop_task = self.start_background_task(
            self._read_loop_websocket)
        return True
    
    AsyncClient._connect_websocket = _connect_websocket # pylint: disable=protected-access


monkey_patch_engineio()


@app_module_setup(__name__, ModuleCategory.SYSTEM, logger=log)
def setup(app: web.Application):
    mgr = None
    sio = AsyncServer(async_mode="aiohttp", client_manager=mgr, logging=log)
    sio.attach(app)
    app[APP_CLIENT_SOCKET_SERVER_KEY] = sio
    handlers_utils.register_handlers(app, handlers)


# alias
setup_sockets = setup
__all__ = "setup_sockets"
