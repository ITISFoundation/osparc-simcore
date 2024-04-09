"""
    Helper functions to convert models used in
    services/api-server/src/simcore_service_api_server/api/routes/studies_jobs.py
"""
from typing import NamedTuple

from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.api_schemas_webserver.projects_ports import (
    ProjectInputGet,
    ProjectInputUpdate,
)
from models_library.projects import DateTimeStr
from models_library.projects_nodes import InputID, NodeID
from models_library.projects_nodes_io import SimcoreS3FileID

from ..models.domain.projects import InputTypes, SimCoreFileLink
from ..models.schemas.files import File
from ..models.schemas.jobs import Job, JobInputs
from ..models.schemas.studies import Study, StudyID


class ProjectInputs(NamedTuple):
    inputs: list[ProjectInputUpdate]
    file_inputs: dict[InputID, InputTypes]


def get_project_and_file_inputs_from_job_inputs(
    project_inputs: dict[NodeID, ProjectInputGet],
    file_inputs: dict[InputID, InputTypes],
    job_inputs: JobInputs,
) -> ProjectInputs:
    job_inputs_dict = job_inputs.values

    # TODO make sure all values are set at some point

    for name, value in job_inputs.values.items():
        if isinstance(value, File):
            # FIXME: ensure this aligns with storage policy
            file_inputs[InputID(name)] = SimCoreFileLink(
                store=0,
                path=SimcoreS3FileID(f"api/{value.id}/{value.filename}"),
                label=value.filename,
                eTag=value.e_tag,
            )

    new_inputs: list[ProjectInputUpdate] = []
    for node_id, node_dict in project_inputs.items():
        if node_dict.label in job_inputs_dict:
            new_inputs.append(
                ProjectInputUpdate(key=node_id, value=job_inputs_dict[node_dict.label])
            )

    return ProjectInputs(new_inputs, file_inputs)


def create_job_from_study(
    study_key: StudyID,
    project: ProjectGet,
    job_inputs: JobInputs,
) -> Job:
    """
    Given a study, creates a job

    raise ValidationError
    """

    study_name = Study.compose_resource_name(f"{study_key}")

    job_name = Job.compose_resource_name(parent_name=study_name, job_id=project.uuid)

    return Job(
        id=project.uuid,
        name=job_name,
        inputs_checksum=job_inputs.compute_checksum(),
        created_at=DateTimeStr.to_datetime(project.creation_date),
        runner_name=study_name,
        url=None,
        runner_url=None,
        outputs_url=None,
    )
