# itag: iteration tag
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Iterator
from uuid import UUID

from models_library.frontend_services_catalog import (
    _create_data_iterator_int_range,
    is_iterator_consumer_service,
    is_iterator_service,
)
from models_library.services import ServiceDockerData, ServiceInputs
from pydantic import create_model
from pydantic.types import PositiveInt

# /projects/{project_uuid}/workbench:start

# pre-process
#   - any meta nodes?
#      - no
#           - then forward to director_v2_handlers.start_pipeline TODO: adapt so it is callable
#      - yes
#           - create replicas and commit
#           - convert every commit in a project
#           - launch these projects -> start_pipeline
#

# /projects/{project_uuid}/workbench:stop

# meta project (uuid) -> concrete projects  (uuid,tagid)


# these services have a backend implementation

# convert ServiceDockerData into functions??
#
def _linspace(
    linspace_start: int = 0, linspace_stop: int = 1, linspace_step: int = 1
) -> Iterator[int]:
    # TODO: horrible argument names

    for value in range(linspace_start, linspace_stop, linspace_step):
        yield value


#######################

PROPTYPE_2_PYTYPE = {"number": float, "boolean": bool, "integer": int, "string": str}
PYTYPE_2_PROPTYPE = {v: k for k, v in PROPTYPE_2_PYTYPE}


def to_pydantic_model(service_inputs: ServiceInputs):
    # input_defs to pydantic model, then they can be parsed

    for name, input_def in service_inputs.items():
        input_def.property_type
        input_def.default_value
        input_def.description
