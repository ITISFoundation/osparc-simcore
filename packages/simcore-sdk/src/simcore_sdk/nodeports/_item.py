from ._data_item import DataItem
from ._schema_item import SchemaItem

class Item():
    def __init__(self, schema:SchemaItem, data:DataItem):
        self._schema = schema
        self._data = data

    def __getattr__(self, name):
        if hasattr(self._schema, name):
            return getattr(self._schema, name)
        if hasattr(self._data, name):
            return getattr(self._data, name)

        if "value" in name and not self._data:
            if hasattr(self._schema, "defaultValue"):
                return getattr(self._schema, "defaultValue")
            return None
        raise AttributeError

    def get(self):
        pass
    
    def set(self, value):
        pass