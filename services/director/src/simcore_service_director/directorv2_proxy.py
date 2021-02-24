import logging
from typing import Optional, Dict, Tuple, Union, Any, List

from aiohttp import web, ClientSession, ClientTimeout, ClientResponse
from pydantic import AnyHttpUrl, BaseSettings, Field, validator, conint, constr
from yarl import URL

log = logging.getLogger(__name__)

# not importing from models_library in order to not change current service dependencies
PortInt = conint(gt=0, lt=65535)
VersionTag = constr(regex=r"^v\d$")


KEY_DIRECTOR_V2_SETTINGS = f"{__name__}.Directorv2Settings"
KEY_CLIENT_SESSION = f"{__name__}.ClientSession"


class Directorv2Settings(BaseSettings):
    enabled: bool = True
    host: str = "director-v2"
    port: PortInt = 8000
    vtag: VersionTag = Field(
        "v2", alias="version", description="Director-v2 service API's version tag"
    )

    endpoint: Optional[AnyHttpUrl] = None

    @validator("endpoint", pre=True)
    @classmethod
    def auto_fill_endpoint(cls, v, values):
        if v is None:
            return AnyHttpUrl.build(
                scheme="http",
                host=values["host"],
                port=f"{values['port']}",
                path=f"/{values['vtag']}",
            )
        return v

    class Config:
        env_prefix = "DIRECTOR_V2_"


def setup_director_v2(app: web.Application) -> None:
    """called during setup phase"""
    app[KEY_DIRECTOR_V2_SETTINGS] = Directorv2Settings()
    app[KEY_CLIENT_SESSION] = ClientSession(timeout=ClientTimeout(10))


def _get_settings(app: web.Application) -> Directorv2Settings:
    return app[KEY_DIRECTOR_V2_SETTINGS]


def _get_client_session(app: web.Application) -> ClientSession:
    return app[KEY_CLIENT_SESSION]


class _DirectorServiceError(Exception):
    """Basic exception for errors raised by director"""

    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason
        super().__init__(f"forwarded call failed with status {status}, reason {reason}")


async def _get_decoded_body(resp: ClientResponse) -> Union[None, str, Dict[str, Any]]:
    return (
        await resp.json()
        if resp.content_type == "application/json"
        else await resp.text()
    )


async def _request_director_v2(
    app: web.Application,
    method: str,
    url: URL,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    **kwargs,
) -> Tuple[Dict, int]:
    session = _get_client_session(app)
    try:
        async with session.request(
            method, url, headers=headers, json=data, **kwargs
        ) as resp:
            if resp.status >= 400:
                # in some cases the director-v2 answers with plain text
                payload: Union[Dict, str] = await _get_decoded_body(resp)
                raise _DirectorServiceError(resp.status, payload)

            payload: Dict = await _get_decoded_body(resp)
            return (payload, resp.status)

    except TimeoutError as err:
        raise web.HTTPServiceUnavailable(
            reason="director-v2 service is currently unavailable"
        ) from err


# pylint: disable=too-many-arguments
async def start_service_sidecar_stack(
    app: web.Application,
    user_id: str,
    project_id: str,
    service_key: str,
    service_tag: str,
    node_uuid: str,
    settings: List[Dict[str, Any]],
    paths_mapping: Dict[str, Any],
    compose_spec: Optional[Dict[str, Any]],
    target_container: Optional[str],
) -> Dict[str, Any]:
    director2_settings: Directorv2Settings = _get_settings(app)

    url = URL(
        f"{director2_settings.endpoint}/dynamic-sidecar/start-service-sidecar-stack"
    )
    data = dict(
        user_id=user_id,
        project_id=project_id,
        service_key=service_key,
        service_tag=service_tag,
        node_uuid=node_uuid,
        settings=settings,
        paths_mapping=paths_mapping,
        compose_spec=compose_spec,
        target_container=target_container,
    )

    log.debug("starting sidecar stack with data=%s", data)

    result, status = await _request_director_v2(app, "POST", url, data=data)
    if status != 200:
        message = f"Received unexpected result result (while starting; node_uuid={node_uuid}) {result}"
        log.warning(message)
        raise _DirectorServiceError(status, message)

    return result


async def stop_service_sidecar_stack(app: web.Application, node_uuid: str):
    director2_settings: Directorv2Settings = _get_settings(app)

    url = URL(
        f"{director2_settings.endpoint}/dynamic-sidecar/stop-service-sidecar-stack"
    )
    data = dict(node_uuid=node_uuid)

    try:
        result, status = await _request_director_v2(app, "POST", url, data=data)
        if status != 204:
            message = f"Received unexpected result result (while stopping; node_uuid={node_uuid}) {result}"
            log.warning(message)
            raise _DirectorServiceError(status, message)

        return result

    except _DirectorServiceError:
        log.error("Could not stop service-sidecar stack for node_uuid=%s", node_uuid)


async def get_service_sidecar_stack_status(app: web.Application, node_uuid: str):
    director2_settings: Directorv2Settings = _get_settings(app)

    url = URL(
        f"{director2_settings.endpoint}/dynamic-sidecar/service-sidecar-stack-status"
    )
    data = dict(node_uuid=node_uuid)

    try:
        result, status = await _request_director_v2(app, "POST", url, data=data)
        if status != 200:
            message = f"Received unexpected result result (while getting state; node_uuid={node_uuid}) {result}"
            log.warning(message)
            raise _DirectorServiceError(status, message)

        return result

    except _DirectorServiceError:
        log.exception(
            "Could not retrive status for service-sidecar stack for node_uuid=%s",
            node_uuid,
        )
        return None


__all__ = ["setup_director_v2", "start_service_sidecar_stack"]