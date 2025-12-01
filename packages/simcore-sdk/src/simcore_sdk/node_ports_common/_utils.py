from abc import abstractmethod


class BaseLogParser:
    @abstractmethod
    async def __call__(self, logs: str) -> None: ...
