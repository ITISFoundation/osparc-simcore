import collections
import logging

from . import config, exceptions

log = logging.getLogger(__name__)

_SchemaItem = collections.namedtuple("_SchemaItem", config.SCHEMA_ITEM_KEYS.keys())

class SchemaItem(_SchemaItem):
    def __new__(cls, **kwargs):
        new_kargs = dict.fromkeys(config.SCHEMA_ITEM_KEYS.keys())
        for key, required in config.SCHEMA_ITEM_KEYS.items():
            if key not in kwargs:
                if required:
                    raise exceptions.InvalidProtocolError(kwargs, "key \"%s\" is missing" % (str(key)))
                # new_kargs[key] = None
            else:
                new_kargs[key] = kwargs[key]

        log.debug("Creating new schema item with %s", new_kargs)
        self = super(SchemaItem, cls).__new__(cls, **new_kargs)
        return self
