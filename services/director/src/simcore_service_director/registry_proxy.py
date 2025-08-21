import asyncio
import enum
import json
import logging
import re
from collections.abc import AsyncGenerator, Mapping
from typing import Any, Final, cast

import httpx
from aiocache import Cache, SimpleMemoryCache  # type: ignore[import-untyped]
from common_library.async_tools import cancel_wait_task
from common_library.json_serialization import json_loads
from fastapi import FastAPI, status
from servicelib.background_task import create_periodic_task
from servicelib.fastapi.client_session import get_client_session
from servicelib.logging_utils import log_catch, log_context
from servicelib.utils import limited_as_completed
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed, wait_random_exponential
from yarl import URL

from .constants import DIRECTOR_SIMCORE_SERVICES_PREFIX
from .core.errors import (
    DirectorRuntimeError,
    DockerRegistryUnsupportedManifestSchemaVersionError,
    RegistryConnectionError,
    ServiceNotAvailableError,
)
from .core.settings import ApplicationSettings, get_application_settings

DEPENDENCIES_LABEL_KEY: str = "simcore.service.dependencies"

VERSION_REG = re.compile(
    r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"
)

_logger = logging.getLogger(__name__)

#
# NOTE: if you are refactoring this module,
# please consider reusing packages/pytest-simcore/src/pytest_simcore/helpers/docker_registry.py
#


class ServiceType(enum.Enum):
    ALL = ""
    COMPUTATIONAL = "comp"
    DYNAMIC = "dynamic"


async def _basic_auth_registry_request(
    app: FastAPI, path: str, method: str, **session_kwargs
) -> tuple[dict, Mapping]:
    app_settings = get_application_settings(app)
    # try the registry with basic authentication first, spare 1 call
    resp_data: dict = {}
    resp_headers: Mapping = {}
    auth = (
        httpx.BasicAuth(
            username=app_settings.DIRECTOR_REGISTRY.REGISTRY_USER,
            password=app_settings.DIRECTOR_REGISTRY.REGISTRY_PW.get_secret_value(),
        )
        if app_settings.DIRECTOR_REGISTRY.REGISTRY_AUTH
        else None
    )

    request_url = URL(f"{app_settings.DIRECTOR_REGISTRY.api_url}").joinpath(
        path, encoded=True
    )

    session = get_client_session(app)
    response = await session.request(
        method.lower(),
        f"{request_url}",
        auth=auth,
        **session_kwargs,
    )

    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        # basic mode failed, test with other auth mode
        resp_data, resp_headers = await _auth_registry_request(
            app_settings,
            request_url,
            method,
            response.headers,
            session,
            **session_kwargs,
        )

    elif response.status_code == status.HTTP_404_NOT_FOUND:
        raise ServiceNotAvailableError(service_name=path)

    elif response.status_code >= status.HTTP_400_BAD_REQUEST:
        raise RegistryConnectionError(
            msg=f"{response}: {response.text} for {request_url}"
        )

    else:
        # registry that does not need an auth
        if method.lower() != "head":
            resp_data = response.json()
        resp_headers = response.headers

    return (resp_data, resp_headers)


