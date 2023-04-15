""" Reusable validators

    Example:

    from pydantic import BaseModel, validator

    class MyModel(BaseModel):
       thumbnail: str | None

       _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
           empty_str_to_none
       )

SEE https://docs.pydantic.dev/usage/validators/#reuse-validators
"""

from typing import Any


def empty_str_to_none(value: Any):
    if isinstance(value, str) and value.strip() == "":
        return None
    return value
