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
# Models -----------------------------------------------------------------------------------------------
#

PortKindStr = Literal["input", "output"]


class ServicePortGet(BaseModel):
    name: str = Field(
        ..., description="port identifier name", regex=PUBLIC_VARIABLE_NAME_RE
    )
    kind: PortKindStr
    display_name: str
    content_schema: Optional[dict[str, Any]] = None

    @classmethod
    def from_service_io(
        cls,
        kind: PortKindStr,
        name: str,
        io: Union[ServiceInput, ServiceOutput],
    ) -> "ServicePortGet":
        return cls(
            name=name,
            display_name=io.label,
            kind=kind,
            content_schema=io.content_schema,
        )


#
# Routes -----------------------------------------------------------------------------------------------
#

router = APIRouter()


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
    ports: list[ServicePortGet] = []

    if service.inputs:
        for name, port in service.inputs.items():
            ports.append(ServicePortGet.from_service_io("input", name, port))

    if service.outputs:
        for name, port in service.outputs.items():
            ports.append(ServicePortGet.from_service_io("output", name, port))

    return ports
