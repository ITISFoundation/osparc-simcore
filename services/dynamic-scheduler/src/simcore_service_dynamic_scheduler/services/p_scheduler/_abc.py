from abc import ABC, abstractmethod
from datetime import timedelta

from ._models import DagNodeUniqueReference, InData, InDataKeys, OutData, OutDataKeys


class BaseStep(ABC):
    @classmethod
    def get_unique_reference(cls) -> DagNodeUniqueReference:
        """Unique reference for this step class"""
        return f"{cls.__module__}.{cls.__name__}"

    ### APPLY ###

    @classmethod
    def apply_requests_inputs(cls) -> InDataKeys:
        """Defines which inputs are required to run the apply step"""
        return set()

    @classmethod
    def apply_provides_outputs(cls) -> OutDataKeys:
        """Defines which outputs are provided after running the apply step"""
        return set()

    @classmethod
    @abstractmethod
    async def apply(cls, in_data: InData) -> OutData:
        """actions that construct/create resources in the system"""

    @classmethod
    @abstractmethod
    def get_apply_timeout(cls) -> timedelta:
        """max amount of time after which the apply step will be cancelled"""

    ### REVERT ###

    @classmethod
    def revert_requests_inputs(cls) -> InDataKeys:
        """defines which inputs are required to run the revert step"""
        return set()

    @classmethod
    def revert_provides_outputs(cls) -> OutDataKeys:
        """defines which outputs are provided after running the revert step"""
        return set()

    @classmethod
    @abstractmethod
    async def revert(cls, in_data: InData) -> OutData:
        """actions that destroy/remove resources from the system"""

    @classmethod
    @abstractmethod
    def get_revert_timeout(cls) -> timedelta:
        """max amount of time after which the revert step will be cancelled"""
