import logging
from collections.abc import Mapping
from typing import Dict

from . import exceptions
from ._schema_item import SchemaItem

log = logging.getLogger(__name__)


class SchemaItemsList(Mapping):
    def __init__(self, data: Dict[str, SchemaItem] = None):
        log.debug("creating SchemaItemsList with %s", data)
        if not data:
            data = {}
        self._store = data

    def __getitem__(self, key) -> SchemaItem:
        if isinstance(key, int):
            if key < len(self._store):
                key = list(self._store.keys())[key]
        if not key in self._store:
            raise exceptions.UnboundPortError(key)
        return self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)
