import logging
from collections.abc import Callable
from math import ceil
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi_pagination import LimitOffsetPage
from models_library.api_schemas_storage.storage_schemas import (
    DEFAULT_NUMBER_OF_PATHS_PER_PAGE,
)
from servicelib.fastapi.httpx_client import get_httpx_client

from ...core.settings import get_application_settings
from .datcore_adapter_exceptions import (
    DatcoreAdapterClientError,
    DatcoreAdapterResponseError,
    DatcoreAdapterTimeoutError,
)

_logger = logging.getLogger(__file__)


async def request(
    app: FastAPI,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    *,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    **request_kwargs,
) -> dict[str, Any] | list[dict[str, Any]]:
    datcore_adapter_settings = get_application_settings(app).DATCORE_ADAPTER
    url = datcore_adapter_settings.endpoint + path
    client = get_httpx_client(app)

    try:
        if request_kwargs is None:
            request_kwargs = {}
        response = await client.request(
            method.upper(),
            url,
            headers={
                "x-datcore-api-key": api_key,
                "x-datcore-api-secret": api_secret,
            },
            json=json,
            params=params,
            **request_kwargs,
        )
        response.raise_for_status()
        response_data = response.json()
        assert isinstance(response_data, dict | list)  # nosec
        return response_data

    except httpx.HTTPStatusError as exc:
        raise DatcoreAdapterResponseError(status=exc.response.status_code, reason=f"{exc}") from exc

    except TimeoutError as exc:
        msg = f"datcore-adapter server timed-out: {exc}"
        raise DatcoreAdapterTimeoutError(msg) from exc

    except httpx.RequestError as exc:
        msg = f"unexpected request error: {exc}"
        raise DatcoreAdapterClientError(msg) from exc


async def retrieve_all_pages[T](
    app: FastAPI,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    return_type_creator: Callable[..., T],
) -> list[T]:
    offset = 0
    total: int | None = None
    objs: list[T] = []
    while total is None or offset < total:
        response_page = LimitOffsetPage[dict[str, Any]].model_validate(
            await request(
                app,
                api_key,
                api_secret,
                method,
                path,
                params={"limit": DEFAULT_NUMBER_OF_PATHS_PER_PAGE, "offset": offset},
            )
        )
        assert response_page.limit is not None  # nosec
        assert response_page.offset is not None  # nosec
        _logger.debug(
            "called %s [%d/%d], received %d objects",
            path,
            response_page.offset // response_page.limit + 1,
            ceil(response_page.total / response_page.limit),
            len(response_page.items),
        )

        objs += [return_type_creator(item) for item in response_page.items]
        total = response_page.total
        offset = response_page.offset + response_page.limit
        if not response_page.items:
            break
    return objs
