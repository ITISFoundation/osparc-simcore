from models_library.functions import FunctionID
from models_library.rest_pagination import PageQueryParameters
from pydantic import BaseModel, ConfigDict

from ...models import AuthenticatedRequestContext

assert AuthenticatedRequestContext.__name__  # nosec


class FunctionPathParams(BaseModel):
    function_id: FunctionID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class _FunctionQueryParams(BaseModel):
    include_extras: bool = False


class FunctionGetQueryParams(_FunctionQueryParams): ...


class FunctionsListQueryParams(PageQueryParameters, _FunctionQueryParams): ...


__all__: tuple[str, ...] = ("AuthenticatedRequestContext",)
