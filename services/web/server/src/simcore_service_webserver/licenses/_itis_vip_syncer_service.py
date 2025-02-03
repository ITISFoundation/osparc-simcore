import asyncio
import logging
from datetime import timedelta

from aiohttp import web
from httpx import AsyncClient
from models_library.licensed_items import LicensedResourceType
from pydantic import ValidationError
from servicelib.async_utils import cancel_wait_task
from servicelib.background_task_utils import exclusive_periodic
from servicelib.logging_utils import log_catch, log_context
from simcore_service_webserver.licenses import (
    _itis_vip_service,
    _licensed_items_service,
)
from simcore_service_webserver.licenses._itis_vip_settings import ItisVipSettings

from ..redis import get_redis_lock_manager_client_sdk, setup_redis
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
            with log_context(
                _logger, logging.INFO, "Fetching %s and validating", category_url
            ), log_catch(_logger, reraise=True):
                vip_data_items: list[
                    ItisVipData
                    # TODO: handle errors to avoid disrupting other categories?
                ] = await _itis_vip_service.get_category_items(
                    http_client, category_url
                )

            # REGISTRATION
            for vip_data in vip_data_items:

                licensed_resource_name = f"{category_id}/{vip_data.id}"

                with log_context(
                    _logger, logging.INFO, "Registering %s", licensed_resource_name
                ), log_catch(_logger, reraise=False):
                    # TODO: handle error to avoid disrupting other vip_data_items?
                    result = await _licensed_items_service.register_resource_as_licensed_item(
                        app,
                        licensed_item_display_name=f"{vip_data.features.get('name', 'UNNAMED!!')} "
                        f"{vip_data.features.get('version', 'UNVERSIONED!!')}",
                        # RESOURCE unique identifiers
                        licensed_resource_name=licensed_resource_name,
                        licensed_resource_type=LicensedResourceType.VIP_MODEL,
                        # RESOURCE extended data
                        licensed_resource_data=ItisVipResourceData(
                            category_id=category_id,
                            category_display=category_display,
                            source=vip_data,
                        ),
                    )

                    if result.state == RegistrationState.ALREADY_REGISTERED:
                        # NOTE: not really interesting
                        _logger.debug(result.message)

                    elif result.state == RegistrationState.DIFFERENT_RESOURCE:
                        # NOTE: notify since need human decision
                        _logger.warning(result.message)

                    else:
                        assert (
                            result.state == RegistrationState.NEWLY_REGISTERED
                        )  # nosec
                        # NOTE: inform since needs curation
                        _logger.info(
                            "%s . New licensed_item_id=%s pending for activation.",
                            result.message,
                            result.registered.licensed_item_id,
                        )


_BACKGROUND_TASK_NAME = f"{__name__}.itis_vip_syncer_cleanup_ctx._periodic_sync"


def setup_itis_vip_syncer(app: web.Application):
    categories = []

    try:
        settings = ItisVipSettings.create_from_envs()
        categories = settings.to_categories()

    except ValidationError as err:
        _logger.warning("IT'IS VIP syncer disabled. Skipping. %s", err)
        return

    async def _cleanup_ctx(app: web.Application):
        with (
            log_context(
                _logger, logging.INFO, f"IT'IS VIP syncing {len(categories)} categories"
            ),
            log_catch(_logger, reraise=False),
        ):

            @exclusive_periodic(
                get_redis_lock_manager_client_sdk(app),
                task_interval=timedelta(minutes=1),
                retry_after=timedelta(minutes=2),
            )
            async def _periodic_sync() -> None:
                await sync_resources_with_licensed_items(app, categories=categories)

            background_task = asyncio.create_task(
                _periodic_sync(), name=_BACKGROUND_TASK_NAME
            )

            yield

            await cancel_wait_task(background_task)

    if categories:
        setup_redis(app)
        app.cleanup_ctx.append(_cleanup_ctx)
