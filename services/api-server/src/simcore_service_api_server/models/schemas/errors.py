from typing import Any, ClassVar

from pydantic import BaseModel


class ErrorGet(BaseModel):
    # We intentionally keep it open until more restrictive policy is implemented
    # Check use cases:
    #   - https://github.com/ITISFoundation/osparc-issues/issues/958
    #   - https://github.com/ITISFoundation/osparc-simcore/issues/2520
    #   - https://github.com/ITISFoundation/osparc-simcore/issues/2446
    errors: list[Any]

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "errors": [
                    "some error message",
                    "another error message",
                ]
            }
        }
