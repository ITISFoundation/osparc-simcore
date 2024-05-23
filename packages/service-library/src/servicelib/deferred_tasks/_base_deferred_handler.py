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

    SUBCLASSES: ClassVar[list[type["BaseDeferredHandler"]]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDeferredHandler.SUBCLASSES.append(cls)

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

        This is used only when ``run_deferred`` raises an error other than `asyncio.CancelledError`` and this
        value is > 0. The code inside ``run_deferred`` will be retried.

        NOTE: if the process running the ``run_deferred`` code dies, it automatically gets
        retried when the process is restarted or by another copy of the service.
        """

        _ = context
        return 0

    @classmethod
    @abstractmethod
    async def get_timeout(cls, context: DeferredContext) -> timedelta:
        """return the timeout for the execution of `run_deferred`.
        If ``run_deferred`` does not finish executing in time a timeout exception will be raised
        """

    @classmethod
    @abstractmethod
    async def start_deferred(cls, **kwargs) -> StartContext:
        """
        helper function to be overwritten by the user and generates
        the data passed to run_deferred.

        Inside ``**kwargs`` the ``globals_for_start_context`` are also injected in addition
        to any user provided fields when invoked from the subclass.

        hast to returns: a context context object used during ``run_deferred`` and
            to process the result inside ``deferred_result``
        """
        # NOTE: intercepted by ``DeferredManager``

    @classmethod
    async def on_deferred_created(
        cls, task_uid: TaskUID, context: DeferredContext
    ) -> None:
        """return after deferred was scheduled"""

    @classmethod
    @abstractmethod
    async def run_deferred(cls, context: DeferredContext) -> ResultType:
        """Code to be run in the background"""

    @classmethod
    @abstractmethod
    async def on_deferred_result(
        cls, result: ResultType, context: DeferredContext
    ) -> None:
        """Called in case `run_deferred` ended and provided a successful result"""

    @classmethod
    async def on_finished_with_error(
        cls, error: TaskResultError, context: DeferredContext
    ) -> None:
        """
        NOTE: by design the default action is to do nothing
        """

    @classmethod
    async def cancel_deferred(cls, task_uid: TaskUID) -> None:
        """User can call this method to cancel the task"""
        # NOTE: intercepted by ``DeferredManager``
