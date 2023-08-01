"""
    Factory to build catalog of i/o metadata for functions implemented in the front-end

    NOTE: These definitions are currently needed in the catalog and director2
    services. Since it is static data, instead of making a call from
    director2->catalog, it was decided to share as a library
"""

import logging

from ..function_services_catalog.services import nodes_group
from ._settings import FunctionServiceSettings
from ._utils import FunctionServices
from .services import (
    demo_units,
    file_picker,
    iter_range,
    iter_sensitivity,
    parameters,
    probes,
)

_logger = logging.getLogger(__name__)


catalog = FunctionServices(settings=FunctionServiceSettings())
catalog.extend(demo_units.services)
catalog.extend(file_picker.services)
catalog.extend(iter_range.services)
catalog.extend(iter_sensitivity.services)
catalog.extend(nodes_group.services)
catalog.extend(parameters.services)
catalog.extend(probes.services)
