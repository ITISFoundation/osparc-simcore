""" Storage subsystem's API: responsible of communication with storage service

"""
import logging
from pprint import pformat

from aiohttp import web
from servicelib.rest_responses import unwrap_envelope
from yarl import URL

from .storage_config import get_client_session, get_config

log = logging.getLogger(__name__)


def _get_storage_client(app: web.Application):
    cfg = get_config(app)

    # storage service API endpoint
    endpoint = URL.build(scheme="http", host=cfg["host"], port=cfg["port"]).with_path(
        cfg["version"]
    )

    session = get_client_session(app)
    return session, endpoint


async def copy_data_folders_from_project(
    app, source_project, destination_project, nodes_map, user_id
):
    # TODO: optimize if project has actualy data or not before doing the call
    client, api_endpoint = _get_storage_client(app)

    # /simcore-s3/folders:
    url = (api_endpoint / "simcore-s3/folders").with_query(user_id=user_id)
    async with client.post(
        url,
        json={
            "source": source_project,
            "destination": destination_project,
            "nodes_map": nodes_map,
        },
        ssl=False,
    ) as resp:
        payload = await resp.json()
        updated_project, error = unwrap_envelope(payload)
        if error:
            msg = "Cannot copy project data in storage: %s" % pformat(error)
            log.error(msg)
            # TODO: should reconstruct error and rethrow same exception as storage service?
            raise web.HTTPServiceUnavailable(reason=msg)

        return updated_project


async def _delete(session, target_url):
    async with session.delete(target_url, ssl=False) as resp:
        log.info(
            "delete_data_folders_of_project request responded with status %s",
            resp.status,
        )
        # NOTE: context will automatically close connection


async def delete_data_folders_of_project(app, project_id, user_id):
    # SEE api/specs/storage/v0/openapi.yaml
    session, api_endpoint = _get_storage_client(app)
    url = (api_endpoint / f"simcore-s3/folders/{project_id}").with_query(
        user_id=user_id
    )

    await _delete(session, url)


async def delete_data_folders_of_project_node(
    app, project_id: str, node_id: str, user_id: str
):
    # SEE api/specs/storage/v0/openapi.yaml
    session, api_endpoint = _get_storage_client(app)
    url = (api_endpoint / f"simcore-s3/folders/{project_id}").with_query(
        user_id=user_id, node_id=node_id
    )

    await _delete(session, url)
