from fastapi import Response
from starlette.background import BackgroundTask


class NoContentResponse(Response):
    def __init__(
        self,  # pylint: disable=unused-argument
        status_code: int = 204,
        headers: dict = None,
        background: BackgroundTask = None,
    ) -> None:
        super().__init__(
            content=b"", status_code=status_code, headers=headers, background=background
        )
