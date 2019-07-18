
from .storage_config import get_client_session, get_config
from aiohttp import web
from yarl import URL
import logging


log = logging.getLogger(__name__)



def _get_storage_client(app: web.Application):
    cfg = get_config(app)

    # storage service API endpoint
    endpoint = URL.build(scheme='http',
                         host=cfg['host'],
                         port=cfg['port']).with_path(cfg["version"])

    client = get_client_session(app)
    return client, endpoint

from servicelib.rest_resources import unwrap_envelope


async def copy_data_from_project(app, source_project, destination_project, nodes_map):
    client, endpoint = _get_storage_client(app)

    url = endpoint / "simcore-s3/folders"
    async with client.post( url , json={
        'source':source_project,
        'destination': destination_project,
        'nodes_map': nodes_map
    }) as resp:
        payload = await resp.json()
        data, error = unwrap_envelope(payload)
        if error:
            log.error(error)

    return data
