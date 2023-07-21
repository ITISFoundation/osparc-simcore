
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from models_library.generics import Envelope
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.diagnostics._handlers import (
    AppStatusCheck,
    StatusDiagnosticsGet,
    StatusDiagnosticsQueryParam,
)
from simcore_service_webserver.rest.healthcheck import HealthInfoDict

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "catalog",
    ],
)



@router.get(
    '/catalog/dags',
    response_model=None,
    responses={'default': {'model': CatalogDagsGetResponse}},

)
def list_catalog_dags() -> Union[None, CatalogDagsGetResponse]:
    pass


@router.post(
    '/catalog/dags',
    response_model=None,
    responses={'default': {'model': CatalogDagsPostResponse}},

)
def create_catalog_dag(
    body: CatalogDagsPostRequest = None,
) -> Union[None, CatalogDagsPostResponse]:
    """
    Creates a new dag in catalog
    """
    pass


@router.put(
    '/catalog/dags/{dag_id}',
    response_model=None,
    responses={'default': {'model': CatalogDagsDagIdPutResponse}},

)
def replace_catalog_dag(
    dag_id: int, body: CatalogDagsDagIdPutRequest = None
) -> Union[None, CatalogDagsDagIdPutResponse]:
    """
    Replaces a dag in catalog
    """
    pass


@router.delete('/catalog/dags/{dag_id}', response_model=None, tags=['catalog'])
def delete_catalog_dag(dag_id: int) -> None:
    """
    Deletes an existing dag
    """
    pass


@router.get(
    '/catalog/services',
    response_model=None,
    responses={'default': {'model': CatalogServicesGetResponse}},

)
def list_services_handler() -> Union[None, CatalogServicesGetResponse]:
    """
    List Services
    """
    pass


@router.get(
    '/catalog/services/{service_key}/{service_version}',
    response_model=None,
    responses={
        'default': {'model': CatalogServicesServiceKeyServiceVersionGetResponse}
    },

)
def get_service_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
) -> Union[None, CatalogServicesServiceKeyServiceVersionGetResponse]:
    """
    Get Service
    """
    pass


@router.patch(
    '/catalog/services/{service_key}/{service_version}',
    response_model=None,
    responses={
        'default': {'model': CatalogServicesServiceKeyServiceVersionPatchResponse}
    },

)
def update_service_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
    body: CatalogServicesServiceKeyServiceVersionPatchRequest = None,
) -> Union[None, CatalogServicesServiceKeyServiceVersionPatchResponse]:
    """
    Update Service
    """
    pass


@router.get(
    '/catalog/services/{service_key}/{service_version}/inputs',
    response_model=CatalogServicesServiceKeyServiceVersionInputsGetResponse,
    responses={
        '422': {'model': CatalogServicesServiceKeyServiceVersionInputsGetResponse1}
    },

)
def list_service_inputs_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
) -> Union[
    CatalogServicesServiceKeyServiceVersionInputsGetResponse,
    CatalogServicesServiceKeyServiceVersionInputsGetResponse1,
]:
    """
    List Service Inputs
    """
    pass


@router.get(
    '/catalog/services/{service_key}/{service_version}/inputs/{input_key}',
    response_model=CatalogServicesServiceKeyServiceVersionInputsInputKeyGetResponse,
    responses={
        '422': {
            'model': CatalogServicesServiceKeyServiceVersionInputsInputKeyGetResponse1
        }
    },

)
def get_service_input_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
    input_key: constr(regex=r'^[-_a-zA-Z0-9]+$') = ...,
) -> Union[
    CatalogServicesServiceKeyServiceVersionInputsInputKeyGetResponse,
    CatalogServicesServiceKeyServiceVersionInputsInputKeyGetResponse1,
]:
    """
    Get Service Input
    """
    pass


@router.get(
    '/catalog/services/{service_key}/{service_version}/inputs:match',
    response_model=List[constr(regex=r'^[-_a-zA-Z0-9]+$')],
    responses={
        '422': {'model': CatalogServicesServiceKeyServiceVersionInputsMatchGetResponse}
    },

)
def get_compatible_inputs_given_source_output_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
    from_service: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ) = Query(..., alias='fromService'),
    from_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = Query(..., alias='fromVersion'),
    from_output: constr(regex=r'^[-_a-zA-Z0-9]+$') = Query(..., alias='fromOutput'),
) -> Union[
    List[constr(regex=r'^[-_a-zA-Z0-9]+$')],
    CatalogServicesServiceKeyServiceVersionInputsMatchGetResponse,
]:
    """
    Get Compatible Inputs Given Source Output
    """
    pass


@router.get(
    '/catalog/services/{service_key}/{service_version}/outputs',
    response_model=List[CatalogServicesServiceKeyServiceVersionOutputsGetResponse],
    responses={
        '422': {'model': CatalogServicesServiceKeyServiceVersionOutputsGetResponse1}
    },

)
def list_service_outputs_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
) -> Union[
    List[CatalogServicesServiceKeyServiceVersionOutputsGetResponse],
    CatalogServicesServiceKeyServiceVersionOutputsGetResponse1,
]:
    """
    List Service Outputs
    """
    pass


@router.get(
    '/catalog/services/{service_key}/{service_version}/outputs/{output_key}',
    response_model=CatalogServicesServiceKeyServiceVersionOutputsOutputKeyGetResponse,
    responses={
        '422': {
            'model': CatalogServicesServiceKeyServiceVersionOutputsOutputKeyGetResponse1
        }
    },

)
def get_service_output_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
    output_key: constr(regex=r'^[-_a-zA-Z0-9]+$') = ...,
) -> Union[
    CatalogServicesServiceKeyServiceVersionOutputsOutputKeyGetResponse,
    CatalogServicesServiceKeyServiceVersionOutputsOutputKeyGetResponse1,
]:
    """
    Get Service Output
    """
    pass


@router.get(
    '/catalog/services/{service_key}/{service_version}/outputs:match',
    response_model=List[constr(regex=r'^[-_a-zA-Z0-9]+$')],
    responses={
        '422': {'model': CatalogServicesServiceKeyServiceVersionOutputsMatchGetResponse}
    },

)
def get_compatible_outputs_given_target_input_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
    to_service: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ) = Query(..., alias='toService'),
    to_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = Query(..., alias='toVersion'),
    to_input: constr(regex=r'^[-_a-zA-Z0-9]+$') = Query(..., alias='toInput'),
) -> Union[
    List[constr(regex=r'^[-_a-zA-Z0-9]+$')],
    CatalogServicesServiceKeyServiceVersionOutputsMatchGetResponse,
]:
    """
    Get Compatible Outputs Given Target Input
    """
    pass


@router.get(
    '/catalog/services/{service_key}/{service_version}/resources',
    response_model=CatalogServicesServiceKeyServiceVersionResourcesGetResponse,
    responses={
        'default': {
            'model': CatalogServicesServiceKeyServiceVersionResourcesGetResponse1
        }
    },

)
def get_service_resources_handler(
    service_key: constr(
        regex=r'^(simcore)/(services)/(comp|dynamic|frontend)(/[\w/-]+)+$'
    ),
    service_version: constr(
        regex=r'^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$'
    ) = ...,
) -> Union[
    CatalogServicesServiceKeyServiceVersionResourcesGetResponse,
    CatalogServicesServiceKeyServiceVersionResourcesGetResponse1,
]:
    pass
