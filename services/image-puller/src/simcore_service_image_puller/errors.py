from typing import Any


class ImagePullerError(Exception):
    def __init__(self, msg: str, *context: Any) -> None:
        self.context = context
        super().__init__(msg)
