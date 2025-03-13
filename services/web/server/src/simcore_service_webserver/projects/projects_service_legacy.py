import warnings

from ._projects_repository_legacy import ProjectDBAPI, setup_projects_db
from ._projects_service_utils import (
    clone_project_document,
    substitute_parameterized_inputs,
)

warnings.warn(
    "The 'projects_service_legacy' module is deprecated. Please use the 'projects_service' module instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__: tuple[str, ...] = (
    "ProjectDBAPI",
    "clone_project_document",
    "setup_projects_db",
    "substitute_parameterized_inputs",
)

# nopycln: file
