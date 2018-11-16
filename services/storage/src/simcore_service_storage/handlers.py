import logging
import time

import attr
from aiohttp import web

from servicelib.rest_utils import extract_and_validate

from . import __version__
from .rest_models import FileMetaDataSchema
from .session import get_session
from .settings import RQT_DSM_KEY

log = logging.getLogger(__name__)


#FIXME: W0613: Unused argument 'request' (unused-argument)
#pylint: disable=W0613

#FIXME: W0612:Unused variable 'fileId'
# pylint: disable=W0612

file_schema  = FileMetaDataSchema()
files_schema = FileMetaDataSchema(many=True)

async def check_health(request: web.Request):
    log.info("CHECK HEALTH INCOMING PATH %s",request.path)

    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert not body

    # we play with session here
    session = await get_session(request)
    data = {
        'name':__name__.split('.')[0],
        'version': __version__,
        'status': 'SERVICE_RUNNING',
        'last_access' : session.get("last", -1.)
    }

    #TODO: servicelib.create_and_validate_response(data)

    session["last"] = time.time()
    return data

async def check_action(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert body, "body %s" % body

    if params['action'] == 'fail':
        raise ValueError("some randome failure")

    # echo's input FIXME: convert to dic
    # FIXME: output = fake_schema.dump(body)
    output = {
    "path_value" : params.get('action'),
    "query_value": query.get('data'),
    "body_value" :{
        "key1": 1, #body.body_value.key1,
        "key2": 0  #body.body_value.key2,
        }
    }
    return output

async def get_storage_locations(request: web.Request):
    log.info("CHECK LOCATION PATH %s %s",request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert not params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert query["user_id"]
    user_id = query["user_id"]
    dsm = request[RQT_DSM_KEY]

    assert dsm

    locs = await dsm.locations(user_id=user_id)
    return {
        'error': None,
        'data': locs
        }


async def get_files_metadata(request: web.Request):
    log.info("GET FILES METADATA %s %s",request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert query["user_id"]
    dsm = request[RQT_DSM_KEY]

    location_id = params["location_id"]
    location = dsm.location_from_id(location_id)
    user_id = query["user_id"]

    uuid_filter = ""
    if query.get("uuid_filter"):
        uuid_filter = query["uuid_filter"]

    log.info("list files %s %s %s", user_id, location, uuid_filter)

    data = await dsm.list_files(user_id=user_id, location=location, uuid_filter=uuid_filter)

    data_as_dict = []
    for d in data:
        log.info("DATA %s",attr.asdict(d))
        data_as_dict.append(attr.asdict(d))

    envelope = {
        'error': None,
        'data': data_as_dict
        }

    return envelope

async def get_file_metadata(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert params["fileId"]
    assert query["user_id"]
    dsm = request[RQT_DSM_KEY]

    location_id = params["location_id"]
    location = dsm.location_from_id(location_id)
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    data = await dsm.list_file(user_id=user_id, location=location, file_uuid=file_uuid)

    data_as_dict = None
    if data:
        data_as_dict = attr.asdict(data)

    envelope = {
        'error': None,
        'data': attr.asdict(data)
        }

    return envelope


async def update_file_meta_data(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert params["fileId"]
    assert query["user_id"]
    dsm = request[RQT_DSM_KEY]

    location_id = params["location_id"]
    location = dsm.location_from_id(location_id)
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    return

async def download_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert params["fileId"]
    assert query["user_id"]
    dsm = request[RQT_DSM_KEY]

    location_id = params["location_id"]
    location = dsm.location_from_id(location_id)
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    link = await dsm.download_link(user_id=user_id, location=location, file_uuid=file_uuid)

    envelope = {
        'error': None,
        'data': {
            "link": link
        }
        }

    return envelope

async def upload_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert params["fileId"]
    assert query["user_id"]
    dsm = request[RQT_DSM_KEY]

    location_id = params["location_id"]
    location = dsm.location_from_id(location_id)
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    if query.get("extra_source") and query.get("extra_location"):
        source_uuid = query["extra_source"]
        source_id = query["extra_location"]
        source_location = dsm.location_from_id(source_id)
        link = await dsm.copy_file(user_id=user_id, dest_location=location,
            dest_uuid=file_uuid, source_location=source_location, source_uuid=source_uuid)

        envelope = {
            'error': None,
            'data': {
                "link": link
            }
            }
    else:
        link = await dsm.upload_link(user_id=user_id, file_uuid=file_uuid)

        envelope = {
            'error': None,
            'data': {
                    "link":link
                }
            }

    return envelope

async def delete_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert params["fileId"]
    assert query["user_id"]
    dsm = request[RQT_DSM_KEY]

    location_id = params["location_id"]
    location = dsm.location_from_id(location_id)
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    data = await dsm.delete_file(user_id=user_id, location=location, file_uuid=file_uuid)

    envelope = {
        'error': None,
        'data': None
        }

    return envelope
