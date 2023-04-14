from models_library.basic_regex import VERSION_RE
from models_library.emails import LowerCaseEmailStr
from models_library.projects_nodes import Node
from models_library.services import SERVICE_KEY_RE
from pydantic import BaseModel, Field, Json


class DAGBase(BaseModel):
    key: str = Field(
        ...,
        regex=SERVICE_KEY_RE,
        example="simcore/services/frontend/nodes-group/macros/1",
    )
    version: str = Field(..., regex=VERSION_RE, example="1.0.0")
    name: str
    description: str | None
    contact: LowerCaseEmailStr | None


class DAGAtDB(DAGBase):
    id: int
    # pylint: disable=unsubscriptable-object
    workbench: Json[dict[str, Node]]  # type: ignore

    class Config:
        orm_mode = True


class DAGData(DAGAtDB):
    workbench: dict[str, Node] | None  # type: ignore
