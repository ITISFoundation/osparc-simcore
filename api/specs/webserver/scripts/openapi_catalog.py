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
    operation_id="list_services",
    response_model=Envelope[list[ServiceGet]],
)
def list_services():
    pass


@router.get(
    "/catalog/services/{service_key}/{service_version}",
    response_model=Envelope[ServiceGet],
    operation_id="get_service",
)
def get_service(_path_params: Annotated[ServicePathParams, Depends()]):
    ...


@router.patch(
    "/catalog/services/{service_key}/{service_version}",
    response_model=Envelope[ServiceGet],
    operation_id="update_service",
)
def update_service(
    _path_params: Annotated[ServicePathParams, Depends()],
    _update: ServiceUpdate,
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs",
    response_model=Envelope[list[ServiceInputGet]],
    operation_id="list_service_inputs",
)
def list_service_inputs(
    _path_params: Annotated[ServicePathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs/{input_key}",
    response_model=Envelope[ServiceInputGet],
    operation_id="get_service_input",
)
def get_service_input(
    _path_params: Annotated[_ServiceInputsPathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs:match",
    response_model=Envelope[list[ServiceInputKey]],
    operation_id="get_compatible_inputs_given_source_output",
)
def get_compatible_inputs_given_source_output(
    _path_params: Annotated[ServicePathParams, Depends()],
    _query_params: Annotated[_FromServiceOutputParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs",
    response_model=Envelope[list[ServiceOutputKey]],
    operation_id="list_service_outputs",
)
def list_service_outputs(
    _path_params: Annotated[ServicePathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs/{output_key}",
    response_model=Envelope[list[ServiceOutputGet]],
    operation_id="get_service_output",
)
def get_service_output(
    _path_params: Annotated[_ServiceOutputsPathParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs:match",
    response_model=Envelope[list[ServiceOutputKey]],
    operation_id="get_compatible_outputs_given_target_input",
)
def get_compatible_outputs_given_target_input(
    _path_params: Annotated[ServicePathParams, Depends()],
    _query_params: Annotated[_ToServiceInputsParams, Depends()],
):
    ...


@router.get(
    "/catalog/services/{service_key}/{service_version}/resources",
    response_model=ServiceResourcesGet,
    operation_id="get_service_resources",
)
def get_service_resources(
    _params: Annotated[ServicePathParams, Depends()],
):
    ...
