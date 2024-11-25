import asyncio
import logging
from collections import deque
from pathlib import Path
from typing import Any, Final

from aiohttp import web
from servicelib.pools import non_blocking_process_pool_executor

from ...catalog.client import get_service
from ...projects.exceptions import BaseProjectError
from ...projects.models import ProjectDict
from ...projects.projects_api import get_project_for_user
from ...scicrunch.db import ResearchResourceRepository
from ..exceptions import SDSException
from .template_json import write_template_json
from .xlsx.code_description import (
    CodeDescriptionModel,
    CodeDescriptionParams,
    InputsEntryModel,
    OutputsEntryModel,
    RRIDEntry,
)
from .xlsx.dataset_description import DatasetDescriptionParams
from .xlsx.writer import write_xlsx_files

_logger = logging.getLogger(__name__)

_ORIGINAL_TSR_KEYS: Final[set[str]] = {
    "r01",
    "r02",
    "r03",
    "r04",
    "r05",
    "r06",
    "r07",
    "r08",
    "r09",
    "r10",
}
_ONLY_REFERENCE_TSR_KEYS: Final[set[str]] = {
    "r03b",
    "r03c",
    "r07b",
    "r07c",
    "r07d",
    "r07e",
    "r08b",
    "r10b",
}
_EXPECTED_TSR_KEYS: Final[set[str]] = _ORIGINAL_TSR_KEYS | _ONLY_REFERENCE_TSR_KEYS


def _write_sds_directory_content(
    base_path: Path,
    dataset_description_params: DatasetDescriptionParams,
    code_description_params: CodeDescriptionParams,
) -> None:
    write_xlsx_files(
        base_path=base_path,
        dataset_description_params=dataset_description_params,
        code_description_params=code_description_params,
    )


async def _add_rrid_entries(
    app: web.Application,
    project_data: ProjectDict,
    params_code_description: dict[str, Any],
) -> None:
    rrid_entires: deque[RRIDEntry] = deque()

    repo = ResearchResourceRepository(app)
    classifiers = project_data["classifiers"]
    for classifier in classifiers:
        scicrunch_resource = await repo.get(rrid=classifier)
        if scicrunch_resource is None:
            continue

        rrid_entires.append(
            RRIDEntry.model_validate(
                {
                    "rrid_term": scicrunch_resource.name,
                    "rrid_identifier": scicrunch_resource.rrid,
                },
            )
        )
    params_code_description["rrid_entires"] = list(rrid_entires)


def _add_tsr_entries(
    project_data: ProjectDict, params_code_description: dict[str, Any]
) -> None:
    # adding TSR data
    quality_data = project_data["quality"]
    if quality_data.get("enabled", False):
        # check if the TSR data is in the expected format
        # otherwise ask the user to save it once more
        tsr_target: dict[str, Any] = quality_data.get("tsr_target", {})
        tsr_current = quality_data.get("tsr_current", {})
        tsr_target_keys = set(tsr_target.keys())
        tsr_current_keys = set(tsr_current.keys())

        tsr_entries: dict[str, Any] = {}

        if tsr_target_keys == tsr_current_keys == _EXPECTED_TSR_KEYS:
            # since the data is in the expected format, extract it
            for key in _ORIGINAL_TSR_KEYS:
                if key not in tsr_entries:
                    tsr_entries[key] = {}

                target_level: int = tsr_target.get(key, {}).get("level", 4)
                current_level: int = tsr_current.get(key, {}).get("level", 0)
                tsr_entries[key]["target_level"] = target_level
                tsr_entries[key]["current_level"] = current_level

            for key in _EXPECTED_TSR_KEYS:
                if key not in tsr_entries:
                    tsr_entries[key] = {}

                references = tsr_current.get(key, {}).get("references", "")
                tsr_entries[key]["references"] = references.split("\n")

            params_code_description["tsr_entries"] = tsr_entries
        else:
            # User might have a deprecated version here, asking to regenerate the TSR.
            # This should make it exportable once again after the format is saved.
            msg = (
                "Current TSR data format is too old. Please `Edit` and `Save` it again."
            )
            _logger.warning("%s Stored data: %s", msg, quality_data)
            raise SDSException(msg)
    else:
        msg = "TSR is disabled, please enable it and try to export again"
        raise SDSException(msg)


async def create_sds_directory(
    app: web.Application,
    base_path: Path,
    project_id: str,
    user_id: int,
    product_name: str,
) -> None:
    try:
        project_data: ProjectDict = await get_project_for_user(
            app=app,
            project_uuid=project_id,
            user_id=user_id,
            include_state=True,
        )
    except BaseProjectError as e:
        msg = f"Could not find project {project_id}"
        raise SDSException(msg) from e

    _logger.debug("Project data: %s", project_data)

    # assemble params here
    dataset_description_params = DatasetDescriptionParams.model_validate(
        {
            "name": project_data["name"],
            "description": (
                ""
                if project_data["description"] is None
                else project_data["description"]
            ),
        },
    )

    params_code_description: dict[str, Any] = {}

    await _add_rrid_entries(app, project_data, params_code_description)

    _add_tsr_entries(project_data, params_code_description)

    workbench = project_data["workbench"]

    inputs: deque[InputsEntryModel] = deque()
    outputs: deque[OutputsEntryModel] = deque()

    for entry in workbench.values():
        service_key = entry["key"]
        service_version = entry["version"]
        label = entry["label"]

        service_data = await get_service(
            app=app,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
            product_name=product_name,
        )

        service_data_inputs = service_data["inputs"]
        for service_input in service_data_inputs.values():
            input_entry = InputsEntryModel(
                service_alias=label,
                service_name=service_data["name"],
                service_key=service_data["key"],
                service_version=service_data["version"],
                input_name=service_input["label"],
                input_parameter_description=service_data.get("description", ""),
                # not present on the service
                input_data_type=service_input["type"],
                # this is optional
                input_data_units=service_input.get("unit", ""),
                # not always available
                input_data_default_value=str(service_input.get("defaultValue", "")),
                # NOTE: currently not available in the backend
                input_data_constraints="",
            )
            inputs.append(input_entry)

        service_data_outputs = service_data["outputs"]
        for service_output in service_data_outputs.values():
            output_entry = OutputsEntryModel(
                service_alias=label,
                service_name=service_data["name"],
                service_key=service_data["key"],
                service_version=service_data["version"],
                output_name=service_output["label"],
                output_parameter_description=service_data.get("description", ""),
                # not present on the service
                output_data_ontology_identifier="",
                output_data_type=service_output["type"],
                # this is optional
                output_data_units=service_output.get("unit", ""),
                # NOTE: currently not available in the backend
                output_data_constraints="",
            )
            outputs.append(output_entry)

    code_description = CodeDescriptionModel(**params_code_description)
    code_description_params = CodeDescriptionParams(
        code_description=code_description, inputs=list(inputs), outputs=list(outputs)
    )

    await write_template_json(target_dir=base_path, project_data=project_data)

    # writing SDS structure with process pool to avoid blocking
    with non_blocking_process_pool_executor(max_workers=1) as pool:
        return await asyncio.get_event_loop().run_in_executor(
            pool,
            _write_sds_directory_content,
            base_path,
            dataset_description_params,
            code_description_params,
        )
