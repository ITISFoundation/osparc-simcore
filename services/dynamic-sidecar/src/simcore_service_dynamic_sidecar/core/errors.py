from typing import List


class BaseDynamicSidecarError(Exception):
    """Used as base for all exceptions"""

    def __init__(self, nessage: str, status: int = 500) -> None:
        self.message: str = nessage
        self.status: int = status
        super().__init__(nessage)


class VolumeNotFoundError(BaseDynamicSidecarError):
    def __init__(self, source_label: str, volumes: List[str]) -> None:
        super().__init__(
            f"Expected 1 volume with {source_label=}, query returned {volumes}",
            status=404,
        )


class UnexpectedDockerError(BaseDynamicSidecarError):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(
            f"An unexpected Docker error occurred {status=}, {message=}", status=status
        )
