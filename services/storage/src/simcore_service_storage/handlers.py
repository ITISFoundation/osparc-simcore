import asyncio
import json
import logging
import urllib.parse
from contextlib import contextmanager
from typing import Any, Optional

import attr
from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.users import UserID
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from servicelib.aiohttp.rest_utils import extract_and_validate
from settings_library.s3 import S3Settings

# Exclusive for simcore-s3 storage -----------------------
from . import sts
from ._meta import api_vtag
from .access_layer import InvalidFileIdentifier
from .constants import APP_DSM_KEY, DATCORE_STR, SIMCORE_S3_ID, SIMCORE_S3_STR
from .db_tokens import get_api_token_and_secret
from .dsm import DataStorageManager, DatCoreApiToken
from .models import FileMetaDataEx
from .settings import Settings

log = logging.getLogger(__name__)

routes = RouteTableDef()


async def _prepare_storage_manager(
    params: dict, query: dict, request: web.Request
) -> DataStorageManager:
    # FIXME: scope properly, either request or app level!!
    # Notice that every request is changing tokens!
    # I would rather store tokens in request instead of in dsm
    # or creating an different instance of dsm per request

    INIT_STR = "init"
    dsm: DataStorageManager = request.app[APP_DSM_KEY]
    user_id = query.get("user_id")
    location_id = params.get("location_id")
    location = (
        dsm.location_from_id(location_id) if location_id is not None else INIT_STR
    )

    if user_id and location in (INIT_STR, DATCORE_STR):
        # TODO: notify from db instead when tokens changed, then invalidate resource which enforces
        # re-query when needed.

        # updates from db
        token_info = await get_api_token_and_secret(request.app, int(user_id))
        if all(token_info):
            dsm.datcore_tokens[user_id] = DatCoreApiToken(*token_info)
        else:
            dsm.datcore_tokens.pop(user_id, None)
    return dsm


@contextmanager
def handle_storage_errors():
    """Basic policies to translate low-level errors into HTTP errors"""
    # TODO: include _prepare_storage_manager?
    # TODO: middleware? decorator?
    try:

        yield

    except InvalidFileIdentifier as err:
        raise web.HTTPUnprocessableEntity(
            reason=f"{err} is an invalid file identifier"
        ) from err


# HANDLERS ---------------------------------------------------


