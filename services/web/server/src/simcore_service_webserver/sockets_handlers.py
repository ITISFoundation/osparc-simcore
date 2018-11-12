""" Defines **async** handlers for socket.io server

    SEE https://pypi.python.org/pypi/python-socketio
    SEE http://python-socketio.readthedocs.io/en/latest/
"""
# pylint: disable=C0111
# pylint: disable=W0703

import logging

import socketio

from s3wrapper.s3_client import S3Client
from simcore_sdk.config.s3 import Config as s3_config
# TODO: this is the only config that is not part of the schema
# At first sight, adding it would require refactorin how socketio
# is setup and avoid sio as a singleton!

from .director import interactive_services_manager

log = logging.getLogger(__file__)

# TODO: separate API from server application!
sio = socketio.AsyncServer(async_mode="aiohttp", logging=log)


@sio.on("connect")
def connect(sid, environ):
    # pylint: disable=W0613
    # environ = WSGI evnironment dictionary
    log.debug("client %s connects", sid)
    interactive_services_manager.session_connect(sid)
    return True

@sio.on("startDynamic")
async def start_dynamic_service(sid, data):
    log.debug("client %s starts dynamic service %s", sid, data)
    try:
        service_key = data["serviceKey"]
        service_version = "latest"
        # if "serviceVersion" in data:
        #     service_version = data["serviceVersion"]
        node_id = data["nodeId"]
        result = await interactive_services_manager.start_service(sid, service_key, node_id, service_version)
        await sio.emit("startDynamic", data=result, room=sid)
    except IOError:
        log.exception("Error emitting results")
    except Exception:
        log.exception("Error while starting service")

@sio.on("stopDynamic")
async def stop_dynamic_service(sid, data):
    log.debug("client %s stops dynamic service %s", sid, data)
    try:
        node_id = data["nodeId"]
        await interactive_services_manager.stop_service(sid, node_id)
    except Exception:
        log.exception("Error while stopping service")

@sio.on("presignedUrl")
async def retrieve_url_for_file(sid, data):
    log.debug("client %s requests S3 url for %s", sid, data)
    _config = s3_config()
    log.debug("S3 endpoint %s", _config.endpoint)


    s3_client = S3Client(endpoint=_config.endpoint,
        access_key=_config.access_key, secret_key=_config.secret_key)
    url = s3_client.create_presigned_put_url(_config.bucket_name, data["fileName"])
    #result = minioClient.presigned_put_object(data["bucketName"], data["fileName"])
    # Response error is still possible since internally presigned does get
    # bucket location.
    data_out = {}
    data_out["url"] = url
    try:
        await sio.emit("presignedUrl", data=data_out, room=sid)
    except IOError:
        log.exception("Error emitting results")

@sio.on("listObjects")
async def list_S3_objects(sid, data):
    log.debug("client %s requests objects in storage. Extra argument %s", sid, data)
    _config = s3_config()

    s3_client = S3Client(endpoint=_config.endpoint,
        access_key=_config.access_key, secret_key=_config.secret_key)

    objects = s3_client.list_objects_v2(_config.bucket_name)
    data_out = []
    location = "simcore.sandbox"
    for obj in objects:
        obj_info = {}
        obj_info["file_uuid"] = obj.bucket_name + "/" + obj.object_name
        obj_info["location"] = location
        obj_info["bucket_name"] = obj.bucket_name
        obj_info["object_name"] = obj.object_name
        obj_info["size"] = obj.size
        data_out.append(obj_info)
    try:
        await sio.emit("listObjects", data=data_out, room=sid)
    except IOError:
        log.exception("Error emitting results")

@sio.on("disconnect")
async def disconnect(sid):
    log.debug("client %s disconnected", sid)
    try:
        await interactive_services_manager.session_disconnected(sid)
    except Exception:
        log.exception("Error while disconnecting client")
