import logging
from typing import Annotated, Literal

from aiohttp import web
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.users import UserID
from pydantic import Field
from servicelib.request_keys import RQT_USERID_KEY

from ..constants import RQ_PRODUCT_KEY

routes = web.RouteTableDef()


_logger = logging.getLogger(__name__)


class ProductsRequestContext(RequestParameters):
    user_id: Annotated[UserID, Field(alias=RQT_USERID_KEY)]
    product_name: Annotated[ProductName, Field(..., alias=RQ_PRODUCT_KEY)]


class ProductsRequestParams(StrictRequestParameters):
    product_name: IDStr | Literal["current"]
