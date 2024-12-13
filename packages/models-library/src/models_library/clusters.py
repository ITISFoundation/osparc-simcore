from enum import auto
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, HttpUrl, field_validator
from pydantic.types import NonNegativeInt

from .groups import GroupID
from .utils.common_validators import create_enums_pre_validator
from .utils.enums import StrAutoEnum


class ClusterTypeInModel(StrAutoEnum):
    # This enum contains more types than its equivalent to `simcore_postgres_database.models.clusters.ClusterType`
    # SEE models-library/tests/test__pydantic_models_and_enums.py
    AWS = auto()
    ON_PREMISE = auto()
    ON_DEMAND = auto()


class _AuthenticationBase(BaseModel):
    type: str

    model_config = ConfigDict(frozen=True, extra="forbid")


class NoAuthentication(_AuthenticationBase):
    type: Literal["none"] = "none"

    model_config = ConfigDict(json_schema_extra={"examples": [{"type": "none"}]})


class TLSAuthentication(_AuthenticationBase):
    type: Literal["tls"] = "tls"
    tls_ca_file: Path
    tls_client_cert: Path
    tls_client_key: Path

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "tls",
                    "tls_ca_file": "/path/to/ca_file",
                    "tls_client_cert": "/path/to/cert_file",
                    "tls_client_key": "/path/to/key_file",
                },
            ]
        }
    )


ClusterAuthentication: TypeAlias = NoAuthentication | TLSAuthentication


class BaseCluster(BaseModel):
    name: str = Field(..., description="The human readable name of the cluster")
    type: ClusterTypeInModel
    owner: GroupID
    thumbnail: HttpUrl | None = Field(
        default=None,
        description="url to the image describing this cluster",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
        validate_default=True,
    )
    endpoint: AnyUrl
    authentication: ClusterAuthentication = Field(
        ..., description="Dask gateway authentication", discriminator="type"
    )
    _from_equivalent_enums = field_validator("type", mode="before")(
        create_enums_pre_validator(ClusterTypeInModel)
    )

    model_config = ConfigDict(
        use_enum_values=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "My awesome cluster",
                    "type": ClusterTypeInModel.ON_PREMISE,
                    "owner": 12,
                    "endpoint": "https://registry.osparc-development.fake.dev",
                    "authentication": {
                        "type": "tls",
                        "tls_ca_file": "/path/to/ca_file",
                        "tls_client_cert": "/path/to/cert_file",
                        "tls_client_key": "/path/to/key_file",
                    },
                },
                {
                    "name": "My AWS cluster",
                    "type": ClusterTypeInModel.AWS,
                    "owner": 154,
                    "endpoint": "https://registry.osparc-development.fake.dev",
                    "authentication": {
                        "type": "tls",
                        "tls_ca_file": "/path/to/ca_file",
                        "tls_client_cert": "/path/to/cert_file",
                        "tls_client_key": "/path/to/key_file",
                    },
                },
            ]
        },
    )


ClusterID: TypeAlias = NonNegativeInt
