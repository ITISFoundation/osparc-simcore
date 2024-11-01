# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.projects import NodesDict
from pydantic import ConfigDict, RootModel
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.version_control.db import compute_workbench_checksum


class WorkbenchModel(RootModel[NodesDict]):
    model_config = ConfigDict(populate_by_name=True)


def test_compute_workbench_checksum(fake_project: ProjectDict):

    # as a dict
    sha1_w_dict = compute_workbench_checksum(fake_project["workbench"])

    workbench = WorkbenchModel.model_validate(fake_project["workbench"])

    # with pydantic models, i.e. Nodes
    #
    #  e.g. order after parse maps order in BaseModel but not in dict
    #
    sha1_w_model = compute_workbench_checksum(workbench.root)

    assert sha1_w_model == sha1_w_dict
