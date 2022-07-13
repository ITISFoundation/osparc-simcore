""" Core functionality to interact with the director-v2 service

director-v2 rest API common functionality includes

- common types and constants
- requests helper function to call the API
- thin API client wrapper instance associated to the app's lifespan

"""

import asyncio
import logging
from typing import Any, Optional, Union

import aiohttp
from aiohttp import ClientTimeout, web
from models_library.projects import ProjectID
from models_library.users import UserID
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_random
from yarl import URL

from .director_v2_exceptions import DirectorServiceError
from .director_v2_settings import (
    DirectorV2Settings,
    get_client_session,
    get_plugin_settings,
)

log = logging.getLogger(__name__)

_APP_DIRECTOR_V2_CLIENT_KEY = f"{__name__}.DirectorV2ApiClient"

SERVICE_HEALTH_CHECK_TIMEOUT = ClientTimeout(total=2, connect=1)  # type:ignore

DEFAULT_RETRY_POLICY = dict(
    wait=wait_random(0, 1),
    stop=stop_after_attempt(2),
    reraise=True,
    before_sleep=before_sleep_log(log, logging.WARNING),
)


DataType = dict[str, Any]
DataBody = Union[DataType, list[DataType], None]


async def request_director_v2(
    app: web.Application,
    method: str,
    url: URL,
    expected_status: type[web.HTTPSuccessful] = web.HTTPOk,
    headers: Optional[dict[str, str]] = None,
    data: Optional[Any] = None,
    on_error: Optional[
        dict[int, tuple[type[DirectorServiceError], dict[str, Any]]]
    ] = None,
    **kwargs,
) -> DataBody:
    if not on_error:
        on_error = {}
    try:
        async for attempt in AsyncRetrying(**DEFAULT_RETRY_POLICY):
            with attempt:
                session = get_client_session(app)
                async with session.request(
                    method, url, headers=headers, json=data, **kwargs
                ) as response:
                    payload = (
                        await response.json()
                        if response.content_type == "application/json"
                        else await response.text()
                    )

                    if response.status != expected_status.status_code:
                        if response.status in on_error:
                            exc, exc_ctx = on_error[response.status]
                            raise exc(
                                **exc_ctx, status=response.status, reason=f"{payload}"
                            )
                        raise DirectorServiceError(
                            status=response.status, reason=f"{payload}", url=url
                        )
                    return payload

    # TODO: enrich with https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
    except asyncio.TimeoutError as err:
        raise DirectorServiceError(
            status=web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 timed-out: {err}",
            url=url,
        ) from err

    except aiohttp.ClientError as err:
        raise DirectorServiceError(
            status=web.HTTPServiceUnavailable.status_code,
            reason=f"request to director-v2 service unexpected error {err}",
            url=url,
        ) from err
    log.error("Unexpected result calling %s, %s", f"{url=}", f"{method=}")
    raise DirectorServiceError(
        status=web.HTTPClientError.status_code,
        reason="Unexpected client error",
        url=url,
    )


class DirectorV2ApiClient:
    def __init__(self, app: web.Application) -> None:
        self._app = app
        self._settings: DirectorV2Settings = get_plugin_settings(app)

    async def get(self, project_id: ProjectID, user_id: UserID) -> dict[str, Any]:
        computation_task_out = await request_director_v2(
            self._app,
            "GET",
            (self._settings.base_url / "computations" / f"{project_id}").with_query(
                user_id=int(user_id)
            ),
            expected_status=web.HTTPOk,
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out

    async def start(self, project_id: ProjectID, user_id: UserID, **options) -> str:
        computation_task_out = await request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations",
            expected_status=web.HTTPCreated,
            data={"user_id": user_id, "project_id": project_id, **options},
        )
        assert isinstance(computation_task_out, dict)  # nosec
        return computation_task_out["id"]

    async def stop(self, project_id: ProjectID, user_id: UserID):
        await request_director_v2(
            self._app,
            "POST",
            self._settings.base_url / "computations" / f"{project_id}:stop",
            expected_status=web.HTTPAccepted,
            data={"user_id": user_id},
        )


def get_client(app: web.Application) -> Optional[DirectorV2ApiClient]:
    return app.get(_APP_DIRECTOR_V2_CLIENT_KEY)


def set_client(app: web.Application, obj: DirectorV2ApiClient):
    app[_APP_DIRECTOR_V2_CLIENT_KEY] = obj
