"""This module contains an item representing a node port"""

import collections
import logging

from . import config, exceptions

log = logging.getLogger(__name__)

_DataItem = collections.namedtuple("_DataItem", config.DATA_ITEM_KEYS.keys())

class DataItem(_DataItem):
    """Encapsulates a Data Item and provides accessors functions

    """
    def __new__(cls, **kwargs):
        new_kargs = dict.fromkeys(config.DATA_ITEM_KEYS.keys())
        for key, required in config.DATA_ITEM_KEYS.items():
            if key not in kwargs:
                if required:
                    raise exceptions.InvalidProtocolError(kwargs, "key \"%s\" is missing" % (str(key)))
                new_kargs[key] = None
            else:
                new_kargs[key] = kwargs[key]

        log.debug("Creating new data item with %s", new_kargs)
        self = super(DataItem, cls).__new__(cls, **new_kargs)
        return self

    def __init__(self, **_kwargs):
        super(DataItem, self).__init__()
