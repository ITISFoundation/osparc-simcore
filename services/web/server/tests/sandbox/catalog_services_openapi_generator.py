# pylint: disable=unused-argument

import json
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Query
from models_library.services import (
    KEY_RE,
    VERSION_RE,
    PropertyName,
    ServiceInput,
    ServiceOutput,
)
from pydantic import BaseModel, Extra, Field, constr
from simcore_service_webserver.utils import snake_to_camel

this_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()


ServiceKey = constr(regex=KEY_RE)
ServiceVersion = constr(regex=VERSION_RE)

app = FastAPI()


ServiceInputKey = PropertyName
ServiceOutputKey = PropertyName


# Using ApiOut/ApiIn suffix to distinguish API models vs internal domain model
#  - internal domain models should be consise, non-verbose, minimal, correct
#  - API models should be adapted to API user needs
#  - warning with couplings! Add example to ensure that API model maintain
#    backwards compatibility
#
# TODO: uuid instead of key+version?


class ServiceInputApiOut(ServiceInput):
    key_id: ServiceInputKey = Field(
        ..., description="Unique name identifier for this input"
    )
    unit_long: Optional[str] = Field(
        None, description="Long name of the unit, if available"
    )
    unit_short: Optional[str] = Field(
        None, description="Short name for the unit, if available"
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        # Add example v1, v2, ...


class ServiceOutputApiOut(ServiceOutput):
    key_id: ServiceInputKey = Field(
        ..., description="Unique name identifier for this input"
    )

    class Config:
        extra = Extra.forbid
        alias_generator = snake_to_camel
        # Add example v1, v2, ...


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/inputs",
    response_model=ServiceInputApiOut,
)
def list_service_inputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    pass


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/inputs/{input_key}",
    response_model=ServiceInputApiOut,
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
)
def list_service_outputs(
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    pass


@app.get(
    "/catalog/services/{service_key:path}/{service_version}/outputs/{output_key}",
    response_model=ServiceOutputApiOut,
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


##############


class TargetMatch(BaseModel):
    service_key: ServiceKey
    service_version: ServiceVersion
    input_key: Optional[PropertyName]


class MatchResult(BaseModel):
    ok: bool = Field(description="Compatibility was found")


# @app.get(
#    "/catalog/services/{service_key:path}/{service_version}/inputs:match",
#    response_model=MatchResult,
# )
def get_compatible_inputs_given_source(
    service_key: ServiceKey,
    service_version: ServiceVersion,
    from_service_key: ServiceKey,
    from_service_version: ServiceVersion,
    from_output_key: PropertyName,
):
    """
    Returns compatible ports
    """
    pass


print(json.dumps(app.openapi(), indent=2))
