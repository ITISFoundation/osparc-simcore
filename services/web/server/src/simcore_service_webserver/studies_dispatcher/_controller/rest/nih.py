"""Handles requests to the Rest API"""

import logging

from aiohttp import web
from aiohttp.web import Request
from pydantic import (
    ValidationError,
)

from ...._meta import API_VTAG
from ....db.plugin import get_asyncpg_engine
from ....products import products_web
from ....utils_aiohttp import envelope_json_response
from ... import _service
from ..._catalog import iter_latest_product_services
from ...settings import get_plugin_settings
from .nih_schemas import ServiceGet, Viewer

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/services", name="list_latest_services")
async def list_latest_services(request: Request):
    """Returns a list latest version of services"""
    product_name = products_web.get_product_name(request)

    plugin_settings = get_plugin_settings(request.app)
    engine = get_asyncpg_engine(request.app)

    services = []
    async for service_data in iter_latest_product_services(
        plugin_settings, engine, product_name=product_name
    ):
        try:
            service = ServiceGet.create(service_data, request)
            services.append(service)
        except ValidationError as err:
            _logger.debug("Invalid %s: %s", f"{service_data=}", err)

    return envelope_json_response(services)


@routes.get(f"/{API_VTAG}/viewers", name="list_viewers")
async def list_viewers(request: Request):
    # filter: file_type=*
    file_type: str | None = request.query.get("file_type", None)

    viewers = [
        Viewer.create(request, viewer).model_dump()
        for viewer in await _service.list_viewers_info(request.app, file_type=file_type)
    ]
    return envelope_json_response(viewers)


@routes.get(f"/{API_VTAG}/viewers/default", name="list_default_viewers")
async def list_default_viewers(request: Request):
    # filter: file_type=*
    file_type: str | None = request.query.get("file_type", None)

    viewers = [
        Viewer.create(request, viewer).model_dump()
        for viewer in await _service.list_viewers_info(
            request.app, file_type=file_type, only_default=True
        )
    ]
    return envelope_json_response(viewers)
