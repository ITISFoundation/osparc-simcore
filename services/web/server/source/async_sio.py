"""
    Defines **async** handlers for socket.io server


    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/

"""
# pylint: disable=C0111


import logging
import socketio
import interactive_services_manager

from minio import Minio
from minio.error import ResponseError

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


@SIO.on('presignedUrl')
async def retrieveURLForFile(sid, data):
    _LOGGER.debug("client %s requests S3 url for %s", sid, data)
    try:
        public_url = 'play.minio.io:9000'
        public_access_key = 'Q3AM3UQ867SPQQA43P2F'
        public_secret_key ='zuf+tfteSlswRu7BJ86wekitnifILbZam1KYY3TG'
        minioClient = Minio(
            public_url, 
            access_key=public_access_key,
            secret_key=public_secret_key)
        bucketName = 'maiz'
        result = minioClient.presigned_put_object(bucketName, data)
        # Response error is still possible since internally presigned does get
        # bucket location.
        await SIO.emit('presignedUrl', data=result, room=sid)
    except ResponseError as err:
        print(err)


@SIO.on('listObjects')
async def listS3Objects(sid, data):
    _LOGGER.debug("client %s requests S3 data in %s", sid, data)
    try:
        public_url = 'play.minio.io:9000'
        public_access_key = 'Q3AM3UQ867SPQQA43P2F'
        public_secret_key ='zuf+tfteSlswRu7BJ86wekitnifILbZam1KYY3TG'
        minioClient = Minio(
            public_url, 
            access_key=public_access_key,
            secret_key=public_secret_key)
        
        objects = minioClient.list_objects_v2('simcore')
        for obj in objects:
            print(obj.bucket_name, obj.object_name.encode('utf-8'), obj.last_modified,
                obj.etag, obj.size, obj.content_type)
            obj.objectName = obj.object_name.encode('utf-8')
            obj.lastModified = obj.last_modified
            await SIO.emit('listObjectsPub', data=obj, room=sid)
        
        objects = minioClient.list_objects_v2(data)
        for obj in objects:
            print(obj.bucket_name, obj.object_name.encode('utf-8'), obj.last_modified,
                obj.etag, obj.size, obj.content_type)
            obj.objectName = obj.object_name.encode('utf-8')
            obj.lastModified = obj.last_modified
            await SIO.emit('listObjectsUser', data=obj, room=sid)

    except ResponseError as err:
        print(err)


@SIO.on('disconnect')
def disconnect(sid):
    _LOGGER.debug("client %s disconnected", sid)
    interactive_services_manager.session_disconnected(sid)
