"""

FIXME: for the moment all routings are here and done by hand
"""

import logging

from aiohttp import web
from servicelib.aiohttp import openapi

from . import _handlers

log = logging.getLogger(__name__)


def create(specs: openapi.Spec) -> list[web.RouteDef]:
    # NOTE: consider the case in which server creates routes for both v0 and v1!!!
    # NOTE: should this be taken from servers instead?
    BASEPATH = "/v" + specs.info.version.split(".")[0]

    log.debug("creating %s ", __name__)
    routes = []

    # NOTE: routing will be done automatically using operation_id/tags, etc...

    # storage --
    path, handler = "/storage/locations", _handlers.get_storage_locations
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(BASEPATH + path, handler, name=operation_id))

    path, handler = (
        "/storage/locations/{location_id}:sync",
        _handlers.synchronise_meta_data_table,
    )
    operation_id = specs.paths[path].operations["post"].operation_id
    routes.append(web.post(BASEPATH + path, handler, name=operation_id))

    path, handler = (
        "/storage/locations/{location_id}/datasets",
        _handlers.get_datasets_metadata,
    )
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(BASEPATH + path, handler, name=operation_id))

    path, handle = (
        "/storage/locations/{location_id}/files/metadata",
        _handlers.get_files_metadata,
    )
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(BASEPATH + path, handle, name=operation_id))

    path, handle = (
        "/storage/locations/{location_id}/datasets/{dataset_id}/metadata",
        _handlers.get_files_metadata_dataset,
    )
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(BASEPATH + path, handle, name=operation_id))

    _FILE_PATH = "/storage/locations/{location_id}/files/{file_id}"
    path, handle = (
        f"{_FILE_PATH}/metadata",
        _handlers.get_file_metadata,
    )
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(BASEPATH + path, handle, name=operation_id))

    path, handle = (
        _FILE_PATH,
        _handlers.download_file,
    )
    operation_id = specs.paths[path].operations["get"].operation_id
    routes.append(web.get(BASEPATH + path, handle, name=operation_id))

    path, handle = (
        _FILE_PATH,
        _handlers.delete_file,
    )
    operation_id = specs.paths[path].operations["delete"].operation_id
    routes.append(web.delete(BASEPATH + path, handle, name=operation_id))

    path, handle = (
        _FILE_PATH,
        _handlers.upload_file,
    )
    operation_id = specs.paths[path].operations["put"].operation_id
    routes.append(web.put(BASEPATH + path, handle, name=operation_id))

    path, handle = (
        f"{_FILE_PATH}:complete",
        _handlers.complete_upload_file,
    )
    operation_id = specs.paths[path].operations["post"].operation_id
    routes.append(web.post(BASEPATH + path, handle, name=operation_id))

    path, handle = (
        f"{_FILE_PATH}:abort",
        _handlers.abort_upload_file,
    )
    operation_id = specs.paths[path].operations["post"].operation_id
    routes.append(web.post(BASEPATH + path, handle, name=operation_id))

    path, handle = (
        f"{_FILE_PATH}:complete/futures/{{future_id}}",
        _handlers.is_completed_upload_file,
    )
    operation_id = specs.paths[path].operations["post"].operation_id
    routes.append(web.post(BASEPATH + path, handle, name=operation_id))
    return routes
