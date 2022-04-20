from typing import Union

from models_library.generics import DictModel
from pydantic import BaseModel, StrictFloat, StrictInt, root_validator

ResourceName = str


class ResourceValue(BaseModel):
    limit: Union[StrictInt, StrictFloat, str]
    reservation: Union[StrictInt, StrictFloat, str]

    @root_validator()
    @classmethod
    def ensure_limits_are_equal_or_above_reservations(cls, values):
        if isinstance(values["reservation"], str):
            # in case of string, the limit is the same as the reservation
            values["limit"] = values["reservation"]
        else:
            values["limit"] = max(values["limit"], values["reservation"])

        return values


ServiceResources = DictModel[ResourceName, ResourceValue]
