""" Handlers for STANDARD methods on /projects colletions

Standard methods or CRUD that states for Create+Read(Get&List)+Update+Delete

"""

from models_library.projects import ProjectID
from models_library.users import UserID
from pydantic import BaseModel, Extra, Field
from servicelib.request_keys import RQT_USERID_KEY

from .._constants import RQ_PRODUCT_KEY


class RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class ProjectPathParams(BaseModel):
    project_id: ProjectID

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid
