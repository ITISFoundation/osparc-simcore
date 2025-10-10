from typing import TypeAlias, TypedDict

from models_library.api_schemas_catalog.services import MyServicesRpcBatchGet


class ServiceKeyVersionDict(TypedDict):
    key: str
    version: str


MyServicesBatchGetResult: TypeAlias = MyServicesRpcBatchGet
