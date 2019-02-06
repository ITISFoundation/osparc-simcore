import logging

import attr
from aiohttp import web

from servicelib.rest_utils import extract_and_validate

from . import __version__
from .db_tokens import get_api_token_and_secret
from .dsm import DataStorageManager, DatCoreApiToken
from .rest_models import FileMetaDataSchema
from .settings import APP_DSM_KEY, DATCORE_STR

log = logging.getLogger(__name__)

file_schema  = FileMetaDataSchema()
files_schema = FileMetaDataSchema(many=True)



async def check_health(request: web.Request):
    log.info("CHECK HEALTH INCOMING PATH %s",request.path)
    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert not body

    return {
        'name':__name__.split('.')[0],
        'version': __version__,
        'status': 'SERVICE_RUNNING'
    }


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
    log.debug("CHECK LOCATION PATH %s %s",request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert not params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert query["user_id"]
    user_id = query["user_id"]

    dsm = await _prepare_storage_manager(params, query, request)
    locs = await dsm.locations(user_id)

    return {
        'error': None,
        'data': locs
        }


async def get_files_metadata(request: web.Request):
    log.debug("GET FILES METADATA %s %s",request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert query["user_id"]

    location_id = params["location_id"]
    user_id = query["user_id"]
    uuid_filter = query.get("uuid_filter", "")

    dsm = await _prepare_storage_manager(params, query, request)
    location = dsm.location_from_id(location_id)

    log.debug("list files %s %s %s", user_id, location, uuid_filter)

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

    location_id = params["location_id"]
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    dsm = await _prepare_storage_manager(params, query, request)
    location = dsm.location_from_id(location_id)

    data = await dsm.list_file(user_id=user_id, location=location, file_uuid=file_uuid)

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

    location_id = params["location_id"]
    _user_id = query["user_id"]
    _file_uuid = params["fileId"]

    dsm = await _prepare_storage_manager(params, query, request)
    _location = dsm.location_from_id(location_id)



async def download_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert params["fileId"]
    assert query["user_id"]

    location_id = params["location_id"]
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    dsm = await _prepare_storage_manager(params, query, request)
    location = dsm.location_from_id(location_id)

    link = await dsm.download_link(user_id=user_id, location=location, file_uuid=file_uuid)

    return {
        'error': None,
        'data': {
            "link": link
            }
        }


async def upload_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    location_id = params["location_id"]
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    dsm = await _prepare_storage_manager(params, query, request)
    location = dsm.location_from_id(location_id)

    if query.get("extra_source") and query.get("extra_location"):
        source_uuid = query["extra_source"]
        source_id = query["extra_location"]
        source_location = dsm.location_from_id(source_id)

        link = await dsm.copy_file(user_id=user_id, dest_location=location,
            dest_uuid=file_uuid, source_location=source_location, source_uuid=source_uuid)
    else:
        link = await dsm.upload_link(user_id=user_id, file_uuid=file_uuid)

    return {
            'error': None,
            'data': {
                    "link":link
                }
            }


async def delete_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params
    assert query, "query %s" % query
    assert not body, "body %s" % body

    assert params["location_id"]
    assert params["fileId"]
    assert query["user_id"]

    location_id = params["location_id"]
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    dsm = await _prepare_storage_manager(params, query, request)
    location = dsm.location_from_id(location_id)
    _discard = await dsm.delete_file(user_id=user_id, location=location, file_uuid=file_uuid)

    return {
        'error': None,
        'data': None
        }


# HELPERS -----------------------------------------------------
INIT_STR = "init"

async def _prepare_storage_manager(params, query, request: web.Request) -> DataStorageManager:
    dsm = request.app[APP_DSM_KEY]

    user_id = query.get("user_id")
    location_id = params.get("location_id")
    location = dsm.location_from_id(location_id) if location_id else INIT_STR

    if user_id and location in (INIT_STR, DATCORE_STR):
        # TODO: notify from db instead when tokens changed, then invalidate resource which enforces
        # re-query when needed.

        # updates from db
        token_info = await get_api_token_and_secret(request, user_id)
        if all(token_info):
            dsm.datcore_tokens[user_id] = DatCoreApiToken(*token_info)
        else:
            dsm.datcore_tokens.pop(user_id, None)
    return dsm
