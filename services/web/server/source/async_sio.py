"""
    Defines **async** handlers for socket.io server


    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/

"""
# pylint: disable=C0111


import logging
import socketio
import interactive_services_manager

_LOGGER = logging.getLogger(__file__)

SIO = socketio.AsyncServer(async_mode='aiohttp')


@SIO.on('connect')
def connect(sid, environ):
    # pylint: disable=W0613
    # environ = WSGI evnironment dictionary
    _LOGGER.debug("client %s connects", sid)
    interactive_services_manager.session_connect(sid)
    return True


@SIO.on('getInteractiveServices')
async def get_interactive_services_handler(sid, data):
    # pylint: disable=C0103
    # pylint: disable=W0613
    _LOGGER.debug("client %s gets interactive services", sid)
    result = interactive_services_manager.retrieve_list_of_services()
    await SIO.emit('getInteractiveServices', data=result, room=sid)


@SIO.on('startModeler')
async def start_modeler_handler(sid, data):
    _LOGGER.debug("client %s requests start modeler %s", sid, data)
    result = interactive_services_manager.start_service(sid, 'modeler', data)
    # TODO: Connection failure raises exception that is not treated, which stops the webserver
    # Add mechanism to handle these situations (retry, abandon...)
    try:
        await SIO.emit('startModeler', data=result, room=sid)
    except IOError as err:
        _LOGGER.exception(err)


@SIO.on('stopModeler')
async def stop_modeler_handler(sid, data):
    _LOGGER.debug("client %s requests stop modeler %s", sid, data)
    result = interactive_services_manager.stop_service(sid, data)
    await SIO.emit('stopModeler', data=result, room=sid)


@SIO.on('startJupyter')
async def start_jupyter_handler(sid, data):
    _LOGGER.debug("client %s requests start jupyter %s", sid, data)
    result = interactive_services_manager.start_service(
        sid, 'jupyter-base-notebook', data)
    _LOGGER.debug("director %s starts jupyter %s: %s", sid, data, result)
    await SIO.emit('startJupyter', data=result, room=sid)


@SIO.on('stopJupyter')
async def stop_jupyter_handler(sid, data):
    _LOGGER.debug("client %s requests stop jupyter %s", sid, data)
    result = interactive_services_manager.stop_service(sid, data)
    await SIO.emit('stopJupyter', data=result, room=sid)


@SIO.on('disconnect')
def disconnect(sid):
    _LOGGER.debug("client %s disconnected", sid)
    interactive_services_manager.session_disconnected(sid)
