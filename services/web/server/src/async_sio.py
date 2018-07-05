"""
    Defines **async** handlers for socket.io server


    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/

"""
# pylint: disable=C0111


import logging
import os

import socketio

import config
import interactive_services_manager
from s3wrapper.s3_client import S3Client
from simcore_sdk.config.s3 import Config as s3_config

_LOGGER = logging.getLogger(__file__)

SIO = socketio.AsyncServer(async_mode='aiohttp')

CONFIG = config.CONFIG[os.environ.get('SIMCORE_WEB_CONFIG', 'default')]


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


@SIO.on('startDynamic')
async def start_dynamic_service(sid, data):
    service_name = data['serviceName']
    node_id = data['nodeId']
    _LOGGER.debug("client %s requests start %s", sid, service_name)
    result = interactive_services_manager.start_service(sid, service_name, node_id)
    # TODO: Connection failure raises exception that is not treated, which stops the webserver
    # Add mechanism to handle these situations (retry, abandon...)
    try:
        await SIO.emit('startDynamic', data=result, room=sid)
    except IOError as err:
        _LOGGER.exception(err)


@SIO.on('stopDynamic')
def stop_dynamic_service(sid, data):
    node_id = data['nodeId']
    _LOGGER.debug("client %s requests stop %s", sid, node_id)
    interactive_services_manager.stop_service(sid, node_id)


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


@SIO.on('presignedUrl')
async def retrieve_url_for_file(sid, data):
    _LOGGER.debug("client %s requests S3 url for %s", sid, data)
    _config = s3_config()
    _LOGGER.debug("S3 endpoint %s", _config.endpoint)


    s3_client = S3Client(endpoint=_config.endpoint,
        access_key=_config.access_key, secret_key=_config.secret_key)
    url = s3_client.create_presigned_put_url(_config.bucket_name, data["fileName"])
    #result = minioClient.presigned_put_object(data["bucketName"], data["fileName"])
    # Response error is still possible since internally presigned does get
    # bucket location.
    data_out = {}
    data_out["url"] = url
    await SIO.emit('presignedUrl', data=data_out, room=sid)


@SIO.on('listObjects')
async def list_S3_objects(sid, data):
    _LOGGER.debug("client %s requests objects in storage. Extra argument %s", sid, data)
    _config = s3_config()

    s3_client = S3Client(endpoint=_config.endpoint,
        access_key=_config.access_key, secret_key=_config.secret_key)

    objects = s3_client.list_objects_v2(_config.bucket_name)
    data_out = []
    for obj in objects:
        obj_info = {}
        obj_info['path'] = obj.bucket_name + '/' + obj.object_name
        # @maiz: this does not work, please review
        #obj_info['lastModified'] = obj.last_modified.isoformat()
        obj_info['size'] = obj.size
        data_out.append(obj_info)
    await SIO.emit('listObjects', data=data_out, room=sid)


@SIO.on('disconnect')
def disconnect(sid):
    _LOGGER.debug("client %s disconnected", sid)
    interactive_services_manager.session_disconnected(sid)
