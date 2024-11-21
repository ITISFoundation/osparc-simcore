from contextlib import suppress
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import unquote

import httpx
import jsonref
from pydantic import TypeAdapter, ValidationError
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

assert CapturedParameterSchema  # nosec


_AIOHTTP_PATH: Final[str] = "/dev/doc/swagger.json"
_FASTAPI_PATH: Final[str] = "/api/{}/openapi.json"

ServiceHostNames = Literal[
    "storage",
    "catalog",
    "webserver",
    "director-v2",
]

settings_classes: Final = [
    ("STORAGE", StorageSettings, _AIOHTTP_PATH),
    ("CATALOG", CatalogSettings, _FASTAPI_PATH),
    ("WEBSERVER", WebServerSettings, _AIOHTTP_PATH),
    ("DIRECTOR_V2", DirectorV2Settings, _FASTAPI_PATH),
]


def _get_openapi_specs(url: httpx.URL) -> dict[str, Any]:
    openapi_url = None
    target = (url.host, url.port)

    for prefix, cls, openapi_path in settings_classes:
        with suppress(ValidationError):
            settings = cls.create_from_envs()
            base_url = httpx.URL(settings.base_url)
            if (base_url.host, base_url.port) == target:
                vtag = getattr(settings, f"{prefix}_VTAG")
                openapi_url = settings.base_url + openapi_path.format(vtag)
                break

    if not openapi_url:
        msg = f"{url=} has not been added yet to the testing system. Please do so yourself"
        raise OpenApiSpecError(msg)

    response = httpx.get(openapi_url)
    response.raise_for_status()

    if not response.content:
        msg = f"Cannot retrieve OAS from {openapi_url=}"
        raise RuntimeError(msg)
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
        all_params += TypeAdapter(list[CapturedParameter]).validate_python(params)
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


def enhance_path_description_from_openapi_spec(
    response: httpx.Response,
) -> PathDescription:
    openapi_spec: dict[str, Any] = _get_openapi_specs(response.url)
    return _determine_path(
        openapi_spec, Path(response.request.url.raw_path.decode("utf8").split("?")[0])
    )
