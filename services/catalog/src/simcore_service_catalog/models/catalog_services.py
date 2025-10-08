from typing import TypeAlias

from models_library.api_schemas_catalog.services import MyServicesRpcBatchGet

# NOTE: for now schema and domain are identical. If they differ in the future
# this indirection will allow us to transform between the two
BatchGetUserServicesResult: TypeAlias = MyServicesRpcBatchGet
