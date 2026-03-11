from fastapi import Response
from starlette.background import BackgroundTask


class NoContentResponse(Response):
    def __init__(
        self,  # pylint: disable=unused-argument
        status_code: int = 204,
        headers: dict = None,  # type: ignore[assignment]
        background: BackgroundTask = None,  # type: ignore[assignment]
    ) -> None:
        super().__init__(content=b"", status_code=status_code, headers=headers, background=background)
