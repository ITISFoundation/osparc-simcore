"""
    Helper functions to convert models used in
    services/api-server/src/simcore_service_api_server/api/routes/studies_jobs.py
"""
import collections.abc
from uuid import UUID

import pydantic
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.generics import Envelope
from models_library.projects_nodes import InputID, NodeID

from ..models.domain.projects import InputTypes, SimCoreFileLink
from ..models.schemas.files import File
from ..models.schemas.jobs import ArgumentTypes, Job, JobInputs, JobOutputs
from ..models.schemas.studies import Study, StudyID
from .storage import to_file_api_model


def get_project_and_file_inputs_from_job_inputs(
    project_inputs: dict[NodeID, dict[str, pydantic.typing.Any]],
    file_inputs: dict[InputID, InputTypes],
    job_inputs: JobInputs,
) -> Envelope[dict[NodeID, str]]:
    job_inputs_dict = job_inputs.values

    # TODO make sure all values are set at some point

    for name, value in job_inputs.values.items():
        if isinstance(value, File):
            # FIXME: ensure this aligns with storage policy
            file_inputs[name] = SimCoreFileLink(
                store=0,
                path=f"api/{value.id}/{value.filename}",
                label=value.filename,
                eTag=value.e_tag,
            )

    new_inputs = []
    for node_id, node_dict in project_inputs.items():
        if node_dict["label"] in job_inputs_dict:
            new_inputs.append(
                {"key": node_id, "value": job_inputs_dict[node_dict["label"]]}
            )

    return new_inputs, file_inputs


async def create_job_outputs_from_project_outputs(
    job_id: StudyID,
    project_outputs: dict[NodeID, dict[str, pydantic.typing.Any]],
    user_id,
    storage_client,
) -> JobOutputs:
    results: dict[str, ArgumentTypes] = {}

    for _, node_dict in project_outputs.items():
        name = node_dict["label"]
        value = node_dict["value"]
        if (
            value and isinstance(value, collections.abc.Mapping) and "store" in value
        ):  # TODO make this more robust
            path = value["path"]
            file_id: UUID = File.create_id(*path.split("/"))

            found = await storage_client.search_files(
                user_id=user_id,
                file_id=file_id,
                sha256_checksum=None,
                access_right="read",
            )
            if found:
                assert len(found) == 1  # nosec
                results[name] = to_file_api_model(found[0])
            else:
                api_file: File = await storage_client.create_soft_link(
                    user_id, path, file_id
                )
                results[name] = api_file
        else:
            results[name] = value
    job_outputs = JobOutputs(job_id=job_id, results=results)
    return job_outputs


def create_job_from_study(
    study_key: StudyID,
    project: ProjectGet,
    job_inputs: JobInputs,
) -> Job:
    """
    Given a study, creates a job

    raise ValidationError
    """

    study_name = f"{study_key}"  # TODO do we use the study name here?
    study_name = Study.compose_resource_name(study_key)

    job_name = Job.compose_resource_name(parent_name=study_name, job_id=project.uuid)

    new_job = Job(
        id=project.uuid,
        name=job_name,
        inputs_checksum=job_inputs.compute_checksum(),
        created_at=project.creation_date,
        runner_name=study_name,
        url="https://itis.swiss",
        runner_url="https://itis.swiss",
        outputs_url="https://itis.swiss",
    )

    return new_job
