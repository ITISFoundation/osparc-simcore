from typing import Dict, Tuple, Type, Union

from models_library.services import PROPERTY_KEY_RE
from pydantic import (
    AnyUrl,
    BaseModel,
    Extra,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    create_model,
)
from pydantic.fields import FieldInfo
from typing_extensions import Annotated


class TaskBaseModel(BaseModel):
    class Config:
        extra = Extra.forbid


PortKey = Annotated[str, Field(regex=PROPERTY_KEY_RE)]
InputTypes = Union[
    Type[StrictBool], Type[StrictInt], Type[StrictFloat], Type[StrictStr], Type[AnyUrl]
]


def create_inputs_signature(
    name: str,
    input_data: Dict[
        PortKey,
        Tuple[InputTypes, FieldInfo],
    ],
) -> Type[TaskBaseModel]:
    return create_model(name, **input_data, __module__=__name__, __base__=TaskBaseModel)
