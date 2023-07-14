# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.projects import NodesDict
from pydantic import BaseModel
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.version_control.db import compute_workbench_checksum


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
