import logging
import os
from collections import OrderedDict

import yaml

logger = logging.getLogger(__name__)

# SEE https://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts


def ordered_safe_load(stream, object_pairs_hook=OrderedDict):
    # pylint: disable=too-many-ancestors
    class OrderedLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))

    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
    )
    return yaml.load(stream, OrderedLoader)  # nosec


def ordered_safe_dump(data, stream=None, **kwds):
    # pylint: disable=too-many-ancestors
    class OrderedDumper(yaml.SafeDumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, data.items()
        )

    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)


# pylint: disable=too-many-ancestors
class _LoaderWithInclude(yaml.SafeLoader):
    # Taken from https://stackoverflow.com/questions/528281/how-can-i-include-a-yaml-file-inside-another

    def __init__(self, stream):
        try:
            self._basepath = os.path.split(stream.name)[0]
        except AttributeError:
            self._basepath = os.getcwd()
            logger.warning(
                "Cannot deduce path to yaml file from a %s."
                "Defaulting to '%s' as base path for all !include nodes",
                type(stream),
                self._basepath,
            )

        super().__init__(stream)

    def include(self, node):
        fpath = os.path.join(self._basepath, f"{self.construct_scalar(node)}")
        with open(fpath, "r") as f:
            return yaml_safe_load(f)


_LoaderWithInclude.add_constructor("!include", _LoaderWithInclude.include)


def yaml_safe_load(stream):
    return yaml.load(stream, _LoaderWithInclude)  # nosec
