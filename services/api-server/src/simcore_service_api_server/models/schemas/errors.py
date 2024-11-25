from typing import Any

from pydantic import BaseModel, ConfigDict


class ErrorGet(BaseModel):
    # We intentionally keep it open until more restrictive policy is implemented
    # Check use cases:
    #   - https://github.com/ITISFoundation/osparc-issues/issues/958
    #   - https://github.com/ITISFoundation/osparc-simcore/issues/2520
    #   - https://github.com/ITISFoundation/osparc-simcore/issues/2446
    errors: list[Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "errors": [
                    "some error message",
                    "another error message",
                ]
            }
        }
    )
