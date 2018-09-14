"""
    Defines **async** handlers for socket.io server


    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/

"""
# pylint: disable=C0111
# pylint: disable=W0703

import logging
import socketio

from s3wrapper.s3_client import S3Client
from simcore_sdk.config.s3 import Config as s3_config

from . import interactive_services_manager

_LOGGER = logging.getLogger(__file__)

# TODO: separate API from server application!
SIO = socketio.AsyncServer(async_mode="aiohttp", logging=_LOGGER)


@SIO.on("connect")
def connect(sid, environ):
    # pylint: disable=W0613
    # environ = WSGI evnironment dictionary
    _LOGGER.debug("client %s connects", sid)
    interactive_services_manager.session_connect(sid)
    return True


@SIO.on("getInteractiveServices")
async def get_interactive_services_handler(sid, data):
    # pylint: disable=C0103
    # pylint: disable=W0613
    _LOGGER.debug("client %s gets interactive services", sid)
    try:
        result = await interactive_services_manager.retrieve_list_of_services()
        await SIO.emit("getInteractiveServices", data=result, room=sid)
    #TODO: see how we handle errors back to the frontend
    except IOError:
        _LOGGER.exception("Error emitting retrieved services")
    except Exception:
        _LOGGER.exception("Error while retrieving interactive services")
    


@SIO.on("startDynamic")
async def start_dynamic_service(sid, data):
    _LOGGER.debug("client %s starts dynamic service %s", sid, data)
    try:
        service_key = data["serviceKey"]
        service_version = "latest"
        # if "serviceVersion" in data:
        #     service_version = data["serviceVersion"]
        node_id = data["nodeId"]
        result = await interactive_services_manager.start_service(sid, service_key, node_id, service_version)
        await SIO.emit("startDynamic", data=result, room=sid)
    except IOError:
        _LOGGER.exception("Error emitting results")
    except Exception:
        _LOGGER.exception("Error while starting service")

@SIO.on("stopDynamic")
async def stop_dynamic_service(sid, data):
    _LOGGER.debug("client %s stops dynamic service %s", sid, data)
    try:
        node_id = data["nodeId"]
        await interactive_services_manager.stop_service(sid, node_id)
    except Exception:
        _LOGGER.exception("Error while stopping service")

@SIO.on("presignedUrl")
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
    try:
        await SIO.emit("presignedUrl", data=data_out, room=sid)
    except IOError:
        _LOGGER.exception("Error emitting results")
    


@SIO.on("listObjects")
async def list_S3_objects(sid, data):
    _LOGGER.debug("client %s requests objects in storage. Extra argument %s", sid, data)
    _config = s3_config()

    s3_client = S3Client(endpoint=_config.endpoint,
        access_key=_config.access_key, secret_key=_config.secret_key)

    objects = s3_client.list_objects_v2(_config.bucket_name)
    data_out = []
    for obj in objects:
        obj_info = {}
        obj_info["path"] = obj.bucket_name + "/" + obj.object_name
        # FIXME: @maiz: this does not work, please review
        #obj_info["lastModified"] = obj.last_modified.isoformat()
        obj_info["size"] = obj.size
        data_out.append(obj_info)
    try:
        await SIO.emit("listObjects", data=data_out, room=sid)
    except IOError:
        _LOGGER.exception("Error emitting results")
    


@SIO.on("disconnect")
async def disconnect(sid):
    _LOGGER.debug("client %s disconnected", sid)
    try:
        await interactive_services_manager.session_disconnected(sid)
    except Exception:
        _LOGGER.exception("Error while disconnecting client")
    


def setup_sio(app):
    _LOGGER.debug("Setting up %s ...", __name__)

    SIO.attach(app)