async def _auth_registry_request(  # noqa: C901
    app_settings: ApplicationSettings,
    url: URL,
    method: str,
    auth_headers: Mapping,
    session: httpx.AsyncClient,
    **kwargs,
) -> tuple[dict, Mapping]:
    # auth issue let's try some authentication get the auth type
    auth_type = None
    auth_details: dict[str, str] = {}
    for key in auth_headers:
        if str(key).lower() == "www-authenticate":
            auth_type, auth_value = str(auth_headers[key]).split(" ", 1)
            auth_details = {
                x.split("=")[0]: x.split("=")[1].strip('"')
                for x in auth_value.split(",")
            }
            break
    if not auth_type:
        msg = "Unknown registry type: cannot deduce authentication method!"
        raise RegistryConnectionError(msg=msg)
    auth = httpx.BasicAuth(
        username=app_settings.DIRECTOR_REGISTRY.REGISTRY_USER,
        password=app_settings.DIRECTOR_REGISTRY.REGISTRY_PW.get_secret_value(),
    )

    # bearer type, it needs a token with all communications
    if auth_type == "Bearer":
        # get the token
        token_url = URL(auth_details["realm"]).with_query(
            service=auth_details["service"], scope=auth_details["scope"]
        )
        token_resp = await session.get(f"{token_url}", auth=auth, **kwargs)
        if token_resp.status_code != status.HTTP_200_OK:
            msg = f"Unknown error while authentifying with registry: {token_resp!s}"
            raise RegistryConnectionError(msg=msg)

        bearer_code = (await token_resp.json())["token"]
        headers = {"Authorization": f"Bearer {bearer_code}"}
        resp_wtoken = await getattr(session, method.lower())(
            url, headers=headers, **kwargs
        )
        assert isinstance(resp_wtoken, httpx.Response)  # nosec
        if resp_wtoken.status_code == status.HTTP_404_NOT_FOUND:
            raise ServiceNotAvailableError(service_name=f"{url}")
        if resp_wtoken.status_code >= status.HTTP_400_BAD_REQUEST:
            raise RegistryConnectionError(msg=f"{resp_wtoken}")
        resp_data = await resp_wtoken.json(content_type=None)
        resp_headers = resp_wtoken.headers
        return (resp_data, resp_headers)
    if auth_type == "Basic":
        # basic authentication should not be since we tried already...
        resp_wbasic = await getattr(session, method.lower())(
            str(url), auth=auth, **kwargs
        )
        assert isinstance(resp_wbasic, httpx.Response)  # nosec
        if resp_wbasic.status_code == status.HTTP_404_NOT_FOUND:
            raise ServiceNotAvailableError(service_name=f"{url}")
        if resp_wbasic.status_code >= status.HTTP_400_BAD_REQUEST:
            raise RegistryConnectionError(
                msg=f"{resp_wbasic}: {resp_wbasic.text} for {url}"
            )
        resp_data = await resp_wbasic.json(content_type=None)
        resp_headers = resp_wbasic.headers
        return (resp_data, resp_headers)
    msg = f"Unknown registry authentification type: {url}"
    raise RegistryConnectionError(msg=msg)


@retry(
    retry=retry_if_exception_type((httpx.RequestError, TimeoutError)),
    wait=wait_random_exponential(min=1, max=10),
    stop=stop_after_delay(120),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
    reraise=True,
)
async def _retried_request(
    app: FastAPI, path: str, method: str, **session_kwargs
) -> tuple[dict, Mapping]:
    return await _basic_auth_registry_request(app, path, method, **session_kwargs)


async def registry_request(
    app: FastAPI,
    *,
    path: str,
    method: str,
    use_cache: bool,
    **session_kwargs,
) -> tuple[dict, Mapping]:
    cache: SimpleMemoryCache = app.state.registry_cache_memory
    cache_key = f"{method}_{path}"
    if use_cache and (cached_response := await cache.get(cache_key)):
        assert isinstance(cached_response, tuple)  # nosec
        return cast(tuple[dict, Mapping], cached_response)
    # Add proper Accept headers for manifest requests for accepting both v1 and v2
    if "manifests/" in path and method.upper() == "GET":
        headers = session_kwargs.get("headers", {})
        headers.update(
            {
                "Accept": ", ".join(
                    [
                        "application/vnd.docker.distribution.manifest.v2+json",
                        "application/vnd.docker.distribution.manifest.list.v2+json",
                        "application/vnd.docker.distribution.manifest.v1+prettyjws",
                        "application/json",
                    ]
                )
            }
        )
        session_kwargs["headers"] = headers
    app_settings = get_application_settings(app)
    try:
        response, response_headers = await _retried_request(
            app, path, method.upper(), **session_kwargs
        )
    except httpx.RequestError as exc:
        msg = f"Unknown error while accessing registry: {exc!s} via {exc.request}"
        raise DirectorRuntimeError(msg=msg) from exc

    if app_settings.DIRECTOR_REGISTRY_CACHING and method.upper() == "GET":
        await cache.set(
            cache_key,
            (response, response_headers),
            ttl=app_settings.DIRECTOR_REGISTRY_CACHING_TTL.total_seconds(),
        )

    return response, response_headers


