# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from models_library.projects import NodesDict
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from pydantic import BaseModel
from simcore_service_webserver._meta import API_VTAG as VX
from simcore_service_webserver.projects.project_models import ProjectDict
from simcore_service_webserver.version_control.db import compute_workbench_checksum
from simcore_service_webserver.version_control.plugin import _rest_handlers


@pytest.mark.parametrize(
    "route",
    _rest_handlers.routes,
    ids=lambda r: f"{r.method.upper()} {r.path}",
)
def test_route_against_openapi_specs(route, openapi_specs: OpenApiSpecs):

    assert route.path.startswith(f"/{VX}")
    path = route.path.replace(f"/{VX}", "")

    assert (
        route.method.lower() in openapi_specs.paths[path].operations
    ), f"operation {route.method} undefined in OAS"

    assert (
        openapi_specs.paths[path].operations[route.method.lower()].operation_id
        == route.kwargs["name"]
    ), "route's name differs from OAS operation_id"


class WorkbenchModel(BaseModel):
    __root__: NodesDict

    class Config:
        allow_population_by_field_name = True


def test_compute_workbench_checksum(fake_project: ProjectDict):

    # as a dict
    sha1_w_dict = compute_workbench_checksum(fake_project["workbench"])

    workbench = WorkbenchModel.parse_obj(fake_project["workbench"])

    # with pydantic models, i.e. Nodes
    #
    #  e.g. order after parse maps order in BaseModel but not in dict
    #
    sha1_w_model = compute_workbench_checksum(workbench.__root__)

    assert sha1_w_model == sha1_w_dict
