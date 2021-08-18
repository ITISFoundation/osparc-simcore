# pylint: disable=unused-argument

import json
from typing import List

from fastapi import FastAPI, Query
from simcore_service_webserver.catalog_api_models import (
    ServiceInputApiOut,
    ServiceInputKey,
    ServiceKey,
    ServiceOutputApiOut,
    ServiceOutputKey,
    ServiceVersion,
)

app = FastAPI()


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/inputs",
    response_model=ServiceInputApiOut,
    operation_id="list_service_inputs_handler",
)
def list_service_inputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    pass


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/inputs/{input_key}",
    response_model=ServiceInputApiOut,
    operation_id="get_service_input_handler",
)
def get_service_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    input_key: ServiceInputKey,
):
    pass


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/inputs:match",
    response_model=List[ServiceInputKey],
    operation_id="get_compatible_inputs_given_source_output_handler",
)
def get_compatible_inputs_given_source_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    from_service_key: ServiceKey = Query(..., alias="fromService"),
    from_service_version: ServiceVersion = Query(..., alias="fromVersion"),
    from_output_key: ServiceOutputKey = Query(..., alias="fromOutput"),
):
    """
        Filters inputs of this service that match a given service output

    Returns compatible input ports of the service, provided an output port of
    a connected node.

    """
    # TODO: uuid instead of key+version?

    pass


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/outputs",
    response_model=List[ServiceOutputApiOut],
    operation_id="list_service_outputs_handler",
)
def list_service_outputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    pass


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/outputs/{output_key}",
    response_model=ServiceOutputApiOut,
    operation_id="get_service_output_handler",
)
def get_service_output(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    output_key: ServiceOutputKey,
):
    pass


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/outputs:match",
    response_model=List[ServiceOutputKey],
    operation_id="get_compatible_outputs_given_target_input_handler",
)
def get_compatible_outputs_given_target_input(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    to_service_key: ServiceKey = Query(..., alias="toService"),
    to_service_version: ServiceVersion = Query(..., alias="toVersion"),
    to_input_key: ServiceInputKey = Query(..., alias="toInput"),
):
    """
    Filters outputs of this service that match a given service input

    Returns compatible output port of a connected node for a given input

    """
    pass


print(json.dumps(app.openapi(), indent=2))