async def _setup_registry(app: FastAPI) -> None:
    @retry(
        wait=wait_fixed(1),
        before_sleep=before_sleep_log(_logger, logging.WARNING),
        retry=retry_if_exception_type((httpx.RequestError, DirectorRuntimeError)),
        reraise=True,
    )
    async def _wait_until_registry_responsive(app: FastAPI) -> None:
        await _basic_auth_registry_request(app, path="", method="HEAD", timeout=1.0)

    with log_context(_logger, logging.INFO, msg="Connecting to docker registry"):
        await _wait_until_registry_responsive(app)


async def _list_all_services_task(*, app: FastAPI) -> None:
    with log_context(_logger, logging.INFO, msg="Updating cache with services"):
        await list_services(app, ServiceType.ALL, update_cache=True)


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        cache = Cache(Cache.MEMORY)
        assert isinstance(cache, SimpleMemoryCache)  # nosec
        app.state.registry_cache_memory = cache
        await _setup_registry(app)
        app_settings = get_application_settings(app)
        app.state.auto_cache_task = None
        if app_settings.DIRECTOR_REGISTRY_CACHING:
            app.state.auto_cache_task = create_periodic_task(
                _list_all_services_task,
                interval=app_settings.DIRECTOR_REGISTRY_CACHING_TTL / 2,
                task_name="director-auto-cache-task",
                app=app,
            )

    async def on_shutdown() -> None:
        if app.state.auto_cache_task:
            await cancel_wait_task(app.state.auto_cache_task)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def _get_prefix(service_type: ServiceType) -> str:
    return f"{DIRECTOR_SIMCORE_SERVICES_PREFIX}/{service_type.value}/"


_SERVICE_TYPE_FILTER_MAP: Final[dict[ServiceType, tuple[str, ...]]] = {
    ServiceType.DYNAMIC: (_get_prefix(ServiceType.DYNAMIC),),
    ServiceType.COMPUTATIONAL: (_get_prefix(ServiceType.COMPUTATIONAL),),
    ServiceType.ALL: (
        _get_prefix(ServiceType.DYNAMIC),
        _get_prefix(ServiceType.COMPUTATIONAL),
    ),
}


async def _list_repositories_gen(
    app: FastAPI, service_type: ServiceType, *, update_cache: bool
) -> AsyncGenerator[list[str], None]:
    with log_context(_logger, logging.DEBUG, msg="listing repositories"):
        path = f"_catalog?n={get_application_settings(app).DIRECTOR_REGISTRY_CLIENT_MAX_NUMBER_OF_RETRIEVED_OBJECTS}"
        result, headers = await registry_request(
            app, path=path, method="GET", use_cache=not update_cache
        )  # initial call

        while True:
            if "Link" in headers:
                next_path = (
                    str(headers["Link"]).split(";")[0].strip("<>").removeprefix("/v2/")
                )
                prefetch_task = asyncio.create_task(
                    registry_request(
                        app, path=next_path, method="GET", use_cache=not update_cache
                    )
                )
            else:
                prefetch_task = None

            yield list(
                filter(
                    lambda x: str(x).startswith(_SERVICE_TYPE_FILTER_MAP[service_type]),
                    result["repositories"],
                )
            )
            if prefetch_task:
                result, headers = await prefetch_task
            else:
                return


async def list_image_tags_gen(
    app: FastAPI, image_key: str, *, update_cache=False
) -> AsyncGenerator[list[str], None]:
    with log_context(_logger, logging.DEBUG, msg=f"listing image tags in {image_key}"):
        path = f"{image_key}/tags/list?n={get_application_settings(app).DIRECTOR_REGISTRY_CLIENT_MAX_NUMBER_OF_RETRIEVED_OBJECTS}"
        tags, headers = await registry_request(
            app, path=path, method="GET", use_cache=not update_cache
        )  # initial call
        assert "tags" in tags  # nosec
        while True:
            if "Link" in headers:
                next_path = (
                    str(headers["Link"]).split(";")[0].strip("<>").removeprefix("/v2/")
                )
                prefetch_task = asyncio.create_task(
                    registry_request(
                        app, path=next_path, method="GET", use_cache=not update_cache
                    )
                )
            else:
                prefetch_task = None

            yield (
                list(
                    filter(
                        VERSION_REG.match,
                        tags["tags"],
                    )
                )
                if tags["tags"] is not None
                else []
            )
            if prefetch_task:
                tags, headers = await prefetch_task
            else:
                return


