from abc import ABC
from dataclasses import dataclass, field
from typing import Callable, ClassVar

from simcore_service_storage.dsm import DataStorageManager

DataStorageID = str


@dataclass
class DataStorageBase(ABC):
    data_storage_id: ClassVar[DataStorageID]


@dataclass
class DataStorageFactory:
    _creators: dict[DataStorageID, Callable] = field(default={})

    def register_data_storage(self, creator: DataStorageBase):
        self._creators[creator.data_storage_id] = creator

    def get_serializer(self, dsm_id: DataStorageID):
        creator = self._creators.get(dsm_id)
        if not creator:
            raise ValueError(dsm_id)
        return creator()


factory = DataStorageFactory()
factory.register_data_storage(DataStorageManager)
