import logging
from collections.abc import Callable
from math import ceil
from typing import Any, TypeVar, cast

import httpx
from fastapi import FastAPI
from servicelib.fastapi.client_session import get_client_session

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
    session = get_client_session(app)

    try:
        response = await session.request(
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
        raise DatcoreAdapterResponseError(
            status=exc.response.status_code, reason=f"{exc}"
        ) from exc

    except TimeoutError as exc:
        msg = f"datcore-adapter server timed-out: {exc}"
        raise DatcoreAdapterTimeoutError(msg) from exc

    except httpx.RequestError as exc:
        msg = f"unexpected request error: {exc}"
        raise DatcoreAdapterClientError(msg) from exc


_T = TypeVar("_T")


async def retrieve_all_pages(
    app: FastAPI,
    api_key: str,
    api_secret: str,
    method: str,
    path: str,
    return_type_creator: Callable[..., _T],
) -> list[_T]:
    page = 1
    objs = []
    while (
        response := cast(
            dict[str, Any],
            await request(
                app, api_key, api_secret, method, path, params={"page": page}
            ),
        )
    ) and response.get("items"):
        _logger.debug(
            "called %s [%d/%d], received %d objects",
            path,
            page,
            ceil(response.get("total", -1) / response.get("size", 1)),
            len(response.get("items", [])),
        )

        objs += [return_type_creator(d) for d in response.get("items", [])]
        page += 1
    return objs