async def list_image_tags(app: FastAPI, image_key: str) -> list[str]:
    image_tags = []
    async for tags in list_image_tags_gen(app, image_key):
        image_tags.extend(tags)
    return image_tags


_DOCKER_CONTENT_DIGEST_HEADER = "Docker-Content-Digest"


async def get_image_digest(app: FastAPI, image: str, tag: str) -> str | None:
    """Returns image manifest digest number or None if fails to obtain it

    The manifest digest is essentially a SHA256 hash of the image manifest

    SEE https://distribution.github.io/distribution/spec/api/#digest-header
    """
    path = f"{image}/manifests/{tag}"
    _, headers = await registry_request(app, path=path, method="GET", use_cache=True)

    headers = headers or {}
    return headers.get(_DOCKER_CONTENT_DIGEST_HEADER, None)


async def get_image_labels(
    app: FastAPI, image: str, tag: str, *, update_cache=False
) -> tuple[dict[str, str], str | None]:
    """Returns image labels and the image manifest digest"""
    with log_context(_logger, logging.DEBUG, msg=f"get {image}:{tag} labels"):
        request_result, headers = await registry_request(
            app,
            path=f"{image}/manifests/{tag}",
            method="GET",
            use_cache=not update_cache,
        )

        schema_version = request_result["schemaVersion"]
        labels: dict[str, str] = {}
        match schema_version:
            case 2:
                # Image Manifest Version 2, Schema 2 -> defaults in registries v3 (https://distribution.github.io/distribution/spec/manifest-v2-2/)
                media_type = request_result["mediaType"]
                if (
                    media_type
                    == "application/vnd.docker.distribution.manifest.list.v2+json"
                ):
                    # default to x86_64 architecture
                    _logger.info(
                        "Image %s:%s is a docker image with multiple architectures. "
                        "Currently defaulting to x86_64 architecture",
                        image,
                        tag,
                    )
                    manifests = request_result.get("manifests", [])
                    if not manifests:
                        raise DockerRegistryUnsupportedManifestSchemaVersionError(
                            version=schema_version,
                            service_name=image,
                            service_tag=tag,
                            reason="Manifest list is empty",
                        )
                    first_manifest_digest = manifests[0]["digest"]
                    request_result, _ = await registry_request(
                        app,
                        path=f"{image}/manifests/{first_manifest_digest}",
                        method="GET",
                        use_cache=not update_cache,
                    )

                config_digest = request_result["config"]["digest"]
                # Fetch the config blob
                config_result, _ = await registry_request(
                    app,
                    path=f"{image}/blobs/{config_digest}",
                    method="GET",
                    use_cache=not update_cache,
                )
                labels = config_result.get("config", {}).get("Labels", {})
            case 1:
                # Image Manifest Version 2, Schema 1 deprecated in docker hub since 2024-11-04
                v1_compatibility_key = json_loads(
                    request_result["history"][0]["v1Compatibility"]
                )
                container_config: dict[str, Any] = v1_compatibility_key.get(
                    "container_config", v1_compatibility_key.get("config", {})
                )
                labels = container_config.get("Labels", {})
            case _:
                raise DockerRegistryUnsupportedManifestSchemaVersionError(
                    version=schema_version, service_name=image, service_tag=tag
                )

        headers = headers or {}
        manifest_digest: str | None = headers.get(_DOCKER_CONTENT_DIGEST_HEADER, None)

    return (labels, manifest_digest)


