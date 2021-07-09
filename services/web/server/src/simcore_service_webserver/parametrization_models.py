from typing import Union

from pydantic import BaseModel


class Parameter(BaseModel):
    name: str
    value: Union[bool, float, str]
