from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, ClassVar, Generic, TypeAlias, TypeVar

from pydantic import NonNegativeInt

from ._models import ClassUniqueReference, TaskResultError, TaskUID

ResultType = TypeVar("ResultType")

StartContext: TypeAlias = dict[str, Any]
GlobalsContext: TypeAlias = dict[str, Any]

# composed by merging `GlobalsContext` and `StartContext`
DeferredContext: TypeAlias = dict[str, Any]


class BaseDeferredHandler(ABC, Generic[ResultType]):
    """Base class to define a deferred task."""

    _SUBCLASSES: ClassVar[list[type["BaseDeferredHandler"]]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDeferredHandler._SUBCLASSES.append(cls)

    @classmethod
    def _get_class_unique_reference(cls) -> ClassUniqueReference:
        """
        returns: a unique reference for this class (module and name)
        """
        return f"{cls.__module__}.{cls.__name__}"

    @classmethod
    async def get_retries(cls, context: DeferredContext) -> NonNegativeInt:
        """
        returns: the amount of retries in case of error (default: 0)

        This is used only when ``run`` raises an error other than `asyncio.CancelledError`` and this
        value is > 0. The code inside ``run`` will be retried.

        NOTE: if the process running the ``run`` code dies, it automatically gets
        retried when the process is restarted or by another copy of the service.
        """
        assert context  # nosec
        return 0

    @classmethod
    @abstractmethod
    async def get_timeout(cls, context: DeferredContext) -> timedelta:
        """return the timeout for the execution of `run`.
        If ``run`` does not finish executing in time a timeout exception will be raised
        """

    @classmethod
    @abstractmethod
    async def start(cls, **kwargs) -> StartContext:
        """
        Used to start a deferred.
        These values will be passed to ``run`` when it's ran.
        """

    @classmethod
    async def on_created(cls, task_uid: TaskUID, context: DeferredContext) -> None:
        """called after deferred was scheduled to run"""

    @classmethod
    @abstractmethod
    async def run(cls, context: DeferredContext) -> ResultType:
        """code to be ran by a worker"""

    @classmethod
    @abstractmethod
    async def on_result(cls, result: ResultType, context: DeferredContext) -> None:
        """called when ``run`` provided a successful result"""

    @classmethod
    async def on_finished_with_error(
        cls, error: TaskResultError, context: DeferredContext
    ) -> None:
        """
        called when ``run`` code raises an error

        NOTE: by design the default action is to do nothing
        """

    @classmethod
    async def cancel(cls, task_uid: TaskUID) -> None:
        """cancels a deferred"""

    @classmethod
    async def is_present(cls, task_uid: TaskUID) -> bool:
        """checks if deferred is still scheduled and has not finished

        Returns:
            `True` while task execution is not finished
            `False` if task is no longer present
        """