async def get_image_details(
    app: FastAPI, image_key: str, image_tag: str, *, update_cache=False
) -> dict[str, Any]:
    image_details: dict = {}
    labels, image_manifest_digest = await get_image_labels(
        app, image_key, image_tag, update_cache=update_cache
    )

    if image_manifest_digest:
        # Adds manifest as extra key in the response similar to org.opencontainers.image.base.digest
        # SEE https://github.com/opencontainers/image-spec/blob/main/annotations.md#pre-defined-annotation-keys
        image_details.update({"image_digest": image_manifest_digest})

    if not labels:
        return image_details
    for key in labels:
        if not key.startswith("io.simcore."):
            continue
        try:
            label_data = json_loads(labels[key])
            for label_key in label_data:
                image_details[label_key] = label_data[label_key]
        except json.decoder.JSONDecodeError:
            logging.exception(
                "Error while decoding json formatted data from %s:%s",
                image_key,
                image_tag,
            )
            # silently skip this repo
            return {}

    return image_details


async def get_repo_details(
    app: FastAPI, image_key: str, *, update_cache=False
) -> list[dict[str, Any]]:
    repo_details = []
    async for image_tags in list_image_tags_gen(
        app, image_key, update_cache=update_cache
    ):
        async for image_details_future in limited_as_completed(
            (
                get_image_details(app, image_key, tag, update_cache=update_cache)
                for tag in image_tags
            ),
            limit=get_application_settings(
                app
            ).DIRECTOR_REGISTRY_CLIENT_MAX_CONCURRENT_CALLS,
        ):
            with log_catch(_logger, reraise=False):
                if image_details := await image_details_future:
                    repo_details.append(image_details)
    return repo_details


async def list_services(
    app: FastAPI, service_type: ServiceType, *, update_cache=False
) -> list[dict]:
    with log_context(_logger, logging.DEBUG, msg="listing services"):
        services = []
        concurrency_limit = get_application_settings(
            app
        ).DIRECTOR_REGISTRY_CLIENT_MAX_CONCURRENT_CALLS
        async for repos in _list_repositories_gen(
            app, service_type, update_cache=update_cache
        ):
            # only list as service if it actually contains the necessary labels
            async for repo_details_future in limited_as_completed(
                (
                    get_repo_details(app, repo, update_cache=update_cache)
                    for repo in repos
                ),
                limit=concurrency_limit,
            ):
                with log_catch(_logger, reraise=False):
                    if repo_details := await repo_details_future:
                        services.extend(repo_details)

        return services


async def list_interactive_service_dependencies(
    app: FastAPI, service_key: str, service_tag: str
) -> list[dict]:
    image_labels, _ = await get_image_labels(app, service_key, service_tag)
    dependency_keys = []
    if DEPENDENCIES_LABEL_KEY in image_labels:
        try:
            dependencies = json_loads(image_labels[DEPENDENCIES_LABEL_KEY])
            dependency_keys = [
                {"key": dependency["key"], "tag": dependency["tag"]}
                for dependency in dependencies
            ]

        except json.decoder.JSONDecodeError:
            logging.exception(
                "Incorrect json formatting in %s, skipping...",
                image_labels[DEPENDENCIES_LABEL_KEY],
            )

    return dependency_keys


def get_service_first_name(image_key: str) -> str:
    if str(image_key).startswith(_get_prefix(ServiceType.DYNAMIC)):
        service_name_suffixes = str(image_key)[len(_get_prefix(ServiceType.DYNAMIC)) :]
    elif str(image_key).startswith(_get_prefix(ServiceType.COMPUTATIONAL)):
        service_name_suffixes = str(image_key)[
            len(_get_prefix(ServiceType.COMPUTATIONAL)) :
        ]
    else:
        return "invalid service"

    _logger.debug(
        "retrieved service name from repo %s : %s", image_key, service_name_suffixes
    )
    return service_name_suffixes.split("/")[0]


def get_service_last_names(image_key: str) -> str:
    if str(image_key).startswith(_get_prefix(ServiceType.DYNAMIC)):
        service_name_suffixes = str(image_key)[len(_get_prefix(ServiceType.DYNAMIC)) :]
    elif str(image_key).startswith(_get_prefix(ServiceType.COMPUTATIONAL)):
        service_name_suffixes = str(image_key)[
            len(_get_prefix(ServiceType.COMPUTATIONAL)) :
        ]
    else:
        return "invalid service"
    service_last_name = str(service_name_suffixes).replace("/", "_")
    _logger.debug(
        "retrieved service last name from repo %s : %s", image_key, service_last_name
    )
    return service_last_name
