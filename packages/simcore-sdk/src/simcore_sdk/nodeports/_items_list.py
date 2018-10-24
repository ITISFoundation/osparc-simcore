import logging
from collections import Sequence
from . import exceptions
from ._data_items_list import DataItemsList
from ._schema_items_list import SchemaItemsList
from ._item import Item

log = logging.getLogger(__name__)



class ItemsList(Sequence):

    def __init__(self, schemas: SchemaItemsList, payloads: DataItemsList):
        self._schemas = schemas
        self._payloads = payloads        
    
    def __getitem__(self, key)->Item:
        schema = self._schemas[key]
        try:
            payload = self._payloads[schema.key]
        except exceptions.InvalidKeyError:
            # there is no payload
            payload = None
        except exceptions.UnboundPortError:            
            payload = None
        return Item(schema, payload)

    def __len__(self):
        return len(self._schemas)