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
import interactive_services_manager

_LOGGER = logging.getLogger(__file__)

sio = socketio.AsyncServer(async_mode='aiohttp')


@sio.on('connect')
def connect(sid, environ):
    # environ = WSGI evnironment dictionary
    _LOGGER.debug("client %s connects", sid)
    interactive_services_manager.session_connect(sid)
    return True

@sio.on('getInteractiveServices')
async def get_interactive_services_handler(sid, data):
  _LOGGER.debug("client %s gets interactive services", sid)
  result = retrieve_list_of_services.retrieve_list_of_services()
  await sio.emit('getInteractiveServices', data=result, room=sid)

@sio.on('startModeler')
async def startModeler_handler(sid, data):
  _LOGGER.debug("client %s starts modeler %s", sid, data)
  result = interactive_services_manager.start_service(sid, 'modeler', data)
  # TODO: Connection failure raises exception that is not treated, which stops the webserver
  # Add mechanism to handle these situations (retry, abandon...)
  try:
    await sio.emit('startModeler', data=result, room=sid)
  except ErrorIO as ee:
    _LOGGER.exception(ee)

@sio.on('stopModeler')
async def stopModeler_handler(sid, data):
  _LOGGER.debug("client %s stops modeler %s", sid, data)
  result = interactive_services_manager.stop_service(sid, data)
  await sio.emit('stopModeler', data=result, room=sid)

@sio.on('startJupyter')
async def startJupyter_handler(sid, data):
  _LOGGER.debug("client %s starts jupyter %s", sid, data)
  result = interactive_services_manager.start_service(sid, 'jupyter-base-notebook', data)
  await sio.emit('startJupyter', data=result, room=sid)


@sio.on('stopJupyter')
async def stopJupyter_handler(sid, data):
  _LOGGER.debug("client %s stops jupyter %s", sid, data)
  result = interactive_services_manager.stop_service(sid, data)
  await sio.emit('stopJupyter', data=result, room=sid)


@sio.on('disconnect')
def disconnect(sid):
  _LOGGER.debug("client %s disconnected", sid)
  interactive_services_manager.session_disconnected(sid)
