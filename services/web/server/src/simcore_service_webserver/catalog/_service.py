import logging
from collections.abc import Iterator
from typing import Any, cast

from aiohttp import web
from models_library.api_schemas_catalog.services import MyServiceGet, ServiceUpdateV2
from models_library.api_schemas_webserver.catalog import (
    ServiceInputGet,
    ServiceInputKey,
    ServiceOutputGet,
    ServiceOutputKey,
)
from models_library.products import ProductName
from models_library.rest_pagination import (
    PageLimitInt,
    PageMetaInfoLimitOffset,
    PageOffsetInt,
)
from models_library.services import (
    ServiceInput,
    ServiceKey,
    ServiceOutput,
    ServiceVersion,
)
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pint import UnitRegistry
from servicelib.rabbitmq._errors import RPCServerError
from servicelib.rabbitmq.rpc_interfaces.catalog import services as catalog_rpc
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import CatalogNotAvailableError
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from ..rabbitmq import get_rabbitmq_rpc_client
from . import _catalog_rest_client_service
from ._controller_rest_schemas import (
    CatalogRequestContext,
    ServiceInputGetFactory,
    ServiceOutputGetFactory,
)
from ._units_service import can_connect, replace_service_input_outputs

_logger = logging.getLogger(__name__)


async def _safe_replace_service_input_outputs(
    service: dict[str, Any], unit_registry: UnitRegistry
):
    try:
        await replace_service_input_outputs(
            service,
            unit_registry=unit_registry,
            **RESPONSE_MODEL_POLICY,
        )
    except KeyError:  # noqa: PERF203
        # This will limit the effect of a any error in the formatting of
        # service metadata (mostly in label annotations). Otherwise it would
        # completely break all the listing operation. At this moment,
        # a limitation on schema's $ref produced an error that made faiing
        # the full service listing.
        _logger.exception(
            "Failed while processing this %s. "
            "Skipping service from listing. "
            "TIP: check formatting of docker label annotations for inputs/outputs.",
            f"{service=}",
        )


async def list_latest_services(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    unit_registry: UnitRegistry,
    limit: PageLimitInt,
    offset: PageOffsetInt,
) -> tuple[list, PageMetaInfoLimitOffset]:
    # NOTE: will replace list_services

    page = await catalog_rpc.list_services_paginated(
        get_rabbitmq_rpc_client(app),
        product_name=product_name,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    page_data = jsonable_encoder(page.data, exclude_unset=True)
    for data in page_data:
        await _safe_replace_service_input_outputs(data, unit_registry)

    return page_data, page.meta


async def batch_get_my_services(
    app: web.Application,
    *,
    user_id: UserID,
    product_name: ProductName,
    services_ids: list[tuple[ServiceKey, ServiceVersion]],
) -> list[MyServiceGet]:
    try:

        return await catalog_rpc.batch_get_my_services(
            get_rabbitmq_rpc_client(app),
            user_id=user_id,
            product_name=product_name,
            ids=services_ids,
        )

    except RPCServerError as err:
        raise CatalogNotAvailableError(
            user_id=user_id,
            product_name=product_name,
            services_ids=services_ids,
        ) from err


async def get_service_v2(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    unit_registry: UnitRegistry,
):
    # NOTE: will replace get_service
    service = await catalog_rpc.get_service(
        get_rabbitmq_rpc_client(app),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )

    data = jsonable_encoder(service, exclude_unset=True)
    await replace_service_input_outputs(
        data,
        unit_registry=unit_registry,
        **RESPONSE_MODEL_POLICY,
    )
    return data


async def update_service_v2(
    app: web.Application,
    *,
    product_name: ProductName,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    update_data: dict[str, Any],
    unit_registry: UnitRegistry,
):
    # NOTE: will replace update_service
    service = await catalog_rpc.update_service(
        get_rabbitmq_rpc_client(app),
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update=ServiceUpdateV2.model_validate(update_data),
    )

    data = jsonable_encoder(service, exclude_unset=True)
    await replace_service_input_outputs(
        data,
        unit_registry=unit_registry,
        **RESPONSE_MODEL_POLICY,
    )
    return data


async def list_service_inputs(
    service_key: ServiceKey, service_version: ServiceVersion, ctx: CatalogRequestContext
) -> list[ServiceInputGet]:
    service = await _catalog_rest_client_service.get_service(
        ctx.app,
        user_id=ctx.user_id,
        service_key=service_key,
        service_version=service_version,
        product_name=ctx.product_name,
    )
    return [
        await ServiceInputGetFactory.from_catalog_service_api_model(
            service=service, input_key=input_key
        )
        for input_key in service["inputs"]
    ]


async def get_service_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    input_key: ServiceInputKey,
    ctx: CatalogRequestContext,
) -> ServiceInputGet:
    service = await _catalog_rest_client_service.get_service(
        ctx.app,
        user_id=ctx.user_id,
        service_key=service_key,
        service_version=service_version,
        product_name=ctx.product_name,
    )
    service_input: ServiceInputGet = (
        await ServiceInputGetFactory.from_catalog_service_api_model(
            service=service, input_key=input_key
        )
    )

    return service_input


