from uuid import UUID

from models_library.api_schemas_webserver._base import OutputSchema
from pydantic import BaseModel, ConfigDict, Field

# TODO: move to _schemas or to models_library.api_schemas_webserver??

#
# TOKENS resource
#
class ThirdPartyToken(BaseModel):
    """
    Tokens used to access third-party services connected to osparc (e.g. pennsieve, scicrunch, etc)
    """

    service: str = Field(
        ..., description="uniquely identifies the service where this token is used"
    )
    token_key: UUID = Field(..., description="basic token key")
    token_secret: UUID | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "github-api-v1",
                "token_key": "5f21abf5-c596-47b7-bfd1-c0e436ef1107",
            }
        }
    )


class TokenCreate(ThirdPartyToken):
    ...


#
# Permissions
#
class Permission(BaseModel):
    name: str
    allowed: bool


class PermissionGet(Permission, OutputSchema):
    ...
