import asyncio
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from collections import deque

from aiohttp import web

from simcore_service_webserver.exporter.formatters.formatter_v1 import FormatterV1
from simcore_service_webserver.exporter.formatters.base_formatter import BaseFormatter
from simcore_service_webserver.exporter.formatters.sds.sds import (
    write_sds_directory_content,
)

from simcore_service_webserver.exporter.formatters.sds.xlsx.templates.submission import (
    SubmissionDocumentParams,
)
from simcore_service_webserver.exporter.formatters.sds.xlsx.templates.dataset_description import (
    DatasetDescriptionParams,
)

from simcore_service_webserver.exporter.formatters.sds.xlsx.templates.code_description import (
    CodeDescriptionParams,
    CodeDescriptionModel,
    RRIDEntry,
    InputsEntryModel,
    OutputsEntryModel,
)

from ..exceptions import ExporterException
from simcore_service_webserver.projects.projects_exceptions import ProjectsException
from simcore_service_webserver.projects.projects_api import get_project_for_user
from simcore_service_webserver.catalog_client import get_service


log = logging.getLogger(__name__ + "[SDS]")


async def _write_sds_content(
    base_path: Path,
    app: web.Application,
    project_id: str,
    user_id: int,
    product_name: str,
) -> None:
    try:
        project_data = await get_project_for_user(
            app=app,
            project_uuid=project_id,
            user_id=user_id,
            include_templates=True,
            include_state=True,
        )
    except ProjectsException as e:
        raise ExporterException(f"Could not find project {project_id}") from e

    log.debug("Project data: %s", project_data)

    # assemble params here
    submission_params = SubmissionDocumentParams()
    dataset_description_params = DatasetDescriptionParams(
        name=project_data["name"], description=project_data["description"]
    )

    params_code_description = {}

    # Classifiers
    # TODO: continue with this
    RRIDEntry()

    # adding TSR data
    quality_data = project_data["quality"]
    if quality_data.get("enabled", False):
        tsr_data = quality_data["tsr_current"]
        for i in range(1, 11):
            tsr_entry_key = "r%.02d" % i
            tsr_entry = tsr_data[tsr_entry_key]

            rating_store_key = f"tsr{i}_rating" if i != 10 else f"tsr{i}a_rating"
            reference_store_key = (
                f"tsr{i}_reference" if i != 10 else f"tsr{i}a_reference"
            )

            params_code_description[rating_store_key] = tsr_entry["level"]
            params_code_description[reference_store_key] = tsr_entry["references"]

    workbench = project_data["workbench"]

    inputs = deque()
    outputs = deque()

    for entry in workbench.values():
        service_key = entry["key"]
        service_version = entry["version"]
        # TODO: add this filed to the format
        # label = entry["label"] a field for this will come later

        service_data = await get_service(
            app=app,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
            product_name=product_name,
        )
        log.error("Have data to use for compiling inputs and outputs %s", service_data)

        service_data_inputs = service_data["inputs"]

        for service_input in service_data_inputs.values():
            input_entry = InputsEntryModel(
                service_name=service_data["name"],
                service_version=service_data["version"],
                input_name=service_input["label"],
                # not present on the service
                input_data_ontology_identifier="",
                input_data_type=service_input["type"],
                # this is optional
                input_data_units=service_input.get("unit", ""),
                # not always available
                input_data_default_value=str(service_input.get("defaultValue", "")),
            )
            inputs.append(input_entry)

        service_data_outputs = service_data["outputs"]
        for service_output in service_data_outputs.values():
            output_entry = OutputsEntryModel(
                service_name=service_data["name"],
                service_version=service_data["version"],
                output_name=service_output["label"],
                # not present on the service
                output_data_ontology_identifier="",
                output_data_type=service_output["type"],
                # this is optional
                output_data_units=service_output.get("unit", ""),
            )
            outputs.append(output_entry)

    code_description = CodeDescriptionModel(**params_code_description)
    code_description_params = CodeDescriptionParams(
        code_description=code_description, inputs=list(inputs), outputs=list(outputs)
    )

    # writing SDS structure with process pool to avoid blocking
    with ProcessPoolExecutor(max_workers=1) as pool:
        return await asyncio.get_event_loop().run_in_executor(
            pool,
            write_sds_directory_content,
            base_path,
            submission_params,
            dataset_description_params,
            code_description_params,
        )


class FormatterV2(BaseFormatter):
    """Formates into the SDS format"""

    def __init__(self, root_folder: Path):
        super().__init__(version="2", root_folder=root_folder)

    @property
    def code_folder(self) -> Path:
        return self.root_folder / "code"

    async def format_export_directory(self, **kwargs) -> None:
        kwargs["manifest_root_folder"] = self.root_folder

        self.code_folder.mkdir(parents=True, exist_ok=True)
        formatter_v1 = FormatterV1(root_folder=self.code_folder, version=self.version)

        # generate structure for directory
        await formatter_v1.format_export_directory(**kwargs)
        # extract data to pass to the rest

        app: web.Application = kwargs["app"]
        project_id: str = kwargs["project_id"]
        user_id: int = kwargs["user_id"]
        product_name: str = kwargs["product_name"]

        await _write_sds_content(
            base_path=self.root_folder,
            app=app,
            project_id=project_id,
            user_id=user_id,
            product_name=product_name,
        )

        # continue filling up everuthing here

    async def validate_and_import_directory(self, **kwargs) -> str:
        kwargs["manifest_root_folder"] = self.root_folder

        formatter_v1 = FormatterV1(root_folder=self.code_folder, version=self.version)
        imported_project_uuid = await formatter_v1.validate_and_import_directory(
            **kwargs
        )
        # no ulterior action is required
        return imported_project_uuid
