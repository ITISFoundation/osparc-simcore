import logging
from asyncio import CancelledError
from typing import Dict, Optional, Tuple

from aiohttp import ContentTypeError, web
from servicelib.application_setup import ModuleCategory, app_module_setup
from servicelib.logging_utils import log_decorator
from servicelib.rest_responses import wrap_as_envelope
from servicelib.rest_routing import iter_path_operations, map_handlers_with_operations
from yarl import URL

from .director_v2_settings import (
    CONFIG_SECTION_NAME,
    Directorv2Settings,
    create_settings,
    get_client_session,
    get_settings,
)
from .login.decorators import RQT_USERID_KEY, login_required
from .rest_config import APP_OPENAPI_SPECS_KEY
from .security_decorators import permission_required

log = logging.getLogger(__file__)


@log_decorator(logger=log)
async def _request_director_v2(
    app: web.Application,
    method: str,
    url: URL,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
) -> Tuple[Dict, int]:
    session = get_client_session(app)
    try:
        async with session.request(method, url, headers=headers, json=data) as resp:
            if resp.status >= 400:
                raise web.HTTPServerError(reason=await resp.text())
            try:
                payload: Dict = await resp.json()
                return (payload, resp.status)
            except ContentTypeError:
                payload = await resp.text()
                raise web.HTTPServerError(reason=f"malformed data: {payload}")

    except (CancelledError, TimeoutError) as err:
        raise web.HTTPServiceUnavailable(reason="unavailable catalog service") from err


@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
@log_decorator(logger=log)
async def start_pipeline(request: web.Request) -> web.Response:
    director2_settings: Directorv2Settings = get_settings(request.app)

    user_id = request[RQT_USERID_KEY]
    project_id = request.match_info.get("project_id", None)

    backend_url = URL(f"{director2_settings.endpoint}/computations")
    log.debug("Redirecting '%s' -> '%s'", request.url, backend_url)
    body = {"user_id": user_id, "project_id": project_id}

    # request to director-v2
    computation_task_out, resp_status = await _request_director_v2(
        request.app, "POST", backend_url, data=body
    )
    data = {"pipeline_id": computation_task_out["id"]}

    return web.json_response(data=wrap_as_envelope(data=data), status=resp_status)


@login_required
@permission_required("services.pipeline.*")
@permission_required("project.read")
@log_decorator(logger=log)
async def stop_pipeline(request: web.Request) -> web.Response:
    director2_settings: Directorv2Settings = get_settings(request.app)

    user_id = request[RQT_USERID_KEY]
    project_id = request.match_info.get("project_id", None)

    backend_url = URL(f"{director2_settings.endpoint}/computations/{project_id}:stop")
    log.debug("Redirecting '%s' -> '%s'", request.url, backend_url)
    body = {"user_id": user_id}

    # request to director-v2
    _, resp_status = await _request_director_v2(
        request.app, "POST", backend_url, data=body
    )
    data = {}

    return web.json_response(data=wrap_as_envelope(data=data), status=resp_status)


@app_module_setup(
    __name__,
    ModuleCategory.ADDON,
    config_section=CONFIG_SECTION_NAME,
    depends=["simcore_service_webserver.rest"],
    logger=log,
)
def setup_director_v2(app: web.Application):
    # create settings and injects in app
    create_settings(app)

    if not APP_OPENAPI_SPECS_KEY in app:
        log.warning(
            "rest submodule not initialised? computation routes will not be defined!"
        )
        return

    specs = app[APP_OPENAPI_SPECS_KEY]
    # bind routes with handlers
    routes = map_handlers_with_operations(
        {
            "start_pipeline": start_pipeline,
            "stop_pipeline": stop_pipeline,
        },
        filter(lambda o: "computation" in o[1], iter_path_operations(specs)),
        strict=True,
    )
    app.router.add_routes(routes)
