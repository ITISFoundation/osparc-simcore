
import asyncio
import logging
from pprint import pformat

from aiohttp import web
from yarl import URL

from servicelib.rest_responses import unwrap_envelope

from .storage_config import get_client_session, get_config

log = logging.getLogger(__name__)


def _get_storage_client(app: web.Application):
    cfg = get_config(app)

    # storage service API endpoint
    endpoint = URL.build(scheme='http',
                         host=cfg['host'],
                         port=cfg['port']).with_path(cfg["version"])

    session = get_client_session(app)
    return session, endpoint


async def copy_data_folders_from_project(app, source_project, destination_project, nodes_map):
    # TODO: optimize if project has actualy data or not before doing the call
    client, api_endpoint = _get_storage_client(app)

    url = api_endpoint / "simcore-s3/folders"
    async with client.post( url , json={
        'source':source_project,
        'destination': destination_project,
        'nodes_map': nodes_map
    }, ssl=False) as resp:
        payload = await resp.json()
        updated_project, error = unwrap_envelope(payload)
        if error:
            msg = "Cannot copy project data in storage: %s" % pformat(error)
            log.error(msg)
            # TODO: should reconstruct error and rethrow same exception as storage service?
            raise web.HTTPServiceUnavailable(reason=msg)

        return updated_project


def delete_data_folders_of_project(app, project_id, user_id):
    client, api_endpoint = _get_storage_client(app)

    url = (api_endpoint / f"simcore-s3/folders/{project_id}").with_query(user_id=user_id)
    async def _fire_and_forget():
        with client.delete(url, ssl=False):
            # NOTE: context will automatically close connection
            pass
    asyncio.ensure_future(_fire_and_forget())
