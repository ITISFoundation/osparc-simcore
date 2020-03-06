import json
import logging

import attr
from aiohttp import web

from servicelib.rest_utils import extract_and_validate

from . import __version__
from .db_tokens import get_api_token_and_secret
from .dsm import DataStorageManager, DatCoreApiToken
from .rest_models import FileMetaDataSchema
from .settings import APP_DSM_KEY, DATCORE_STR, SIMCORE_S3_ID, SIMCORE_S3_STR

log = logging.getLogger(__name__)

file_schema  = FileMetaDataSchema()
files_schema = FileMetaDataSchema(many=True)



async def check_health(request: web.Request):
    log.debug("CHECK HEALTH INCOMING PATH %s",request.path)
    await extract_and_validate(request)

    return {
        'name':__name__.split('.')[0],
        'version': __version__,
        'status': 'SERVICE_RUNNING'
    }


async def check_action(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert body, "body %s" % body # nosec

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

    assert not params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

    assert query["user_id"] # nosec
    user_id = query["user_id"]

    dsm = await _prepare_storage_manager(params, query, request)
    locs = await dsm.locations(user_id)

    return {
        'error': None,
        'data': locs
        }


async def get_datasets_metadata(request: web.Request):
    log.debug("GET METADATA DATASETS %s %s",request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

    assert params["location_id"] # nosec
    assert query["user_id"] # nosec

    location_id = params["location_id"]
    user_id = query["user_id"]

    dsm = await _prepare_storage_manager(params, query, request)

    location = dsm.location_from_id(location_id)
    # To implement
    data = await dsm.list_datasets(user_id, location)

    return {
        'error': None,
        'data': data
        }

async def get_files_metadata(request: web.Request):
    log.debug("GET FILES METADATA %s %s",request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

    assert params["location_id"] # nosec
    assert query["user_id"] # nosec

    location_id = params["location_id"]
    user_id = query["user_id"]
    uuid_filter = query.get("uuid_filter", "")

    dsm = await _prepare_storage_manager(params, query, request)
    location = dsm.location_from_id(location_id)

    log.debug("list files %s %s %s", user_id, location, uuid_filter)

    data = await dsm.list_files(user_id=user_id, location=location, uuid_filter=uuid_filter)

    data_as_dict = []
    for d in data:
        log.info("DATA %s",attr.asdict(d.fmd))
        data_as_dict.append({**attr.asdict(d.fmd), 'parent_id': d.parent_id})

    envelope = {
        'error': None,
        'data': data_as_dict
        }

    return envelope

async def get_files_metadata_dataset(request: web.Request):
    log.debug("GET FILES METADATA DATASET %s %s",request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

    assert params["location_id"] # nosec
    assert params["dataset_id"] # nosec
    assert query["user_id"] # nosec

    location_id = params["location_id"]
    user_id = query["user_id"]
    dataset_id = params["dataset_id"]

    dsm = await _prepare_storage_manager(params, query, request)

    location = dsm.location_from_id(location_id)

    log.debug("list files %s %s %s", user_id, location, dataset_id)

    data = await dsm.list_files_dataset(user_id=user_id, location=location, dataset_id=dataset_id)

    data_as_dict = []
    for d in data:
        log.info("DATA %s",attr.asdict(d.fmd))
        data_as_dict.append({**attr.asdict(d.fmd), 'parent_id': d.parent_id})

    envelope = {
        'error': None,
        'data': data_as_dict
        }

    return envelope


async def get_file_metadata(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

    assert params["location_id"] # nosec
    assert params["fileId"] # nosec
    assert query["user_id"] # nosec

    location_id = params["location_id"]
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    dsm = await _prepare_storage_manager(params, query, request)
    location = dsm.location_from_id(location_id)

    data = await dsm.list_file(user_id=user_id, location=location, file_uuid=file_uuid)

    envelope = {
        'error': None,
        'data': {**attr.asdict(data.fmd), 'parent_id': data.parent_id}
        }

    return envelope


async def update_file_meta_data(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

    assert params["location_id"] # nosec
    assert params["fileId"] # nosec
    assert query["user_id"] # nosec

    location_id = params["location_id"]
    _user_id = query["user_id"]
    _file_uuid = params["fileId"]

    dsm = await _prepare_storage_manager(params, query, request)
    _location = dsm.location_from_id(location_id)


async def download_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

    assert params["location_id"] # nosec
    assert params["fileId"] # nosec
    assert query["user_id"] # nosec

    location_id = params["location_id"]
    user_id = query["user_id"]
    file_uuid = params["fileId"]

    dsm = await _prepare_storage_manager(params, query, request)
    location = dsm.location_from_id(location_id)
    if location == SIMCORE_S3_STR:
        link = await dsm.download_link_s3(file_uuid=file_uuid)
    else:
        link, _filename = await dsm.download_link_datcore(user_id, file_uuid)

    return {
        'error': None,
        'data': {
            "link": link
            }
        }


async def upload_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

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

    assert params, "params %s" % params # nosec
    assert query, "query %s" % query # nosec
    assert not body, "body %s" % body # nosec

    assert params["location_id"] # nosec
    assert params["fileId"] # nosec
    assert query["user_id"] # nosec

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


async def create_folders_from_project(request: web.Request):
    #FIXME: Update openapi-core. Fails with additionalProperties https://github.com/p1c2u/openapi-core/issues/124. Fails with project
    # params, query, body = await extract_and_validate(request)

    user_id = request.query.get("user_id")

    body = await request.json()
    source_project = body.get('source', {})
    destination_project = body.get('destination', {})
    nodes_map = body.get('nodes_map', {})

    assert set(nodes_map.keys()) == set(source_project['workbench'].keys())         # nosec
    assert set(nodes_map.values()) == set(destination_project['workbench'].keys())  # nosec

    # TODO: validate project with jsonschema instead??
    params = { "location_id" : SIMCORE_S3_ID }
    query = { "user_id": user_id}
    dsm = await _prepare_storage_manager(params, query, request)
    await dsm.deep_copy_project_simcore_s3(user_id, source_project, destination_project, nodes_map)

    raise web.HTTPCreated(text=json.dumps(destination_project),
                                content_type='application/json')

async def delete_folders_of_project(request: web.Request):
    folder_id = request.match_info['folder_id']
    user_id = request.query.get("user_id")
    node_id = request.query.get("node_id", None)

    params = { "location_id" : SIMCORE_S3_ID }
    query = { "user_id": user_id}
    dsm = await _prepare_storage_manager(params, query, request)
    await dsm.delete_project_simcore_s3(user_id, folder_id, node_id)

    raise web.HTTPNoContent(content_type='application/json')





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
