""" Storage subsystem's API: responsible of communication with storage service

"""
import asyncio
import logging
from pprint import pformat
from typing import Any, Dict, Tuple

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from pydantic.types import PositiveInt
from servicelib.aiohttp.rest_responses import unwrap_envelope
from yarl import URL

from .storage_config import get_client_session, get_storage_config

log = logging.getLogger(__name__)

TOTAL_TIMEOUT_TO_COPY_DATA_SECS = 60 * 60


def _get_storage_client(app: web.Application) -> Tuple[ClientSession, URL]:
    cfg = get_storage_config(app)

    # storage service API endpoint
    endpoint = URL.build(scheme="http", host=cfg["host"], port=cfg["port"]).with_path(
        cfg["version"]
    )

    session = get_client_session(app)
    return session, endpoint


async def copy_data_folders_from_project(
    app: web.Application,
    source_project: Dict,
    destination_project: Dict,
    nodes_map: Dict,
    user_id: int,
):
    # TODO: optimize if project has actualy data or not before doing the call
    client, api_endpoint = _get_storage_client(app)
    log.debug("Coying %d nodes", len(nodes_map))

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
        # NOTE: extends time for copying operation
        timeout=ClientTimeout(total=TOTAL_TIMEOUT_TO_COPY_DATA_SECS),
    ) as resp:
        payload = await resp.json()

        # FIXME: relying on storage to change the project is not a good idea since
        # it is not storage responsibility to deal with projects
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
    app, project_id: str, node_id: str, user_id: PositiveInt
):
    # SEE api/specs/storage/v0/openapi.yaml
    session, api_endpoint = _get_storage_client(app)
    url = (api_endpoint / f"simcore-s3/folders/{project_id}").with_query(
        user_id=user_id, node_id=node_id
    )

    await _delete(session, url)


async def is_healthy(app: web.Application) -> bool:
    try:
        client, api_endpoint = _get_storage_client(app)
        await client.get(
            url=(api_endpoint / ""),
            raise_for_status=True,
            ssl=False,
            timeout=ClientTimeout(total=2, connect=1),
        )
        return True
    except (ClientError, asyncio.TimeoutError) as err:
        # ClientResponseError, ClientConnectionError, ClientPayloadError, InValidURL
        log.debug("Storage is NOT healthy: %s", err)
        return False


async def get_app_status(app: web.Application) -> Dict[str, Any]:
    client, api_endpoint = _get_storage_client(app)

    data = {}
    async with client.get(
        url=api_endpoint / "status",
    ) as resp:
        payload = await resp.json()
        data = payload["data"]

    return data
