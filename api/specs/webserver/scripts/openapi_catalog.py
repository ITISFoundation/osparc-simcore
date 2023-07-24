from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_catalog.schemas.services import ServiceGet
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.catalog._handlers import (
    _FromServiceOutputParams,
    _ServiceInputsPathParams,
    _ServiceOutputsPathParams,
    _ServicePathParams,
    _ToServiceInputsParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "catalog",
    ],
)


@router.get(
    "/catalog/dags",
    response_model=None,
)
def list_catalog_dags():
    pass


@router.post(
    "/catalog/dags",
    response_model=None,
)
def create_catalog_dag(
    _add: CatalogDagsPostRequest = None,
):
    """
    Creates a new dag in catalog
    """


@router.put(
    "/catalog/dags/{dag_id}",
    response_model=None,
)
def replace_catalog_dag(dag_id: int, _new: CatalogDagsDagIdPutRequest = None):
    """
    Replaces a dag in catalog
    """


@router.delete("/catalog/dags/{dag_id}", response_model=None, tags=["catalog"])
def delete_catalog_dag(dag_id: int) -> None:
    """
    Deletes an existing dag
    """


@router.get(
    "/catalog/services",
    response_model=Envelope[list[ServiceGet]],
    operation_id="list_services_handler",
)
def list_services_handler():
    pass


@router.get(
    "/catalog/services/{service_key}/{service_version}",
    response_model=ServiceGet,
)
def get_service_handler(_params: Annotated[_ServicePathParams, Depends()]):
    ...


@router.patch(
    "/catalog/services/{service_key}/{service_version}",
    response_model=None,
)
def update_service_handler(
    _params: Annotated[_ServicePathParams, Depends()],
    _update: CatalogServicesServiceKeyServiceVersionPatchRequest = None,
):
    """
    Update Service
    """


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs",
    response_model=CatalogServicesServiceKeyServiceVersionInputsGetResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": CatalogServicesServiceKeyServiceVersionInputsGetResponse1
        }
    },
)
def list_service_inputs_handler(
    _params: Annotated[_ServicePathParams, Depends()],
):
    """
    List Service Inputs
    """


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs/{input_key}",
    response_model=CatalogServicesServiceKeyServiceVersionInputsInputKeyGetResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": CatalogServicesServiceKeyServiceVersionInputsInputKeyGetResponse1
        }
    },
)
def get_service_input_handler(
    _params: Annotated[_ServiceInputsPathParams, Depends()],
):
    """
    Get Service Input
    """


@router.get(
    "/catalog/services/{service_key}/{service_version}/inputs:match",
    response_model=List[constr(regex=r"^[-_a-zA-Z0-9]+$")],
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": CatalogServicesServiceKeyServiceVersionInputsMatchGetResponse
        }
    },
)
def get_compatible_inputs_given_source_output_handler(
    _params: Annotated[_ServicePathParams, Depends()],
    _qparams: Annotated[_FromServiceOutputParams, Depends()],
):
    """
    Get Compatible Inputs Given Source Output
    """


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs",
    response_model=List[CatalogServicesServiceKeyServiceVersionOutputsGetResponse],
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": CatalogServicesServiceKeyServiceVersionOutputsGetResponse1
        }
    },
)
def list_service_outputs_handler(
    _params: Annotated[_ServicePathParams, Depends()],
):
    """
    List Service Outputs
    """


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs/{output_key}",
    response_model=CatalogServicesServiceKeyServiceVersionOutputsOutputKeyGetResponse,
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": CatalogServicesServiceKeyServiceVersionOutputsOutputKeyGetResponse1
        }
    },
)
def get_service_output_handler(
    _params: Annotated[_ServiceOutputsPathParams, Depends()],
):
    """
    Get Service Output
    """


@router.get(
    "/catalog/services/{service_key}/{service_version}/outputs:match",
    response_model=List[constr(regex=r"^[-_a-zA-Z0-9]+$")],
    responses={
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": CatalogServicesServiceKeyServiceVersionOutputsMatchGetResponse
        }
    },
)
def get_compatible_outputs_given_target_input_handler(
    _params: Annotated[_ServicePathParams, Depends()],
    _qparams: Annotated[_ToServiceInputsParams, Depends()],
):
    """
    Get Compatible Outputs Given Target Input
    """


@router.get(
    "/catalog/services/{service_key}/{service_version}/resources",
    response_model=CatalogServicesServiceKeyServiceVersionResourcesGetResponse,
    responses={
        "default": {
            "model": CatalogServicesServiceKeyServiceVersionResourcesGetResponse1
        }
    },
)
def get_service_resources_handler(
    _params: Annotated[_ServicePathParams, Depends()],
):
    ...
