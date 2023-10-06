from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.catalog import (
    ServiceGet,
    ServiceInputGet,
    ServiceInputKey,
    ServiceOutputGet,
    ServiceOutputKey,
    ServiceResourcesGet,
    ServiceUpdate,
)
from models_library.api_schemas_webserver.resource_usage import ServicePricingPlanGet
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.catalog._handlers import (
    ServicePathParams,
    _FromServiceOutputParams,
    _ServiceInputsPathParams,
    _ServiceOutputsPathParams,
    _ToServiceInputsParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "catalog",
    ],
)


#
# /catalog/services/* COLLECTION
#


@router.get(
    "/catalog/services",
    response_model=Envelope[list[ServiceGet]],
)
def list_services():
    pass


@router.get(
    "/catalog/services/{service_key}/{service_version}",
    response_model=Envelope[ServiceGet],
)
def get_service(_path_params: Annotated[ServicePathParams, Depends()]):
    ...


@router.patch(
    "/catalog/services/{service_key}/{service_version}",
    response_model=Envelope[ServiceGet],
)
def update_service(
    _path_params: Annotated[ServicePathParams, Depends()],
    _update: ServiceUpdate,
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs",
    response_model=Envelope[list[ServiceInputGet]],
)
def list_service_inputs(
    _path_params: Annotated[ServicePathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs/{input_key}",
    response_model=Envelope[ServiceInputGet],
)
def get_service_input(
    _path_params: Annotated[_ServiceInputsPathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs:match",
    response_model=Envelope[list[ServiceInputKey]],
)
def get_compatible_inputs_given_source_output(
    _path_params: Annotated[ServicePathParams, Depends()],
    _query_params: Annotated[_FromServiceOutputParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs",
    response_model=Envelope[list[ServiceOutputKey]],
)
def list_service_outputs(
    _path_params: Annotated[ServicePathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs/{output_key}",
    response_model=Envelope[list[ServiceOutputGet]],
)
def get_service_output(
    _path_params: Annotated[_ServiceOutputsPathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs:match",
    response_model=Envelope[list[ServiceOutputKey]],
)
def get_compatible_outputs_given_target_input(
    _path_params: Annotated[ServicePathParams, Depends()],
    _query_params: Annotated[_ToServiceInputsParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/resources",
    response_model=ServiceResourcesGet,
)
def get_service_resources(
    _params: Annotated[ServicePathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key:path}/{service_version}/pricing-plan",
    response_model=Envelope[ServicePricingPlanGet],
    summary="Retrieve default pricing plan for provided service",
    tags=["pricing-plans"],
)
async def get_service_pricing_plan(
    _params: Annotated[ServicePathParams, Depends()],
):
    ...
