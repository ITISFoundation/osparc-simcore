import logging

from aiohttp import web
from httpx import AsyncClient
from models_library.licensed_items import LicensedResourceType
from simcore_service_webserver.licenses import (
    _itis_vip_service,
    _licensed_items_service,
)

from ._itis_vip_models import CategoryTuple, ItisVipData, ItisVipResourceData
from ._licensed_items_service import RegistrationState

_logger = logging.getLogger(__name__)


async def sync_resources_with_licensed_items(
    app: web.Application, categories: list[CategoryTuple]
):
    async with AsyncClient() as http_client:
        for category_url, category_id, category_display in categories:
            assert f"{category_url}".endswith(category_id)  # nosec

            # FETCH & VALIDATION
            vip_data_items: list[
                ItisVipData
                # TODO: handle errors to avoid disrupting other categories?
            ] = await _itis_vip_service.get_category_items(http_client, category_url)

            # REGISTRATION
            for vip_data in vip_data_items:

                # TODO: handle error to avoid disrupting other vip_data_items?
                result = await _licensed_items_service.register_resource_as_licensed_item(
                    app,
                    licensed_item_display_name=f"{vip_data.features['name']} {vip_data.features['version']}",
                    # RESOURCE unique identifiers
                    licensed_resource_name=f"{category_id}/{vip_data.id}",
                    licensed_resource_type=LicensedResourceType.VIP_MODEL,
                    # RESOURCE extended data
                    licensed_resource_data=ItisVipResourceData(
                        category_id=category_id,
                        category_display=category_display,
                        data=vip_data,
                    ),
                )

                if result.state == RegistrationState.ALREADY_REGISTERED:
                    # NOTE: not really interesting
                    _logger.debug(result.message)

                elif result.state == RegistrationState.DIFFERENT_RESOURCE:
                    # NOTE: notify since need human decision
                    _logger.warning(result.message)

                else:
                    assert result.state == RegistrationState.NEWLY_REGISTERED  # nosec
                    # NOTE: inform since needs curation
                    _logger.info(
                        "%s . New licensed_item_id=%s pending for activation.",
                        result.message,
                        result.registered.licensed_item_id,
                    )


async def background_periodic_sync_lifecycle(app: web.Application):
    ...
