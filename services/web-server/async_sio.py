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
    await sio.emit('startModeler', data=result, room=sid)

@sio.on('stopModeler')
async def stopModeler_handler(sid, data):
    result = director_proxy.stop_service(data)
    await sio.emit('stopModeler', data=result, room=sid)

@sio.on('disconnect')
def disconnect(sid):
    print('disconnect ', sid)
