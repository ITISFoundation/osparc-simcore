import logging

from aiohttp import web
from yarl import URL

from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_utils import extract_and_validate

from ..login.decorators import login_required
from ..security_api import check_permission
from .config import get_client_session, get_config
from .registry import get_registry

ANONYMOUS_USER_ID = -1

log = logging.getLogger(__name__)


def _resolve_url(request: web.Request) -> URL:
    cfg = get_config(request.app)

    # director service API endpoint
    # TODO: service API endpoint could be deduced and checked upon setup (e.g. health check on startup)
    endpoint = URL.build(
        scheme='http',
        host=cfg['host'],
        port=cfg['port']).with_path(cfg["version"])

    # replace raw path, to keep the quotes and
    # strip webserver API version number from basepath
    # >>> URL('http://localhost:8091/v0/services/').raw_parts[2:]
    #    ('services', '')
    tail = "/".join(request.url.raw_parts[2:])

    url = (endpoint / tail)
    return url

# HANDLERS -------------------------------------------------------------------

@login_required
async def services_get(request: web.Request) -> web.Response:
    await check_permission(request, "services.catalog.*")
    await extract_and_validate(request)

    url = _resolve_url(request)
    url = url.with_query(request.query)

    # forward to director API
    session = get_client_session(request.app)
    async with session.get(url, ssl=False) as resp:
        payload = await resp.json()
        return web.json_response(payload, status=resp.status)


@login_required
async def running_interactive_services_post(request: web.Request) -> web.Response:
    """ Starts an interactive service for a given user and
        returns running service's metainfo

        if service already renning, then returns its metainfo
    """
    await check_permission(request, "services.interactive.*")
    params, query, body = await extract_and_validate(request)

    assert not params
    assert query, "POST expected /running_interactive_services? ... "
    assert not body

    userid = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    endpoint = _resolve_url(request)

    session = get_client_session(request.app)

    registry = get_registry(request.app)
    service_uuid = query['service_uuid']

    project_id = query['project_id']

    # get first if already running
    url = (endpoint / service_uuid)
    async with session.get(url, ssl=False) as resp:
        if resp.status == 200:
            # TODO: currently director API does not specify resp. 200
            payload = await resp.json()
        else:
            url = endpoint.with_query(request.query).update_query(
                user_id=userid,
                project_id=project_id,
                # TODO: mountpoint should be setup!!
                service_basepath='/x/' + service_uuid
            )
            # otherwise, start new service
            async with session.post(url, ssl=False) as resp:
                if resp.status < 400:
                    registry.as_started(userid, service_uuid)
                payload = await resp.json()

    return web.json_response(payload, status=resp.status)


@login_required
async def running_interactive_services_get(request: web.Request) -> web.Response:
    await check_permission(request, "services.interactive.*")

    params, query, body = await extract_and_validate(request)

    assert params, "GET expected /running_interactive_services/{service_uuid}"
    assert not query
    assert not body

    url = _resolve_url(request)
    url = url.with_query(request.query)

    # forward to director API
    session = get_client_session(request.app)
    async with session.get(url, ssl=False) as resp:
        payload = await resp.json()
        return web.json_response(payload, status=resp.status)


@login_required
async def running_interactive_services_delete(request: web.Request) -> web.Response:
    """ Stops and removes an interactive service from the

    """
    await check_permission(request, "services.interactive.*")

    params, query, body = await extract_and_validate(request)

    assert params, "DELETE expected /running_interactive_services/{service_uuid}"
    assert not query
    assert not body

    registry = get_registry(request.app)
    service_uuid = params['service_uuid']
    endpoint = _resolve_url(request)

    # forward to director API
    session = get_client_session(request.app)
    # FIXME: composing url might be url = endpoint instead of url = endpoint.with_query()
    # TODO: use instead stop_service from
    url = endpoint
    async with session.delete(url, ssl=False) as resp:
        payload = await resp.json()
        if resp.status < 400 or resp.status == 404:
            registry.as_stopped(service_uuid)
        return web.json_response(payload, status=resp.status)


@login_required
async def running_interactive_services_delete_all(request: web.Request) -> web.Response:
    await check_permission(request, "services.interactive.*")

    params, query, body = await extract_and_validate(request)

    assert not params
    assert not query
    assert not body

    registry = get_registry(request.app)
    userid = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    services = registry.user_to_services_map[userid]

    if services:
        session = get_client_session(request.app)
        endpoint = _resolve_url(request)

        errors = []
        for service_uuid in services:
            url = (endpoint / service_uuid)
            async with session.delete(url, ssl=False) as resp:
                payload = await resp.json()
                if resp.status < 400 or resp.status == 404:
                    registry.as_stopped(service_uuid)
                else:
                    errors.append((payload, resp.status))

        if errors:
            # FIXME: append all errors
            payload, status = errors[0]
            return web.json_response(payload, status=status)

    return web.json_response({'data': ''}, status=204)
