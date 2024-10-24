"""
    Helper functions to convert models used in
    services/api-server/src/simcore_service_api_server/api/routes/studies_jobs.py
"""
from typing import Any, NamedTuple
from uuid import UUID

from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.api_schemas_webserver.projects_ports import (
    ProjectInputGet,
    ProjectInputUpdate,
)
from models_library.projects import DateTimeStr
from models_library.projects_nodes import InputID
from models_library.projects_nodes_io import LinkToFileTypes, NodeID, SimcoreS3FileID
from pydantic import TypeAdapter

from ..models.domain.projects import InputTypes, SimCoreFileLink
from ..models.schemas.files import File
from ..models.schemas.jobs import Job, JobInputs, JobOutputs
from ..models.schemas.studies import Study, StudyID
from .storage import StorageApi, to_file_api_model


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


async def create_job_outputs_from_project_outputs(
    job_id: StudyID,
    project_outputs: dict[NodeID, dict[str, Any]],
    user_id,
    storage_client: StorageApi,
) -> JobOutputs:
    """

    Raises:
        ValidationError: when on invalid project_outputs

    """
    results: dict[str, Any] = {}

    for node_dict in project_outputs.values():
        name = node_dict["label"]
        value = node_dict["value"]

        if (
            value
            and isinstance(value, dict)
            and {"store", "path"}.issubset(value.keys())
        ):
            assert (  # nosec
                TypeAdapter(LinkToFileTypes).validate_python(value) is not None
            )

            path = value["path"]
            file_id: UUID = File.create_id(*path.split("/"))

            if found := await storage_client.search_owned_files(
                user_id=user_id,
                file_id=file_id,
                sha256_checksum=None,
            ):
                assert len(found) == 1  # nosec
                results[name] = to_file_api_model(found[0])
            else:
                api_file: File = await storage_client.create_soft_link(
                    user_id=user_id, target_s3_path=path, as_file_id=file_id
                )
                results[name] = api_file
        else:
            results[name] = value

    return JobOutputs(job_id=job_id, results=results)
