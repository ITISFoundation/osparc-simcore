from typing import Union

from models_library.generics import DictModel
from pydantic import BaseModel, StrictFloat, StrictInt, root_validator

ResourceName = str
ResourceValue = Union[StrictInt, StrictFloat, str]


ResourcesDict = DictModel[ResourceName, ResourceValue]


class ServiceResources(BaseModel):
    limits: ResourcesDict
    reservations: ResourcesDict

    @root_validator()
    @classmethod
    def ensure_limits_are_equal_or_above_reservations(cls, values):

        for key, value in values["reservations"].items():
            if isinstance(value, str):
                values["limits"][key] = values["limits"].get(key, value)
            else:
                values["limits"][key] = max(values["limits"].get(key, value), value)
        return values