@routes.get(f"/{api_vtag}/locations", name="get_storage_locations")  # type: ignore
async def get_storage_locations(request: web.Request):
    log.debug("CHECK LOCATION PATH %s %s", request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert not params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    assert query["user_id"]  # nosec

    with handle_storage_errors():
        user_id = query["user_id"]

        dsm = await _prepare_storage_manager(params, query, request)
        locs = await dsm.locations(user_id)

        return {"error": None, "data": locs}


@routes.get(f"/{api_vtag}/locations/{{location_id}}/datasets")  # type: ignore
async def get_datasets_metadata(request: web.Request):
    log.debug("GET METADATA DATASETS %s %s", request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    assert params["location_id"]  # nosec
    assert query["user_id"]  # nosec

    with handle_storage_errors():

        location_id = params["location_id"]
        user_id = query["user_id"]

        dsm = await _prepare_storage_manager(params, query, request)

        location = dsm.location_from_id(location_id)
        # To implement
        data = await dsm.list_datasets(user_id, location)

        return {"error": None, "data": data}


@routes.get(f"/{api_vtag}/locations/{{location_id}}/files/metadata")  # type: ignore
async def get_files_metadata(request: web.Request):
    log.debug("GET FILES METADATA %s %s", request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    assert params["location_id"]  # nosec
    assert query["user_id"]  # nosec

    with handle_storage_errors():
        location_id = params["location_id"]
        user_id = query["user_id"]
        uuid_filter = query.get("uuid_filter", "")

        dsm = await _prepare_storage_manager(params, query, request)
        location = dsm.location_from_id(location_id)

        log.debug("list files %s %s %s", user_id, location, uuid_filter)

        data = await dsm.list_files(
            user_id=user_id, location=location, uuid_filter=uuid_filter
        )

        data_as_dict = []
        for d in data:
            log.info("DATA %s", attr.asdict(d.fmd))
            data_as_dict.append({**attr.asdict(d.fmd), "parent_id": d.parent_id})

        return {"error": None, "data": data_as_dict}


@routes.get(f"/{api_vtag}/locations/{{location_id}}/datasets/{{dataset_id}}/metadata")  # type: ignore
async def get_files_metadata_dataset(request: web.Request):
    log.debug("GET FILES METADATA DATASET %s %s", request.path, request.url)

    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    assert params["location_id"]  # nosec
    assert params["dataset_id"]  # nosec
    assert query["user_id"]  # nosec

    with handle_storage_errors():
        location_id = params["location_id"]
        user_id = query["user_id"]
        dataset_id = params["dataset_id"]

        dsm = await _prepare_storage_manager(params, query, request)

        location = dsm.location_from_id(location_id)

        log.debug("list files %s %s %s", user_id, location, dataset_id)

        data = await dsm.list_files_dataset(
            user_id=user_id, location=location, dataset_id=dataset_id
        )

        data_as_dict = []
        for d in data:
            log.info("DATA %s", attr.asdict(d.fmd))
            data_as_dict.append({**attr.asdict(d.fmd), "parent_id": d.parent_id})

        return {"error": None, "data": data_as_dict}


@routes.get(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}/metadata")  # type: ignore
async def get_file_metadata(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    assert params["location_id"]  # nosec
    assert params["file_id"]  # nosec
    assert query["user_id"]  # nosec

    with handle_storage_errors():
        location_id = params["location_id"]
        user_id = query["user_id"]
        file_uuid = params["file_id"]

        dsm = await _prepare_storage_manager(params, query, request)
        location = dsm.location_from_id(location_id)

        data = await dsm.list_file(
            user_id=user_id, location=location, file_uuid=file_uuid
        )
        # when no metadata is found
        if data is None:
            # NOTE: This is what happens Larry... data must be an empty {} or else some old
            # dynamic services will FAIL (sic)
            return {"error": "No result found", "data": {}}

        return {
            "error": None,
            "data": {**attr.asdict(data.fmd), "parent_id": data.parent_id},
        }


@routes.post(f"/{api_vtag}/locations/{{location_id}}:sync")  # type: ignore
async def synchronise_meta_data_table(request: web.Request):
    params, query, *_ = await extract_and_validate(request)
    assert query["dry_run"] is not None  # nosec
    assert params["location_id"]  # nosec

    with handle_storage_errors():
        location_id: str = params["location_id"]
        fire_and_forget: bool = query["fire_and_forget"]
        dry_run: bool = query["dry_run"]

        dsm = await _prepare_storage_manager(params, query, request)
        location = dsm.location_from_id(location_id)

        sync_results: dict[str, Any] = {
            "removed": [],
        }
        sync_coro = dsm.synchronise_meta_data_table(location, dry_run)

        if fire_and_forget:
            settings: Settings = request.app[APP_CONFIG_KEY]

            async def _go():
                timeout = settings.STORAGE_SYNC_METADATA_TIMEOUT
                try:
                    result = await asyncio.wait_for(sync_coro, timeout=timeout)
                    log.info(
                        "Sync metadata table completed: %d entries removed",
                        len(result.get("removed", [])),
                    )
                except asyncio.TimeoutError:
                    log.error("Sync metadata table timed out (%s seconds)", timeout)

            asyncio.create_task(_go(), name="fire&forget sync_task")
        else:
            sync_results = await sync_coro

        sync_results["fire_and_forget"] = fire_and_forget
        sync_results["dry_run"] = dry_run

        return {"error": None, "data": sync_results}


@routes.patch(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}/metadata")  # type: ignore
async def update_file_meta_data(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    with handle_storage_errors():
        file_uuid = urllib.parse.unquote_plus(params["file_id"])
        user_id = query["user_id"]

        dsm = await _prepare_storage_manager(params, query, request)

        data: Optional[FileMetaDataEx] = await dsm.update_metadata(
            file_uuid=file_uuid, user_id=user_id
        )
        if data is None:
            raise web.HTTPNotFound(reason=f"Could not update metadata for {file_uuid}")

        return {
            "error": None,
            "data": {**attr.asdict(data.fmd), "parent_id": data.parent_id},
        }


@routes.get(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}")  # type: ignore
async def download_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    assert params["location_id"]  # nosec
    assert params["file_id"]  # nosec
    assert query["user_id"]  # nosec
    link_type = query.get("link_type", "presigned")

    with handle_storage_errors():
        location_id = params["location_id"]
        user_id = query["user_id"]
        file_uuid = params["file_id"]

        if int(location_id) != SIMCORE_S3_ID:
            raise web.HTTPPreconditionFailed(
                reason=f"Only allowed to fetch s3 link for '{SIMCORE_S3_STR}'"
            )

        dsm = await _prepare_storage_manager(params, query, request)
        location = dsm.location_from_id(location_id)
        if location == SIMCORE_S3_STR:
            link = await dsm.download_link_s3(
                file_uuid, user_id, as_presigned_link=bool(link_type == "presigned")
            )
        else:
            link = await dsm.download_link_datcore(user_id, file_uuid)

        return {"error": None, "data": {"link": link}}


@routes.put(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}")  # type: ignore
async def upload_file(request: web.Request):
    params, query, body = await extract_and_validate(request)
    log.debug("received call to upload_file with %s", f"{params=}, {query=}, {body=}")
    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec
    link_type = query.get("link_type", "presigned")

    with handle_storage_errors():
        user_id = query["user_id"]
        file_uuid = params["file_id"]

        dsm = await _prepare_storage_manager(params, query, request)

        link = await dsm.upload_link(
            user_id=user_id,
            file_uuid=file_uuid,
            as_presigned_link=bool(link_type == "presigned"),
        )

    return {"error": None, "data": {"link": link}}


@routes.delete(f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}")  # type: ignore
async def delete_file(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    assert params["location_id"]  # nosec
    assert params["file_id"]  # nosec
    assert query["user_id"]  # nosec

    with handle_storage_errors():
        location_id = params["location_id"]
        user_id = query["user_id"]
        file_uuid = params["file_id"]

        dsm = await _prepare_storage_manager(params, query, request)
        location = dsm.location_from_id(location_id)
        await dsm.delete_file(user_id=user_id, location=location, file_uuid=file_uuid)

        return {"error": None, "data": None}


@routes.post(f"/{api_vtag}/simcore-s3:access")
async def get_or_create_temporary_s3_access(request: web.Request):
    user_id = UserID(request.query["user_id"])
    with handle_storage_errors():
        s3_settings: S3Settings = await sts.get_or_create_temporary_token_for_user(
            request.app, user_id
        )
        return {"data": s3_settings.dict()}


@routes.post(f"/{api_vtag}/simcore-s3/folders", name="copy_folders_from_project")  # type: ignore
async def create_folders_from_project(request: web.Request):
    # FIXME: Update openapi-core. Fails with additionalProperties https://github.com/p1c2u/openapi-core/issues/124. Fails with project
    # params, query, body = await extract_and_validate(request)
    user_id = request.query["user_id"]

    body = await request.json()
    source_project = body.get("source", {})
    destination_project = body.get("destination", {})
    nodes_map = body.get("nodes_map", {})

    assert set(nodes_map.keys()) == set(source_project["workbench"].keys())  # nosec
    assert set(nodes_map.values()) == set(  # nosec
        destination_project["workbench"].keys()  # nosec
    )  # nosec

    # TODO: validate project with jsonschema instead??
    with handle_storage_errors():
        dsm = await _prepare_storage_manager(
            params={"location_id": SIMCORE_S3_ID},
            query={"user_id": user_id},
            request=request,
        )
        await dsm.deep_copy_project_simcore_s3(
            user_id, source_project, destination_project, nodes_map
        )

    raise web.HTTPCreated(
        text=json.dumps(destination_project), content_type="application/json"
    )


@routes.delete(f"/{api_vtag}/simcore-s3/folders/{{folder_id}}")  # type: ignore
async def delete_folders_of_project(request: web.Request):
    folder_id = request.match_info["folder_id"]
    user_id = request.query["user_id"]
    node_id = request.query.get("node_id", None)

    with handle_storage_errors():
        dsm = await _prepare_storage_manager(
            params={"location_id": SIMCORE_S3_ID},
            query={"user_id": user_id},
            request=request,
        )
        await dsm.delete_project_simcore_s3(user_id, folder_id, node_id)

    raise web.HTTPNoContent(content_type="application/json")


@routes.post(f"/{api_vtag}/simcore-s3/files/metadata:search")  # type: ignore
async def search_files_starting_with(request: web.Request):
    params, query, body = await extract_and_validate(request)
    assert not params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert not body, "body %s" % body  # nosec

    assert query["user_id"]  # nosec
    assert query["startswith"]  # nosec

    with handle_storage_errors():

        user_id = int(query["user_id"])
        startswith = query["startswith"]

        dsm = await _prepare_storage_manager(
            {"location_id": SIMCORE_S3_ID}, {"user_id": user_id}, request
        )

        data = await dsm.search_files_starting_with(int(user_id), prefix=startswith)
        log.debug("Found %d files starting with '%s'", len(data), startswith)

        return [{**attr.asdict(d.fmd), "parent_id": d.parent_id} for d in data]


@routes.post(f"/{api_vtag}/files/{{file_id}}:soft-copy", name="copy_as_soft_link")  # type: ignore
async def copy_as_soft_link(request: web.Request):
    # TODO: error handling
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert body, "body %s" % body  # nosec

    with handle_storage_errors():
        target_uuid = params["file_id"]
        user_id = int(query["user_id"])
        link_uuid = body.link_id

        dsm = await _prepare_storage_manager(
            {"location_id": SIMCORE_S3_ID}, {"user_id": user_id}, request
        )

        file_link = await dsm.create_soft_link(user_id, target_uuid, link_uuid)

        data = {**attr.asdict(file_link.fmd), "parent_id": file_link.parent_id}
        return data
