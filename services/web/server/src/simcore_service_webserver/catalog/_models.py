from typing import TypedDict

from models_library.api_schemas_catalog.services import MyServicesRpcBatchGet


class ServiceKeyVersionDict(TypedDict):
    key: str
    version: str


type MyServicesBatchGetResult = MyServicesRpcBatchGet
