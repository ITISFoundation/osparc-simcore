from models_library.functions import FunctionID
from pydantic import BaseModel, ConfigDict

from ...models import RequestContext

assert RequestContext.__name__  # nosec


class FunctionPathParams(BaseModel):
    function_id: FunctionID
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


__all__: tuple[str, ...] = ("RequestContext",)
