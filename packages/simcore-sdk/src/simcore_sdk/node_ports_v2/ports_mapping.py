from collections.abc import ItemsView, Iterator, KeysView, ValuesView

from models_library.services_types import ServicePortKey
from pydantic import RootModel

from ..node_ports_common.exceptions import UnboundPortError
from .port import Port


class BasePortsMapping(RootModel[dict[ServicePortKey, Port]]):
    def __getitem__(self, key: int | ServicePortKey) -> Port:
        if isinstance(key, int) and key < len(self.root):
            key = list(self.root.keys())[key]
        if key not in self.root:
            raise UnboundPortError(key)
        assert isinstance(key, str)  # nosec
        return self.root[key]

    def __iter__(self) -> Iterator[ServicePortKey]:  # type: ignore
        return iter(self.root)

    def keys(self) -> KeysView[ServicePortKey]:
        return self.root.keys()

    def items(self) -> ItemsView[ServicePortKey, Port]:
        return self.root.items()

    def values(self) -> ValuesView[Port]:
        return self.root.values()

    def __len__(self) -> int:
        return self.root.__len__()


class InputsList(BasePortsMapping):
    pass


class OutputsList(BasePortsMapping):
    pass
