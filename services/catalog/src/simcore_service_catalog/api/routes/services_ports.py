import logging
from typing import Any, Literal, Optional, Union

from fastapi import APIRouter, Depends
from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from models_library.services import ServiceInput, ServiceOutput
from pydantic import BaseModel, Field

from ...models.schemas.constants import RESPONSE_MODEL_POLICY
from ...models.schemas.services import ServiceGet
from ..dependencies.services import get_service_from_registry

logger = logging.getLogger(__name__)


#
# Models
#


PortKindStr = Literal["input", "output"]


class ServicePortGet(BaseModel):
    name: str = Field(
        ..., description="port identifier name", regex=PUBLIC_VARIABLE_NAME_RE
    )
    kind: PortKindStr = Field(..., description="Kind of port: input or output")

    display_name: str

    # https://swagger.io/docs/specification/describing-request-body/
    # https://www.iana.org/assignments/media-types/media-types.xhtml
    # media_type: str = Field(..., description="file or in-memory data and if former, what type ?")
    # FIXME: a file is passed in a variaty of
    #
    content_schema: Optional[dict[str, Any]] = None

    # TODO: here in the future there is more metadata on the port

    @classmethod
    def from_service_io(
        cls,
        kind: PortKindStr,
        name: str,
        service_io: Union[ServiceInput, ServiceOutput],
    ) -> "ServicePortGet":
        # TODO: for old formats, should we converted to_json_schema??
        return cls(
            name=name,
            display_name=service_io.label,
            kind=kind,
            content_schema=service_io.content_schema,
        )


#
# Routes
#

router = APIRouter()

# TODO: update version


@router.get(
    "/{service_key:path}/{service_version}/ports",
    response_model=list[ServicePortGet],
    description="Returns a list of service ports starting with inputs and followed by outputs",
    **RESPONSE_MODEL_POLICY,
)
async def list_service_ports(
    user_id: int,
    service: ServiceGet = Depends(get_service_from_registry),
):
    assert user_id  # nosec
    # FIXME: auth !!!
    # FIXME: product?
    # TODO: add e.g. filter='kind==input'?

    ports: list[ServicePortGet] = []

    if service.inputs:
        for name, port in service.inputs.items():
            ports.append(ServicePortGet.from_service_io("input", name, port))

    if service.outputs:
        for name, port in service.outputs.items():
            ports.append(ServicePortGet.from_service_io("output", name, port))

    return ports