async def get_compatible_inputs_given_source_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    from_service_key: ServiceKey,
    from_service_version: ServiceVersion,
    from_output_key: ServiceOutputKey,
    ctx: CatalogRequestContext,
) -> list[ServiceInputKey]:
    """
        Filters inputs of this service that match a given service output

    Returns keys of compatible input ports of the service, provided an output port of
    a connected node.
    """

    # 1 output
    service_output = await get_service_output(
        from_service_key, from_service_version, from_output_key, ctx
    )

    from_output: ServiceOutput = ServiceOutput.model_construct(
        **service_output.model_dump(include=ServiceOutput.model_fields.keys())  # type: ignore[arg-type]
    )

    # N inputs
    service_inputs = await list_service_inputs(service_key, service_version, ctx)

    def iter_service_inputs() -> Iterator[tuple[ServiceInputKey, ServiceInput]]:
        for service_input in service_inputs:
            yield service_input.key_id, ServiceInput.model_construct(
                **service_input.model_dump(include=ServiceInput.model_fields.keys())  # type: ignore[arg-type]
            )

    # check
    matches = []
    for key_id, to_input in iter_service_inputs():
        if can_connect(from_output, to_input, units_registry=ctx.unit_registry):
            matches.append(key_id)

    return matches


async def list_service_outputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    ctx: CatalogRequestContext,
) -> list[ServiceOutputGet]:
    service = await _catalog_rest_client_service.get_service(
        ctx.app,
        user_id=ctx.user_id,
        service_key=service_key,
        service_version=service_version,
        product_name=ctx.product_name,
    )
    return [
        await ServiceOutputGetFactory.from_catalog_service_api_model(
            service=service, output_key=output_key, ureg=None
        )
        for output_key in service["outputs"]
    ]


async def get_service_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    output_key: ServiceOutputKey,
    ctx: CatalogRequestContext,
) -> ServiceOutputGet:
    service = await _catalog_rest_client_service.get_service(
        ctx.app,
        user_id=ctx.user_id,
        service_key=service_key,
        service_version=service_version,
        product_name=ctx.product_name,
    )
    return cast(  # mypy -> aiocache is not typed.
        ServiceOutputGet,
        await ServiceOutputGetFactory.from_catalog_service_api_model(
            service=service, output_key=output_key
        ),
    )


async def get_compatible_outputs_given_target_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    to_service_key: ServiceKey,
    to_service_version: ServiceVersion,
    to_input_key: ServiceInputKey,
    ctx: CatalogRequestContext,
) -> list[ServiceOutputKey]:
    # N outputs
    service_outputs = await list_service_outputs(service_key, service_version, ctx)

    def iter_service_outputs() -> Iterator[tuple[ServiceOutputKey, ServiceOutput]]:
        for service_output in service_outputs:
            yield service_output.key_id, ServiceOutput.model_construct(
                **service_output.model_dump(include=ServiceOutput.model_fields.keys())  # type: ignore[arg-type]
            )

    # 1 input
    service_input = await get_service_input(
        to_service_key, to_service_version, to_input_key, ctx
    )
    to_input: ServiceInput = ServiceInput.model_construct(
        **service_input.model_dump(include=ServiceInput.model_fields.keys())  # type: ignore[arg-type]
    )

    # check
    matches = []
    for key_id, from_output in iter_service_outputs():
        if can_connect(from_output, to_input, units_registry=ctx.unit_registry):
            matches.append(key_id)

    return matches
