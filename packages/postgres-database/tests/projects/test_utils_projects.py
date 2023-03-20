from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.projects import ProjectType
from simcore_postgres_database.utils_projects import can_guest_copy_project


def test_can_guest_copy_project(project: RowProxy):
    project_dict = dict(project.items())
    assert not project_dict["published"]

    assert not can_guest_copy_project(prj_data=project_dict)

    project_dict["type"] = f"{ProjectType.TEMPLATE}"
    project_dict["published"] = True

    assert can_guest_copy_project(prj_data=project_dict)
