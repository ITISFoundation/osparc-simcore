from typing import Any, Dict, Type

from pydantic import AnyUrl, BaseModel, Extra, Field, create_model

SleeperInputs = create_model(
    "SleeperInputs",
    input_1=(AnyUrl, Field(..., alias="single_file.txt")),
    input_2=(int, Field(..., description="some funny number")),
    __module__=__name__,
)

SleeperOutputs = create_model(
    "SleeperOutputs",
    output_1=(AnyUrl, Field(..., alias="single_file.txt")),
    output_2=(int, Field(..., description="some funny number")),
    __module__=__name__,
)


class TaskBaseModel(BaseModel):
    class Config:
        extra = Extra.forbid


def create_inputs_signature(
    name: str, input_data: Dict[str, Any]
) -> Type[TaskBaseModel]:
    return create_model(
        name,
        **{k: (type(v), Field(...)) for k, v in input_data},
        __module__=__name__,
        __base__=TaskBaseModel
    )
