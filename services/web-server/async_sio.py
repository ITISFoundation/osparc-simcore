"""
    Defines **async** handlers for socket.io server


    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/

"""
# pylint: disable=C0111
# pylint: disable=C0103
import logging
import json
import socketio
import director_proxy

_LOGGER = logging.getLogger(__file__)

sio = socketio.AsyncServer(async_mode='aiohttp')

@sio.on('connect')
def connect(sid, environ):
    # environ = WSGI evnironment dictionary
    print("connect ", sid, environ)
    return True

@sio.on('getInteractiveServices')
async def get_interactive_services_handler(sid, data):
    result = director_proxy.retrieve_interactive_services()
    await sio.emit('getInteractiveServices', data=result, room=sid)

@sio.on('startModeler')
async def startModeler_handler(sid, data):
    result = director_proxy.start_service('modeler', data)
    # TODO: Connection failure raises exception that is not treated, which stops the webserver
    # Add mechanism to handle these situations (retry, abandon...)
    try:
      await sio.emit('startModeler', data=result, room=sid)
    except ErrorIO as ee:
      _LOGGER.exception(ee)

@sio.on('stopModeler')
async def stopModeler_handler(sid, data):
    result = director_proxy.stop_service(data)
    await sio.emit('stopModeler', data=result, room=sid)

@sio.on('startJupyter')
async def startJupyter_handler(sid, data):
    result = director_proxy.start_service('jupyter-base-notebook', data)
    await sio.emit('startJupyter', data=result, room=sid)

@sio.on('stopJupyter')
async def stopJupyter_handler(sid, data):
    result = director_proxy.stop_service(data)
    await sio.emit('stopJupyter', data=result, room=sid)

@sio.on('disconnect')
def disconnect(sid):
    print('disconnect ', sid)
