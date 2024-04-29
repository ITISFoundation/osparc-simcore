from pathlib import Path
from typing import Any, Literal, get_args
from urllib.parse import unquote

import httpx
import jsonref
from pydantic import parse_obj_as
from settings_library.catalog import CatalogSettings
from settings_library.director_v2 import DirectorV2Settings
from settings_library.storage import StorageSettings
from settings_library.webserver import WebServerSettings

from .httpx_calls_capture_errors import (
    OpenApiSpecError,
    PathNotInOpenApiSpecError,
    VerbNotInPathError,
)
from .httpx_calls_capture_parameters import (
    CapturedParameter,
    CapturedParameterSchema,
    PathDescription,
)

service_hosts = Literal["storage", "catalog", "webserver", "director-v2"]

assert CapturedParameterSchema  # nosec


def _get_openapi_specs(host: service_hosts) -> dict[str, Any]:
    url: str
    if host == "storage":
        settings = StorageSettings.create_from_envs()
        url = settings.base_url + "/dev/doc/swagger.json"
    elif host == "catalog":
        settings = CatalogSettings.create_from_envs()
        url = settings.base_url + "/api/v0/openapi.json"
    elif host == "webserver":
        settings = WebServerSettings.create_from_envs()
        url = settings.base_url + "/dev/doc/swagger.json"
    elif host == "director-v2":
        settings = DirectorV2Settings.create_from_envs()
        url = settings.base_url + "/api/v2/openapi.json"
    else:
        msg = f"{host=} has not been added yet to the testing system. Please do so yourself"
        raise OpenApiSpecError(msg)
    with httpx.Client() as session:
        response = session.get(url)
        response.raise_for_status()
        openapi_spec = jsonref.loads(response.read().decode("utf8"))
        assert isinstance(openapi_spec, dict)
        return openapi_spec


def _get_params(
    openapi_spec: dict[str, Any], path: str, method: str | None = None
) -> set[CapturedParameter]:
    """Returns all parameters for the method associated with a given resource (and optionally also a given method)"""
    endpoints: dict[str, Any] | None
    if (endpoints := openapi_spec["paths"].get(path)) is None:
        msg = f"{path} was not in the openapi specification"
        raise PathNotInOpenApiSpecError(msg)
    all_params: list[CapturedParameter] = []
    for verb in [method] if method is not None else list(endpoints):
        if (verb_spec := endpoints.get(verb)) is None:
            msg = f"the verb '{verb}' was not available in '{path}' in {openapi_spec}"
            raise VerbNotInPathError(msg)
        if (params := verb_spec.get("parameters")) is None:
            continue
        all_params += parse_obj_as(list[CapturedParameter], params)
    return set(all_params)


def _determine_path(
    openapi_spec: dict[str, Any], response_path: Path
) -> PathDescription:
    def parts(p: str) -> tuple[str, ...]:
        all_parts: list[str] = sum((elm.split("/") for elm in p.split(":")), start=[])
        return tuple(part for part in all_parts if len(part) > 0)

    for p in openapi_spec["paths"]:
        openapi_parts: tuple[str, ...] = tuple(parts(p))
        response_parts: tuple[str, ...] = tuple(parts(f"{response_path}"))
        if len(openapi_parts) != len(response_parts):
            continue
        path_params = {
            param.name: param for param in _get_params(openapi_spec, p) if param.is_path
        }
        if (len(path_params) == 0) and (openapi_parts == response_parts):
            return PathDescription(
                path=str(response_path), path_parameters=list(path_params.values())
            )
        path_param_indices: tuple[int, ...] = tuple(
            openapi_parts.index("{" + name + "}") for name in path_params
        )
        if tuple(
            elm for ii, elm in enumerate(openapi_parts) if ii not in path_param_indices
        ) != tuple(
            elm for ii, elm in enumerate(response_parts) if ii not in path_param_indices
        ):
            continue
        path_param_indices_iter = iter(path_param_indices)
        for key in path_params:
            ii = next(path_param_indices_iter)
            path_params[key].response_value = unquote(response_path.parts[ii])
        return PathDescription(
            path=p,
            path_parameters=list(path_params.values()),
        )
    msg = f"Could not find a path matching {response_path} in "
    raise PathNotInOpenApiSpecError(msg)


def enhance_from_openapi_spec(response: httpx.Response) -> PathDescription:
    assert response.url.host in get_args(
        service_hosts
    ), f"{response.url.host} is not in {service_hosts} - please add it yourself"
    openapi_spec: dict[str, Any] = _get_openapi_specs(response.url.host)
    return _determine_path(
        openapi_spec, Path(response.request.url.raw_path.decode("utf8").split("?")[0])
    )
