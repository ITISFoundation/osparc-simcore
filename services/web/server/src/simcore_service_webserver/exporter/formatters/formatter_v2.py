import asyncio
import logging
from collections import deque
from pathlib import Path
from typing import Optional

from aiohttp import web
from aiopg.sa.engine import SAConnection
from aiopg.sa.result import ResultProxy, RowProxy
from servicelib.pools import non_blocking_process_pool_executor
from simcore_postgres_database.models.scicrunch_resources import scicrunch_resources

from ...catalog_client import get_service
from ...projects.projects_api import get_project_for_user
from ...projects.projects_exceptions import ProjectsException
from ...scicrunch.db import ResearchResourceRepository
from ..exceptions import ExporterException
from .base_formatter import BaseFormatter
from .formatter_v1 import FormatterV1
from .sds import write_sds_directory_content
from .sds.xlsx.templates.code_description import (
    CodeDescriptionModel,
    CodeDescriptionParams,
    InputsEntryModel,
    OutputsEntryModel,
    RRIDEntry,
)
from .sds.xlsx.templates.dataset_description import DatasetDescriptionParams
from .sds.xlsx.templates.submission import SubmissionDocumentParams

log = logging.getLogger(__name__)


async def _get_scicrunch_resource(rrid: str, conn: SAConnection) -> Optional[RowProxy]:
    res: ResultProxy = await conn.execute(
        scicrunch_resources.select().where(scicrunch_resources.c.rrid == rrid)
    )
    return await res.first()


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

    rrid_entires = deque()

    repo = ResearchResourceRepository(app)
    classifiers = project_data["classifiers"]
    for classifier in classifiers:
        scicrunch_resource = await repo.get(rrid=classifier)
        if scicrunch_resource is None:
            continue

        rrid_entires.append(
            RRIDEntry(
                rrid_term=scicrunch_resource.name,
                rrod_identifier=scicrunch_resource.rrid,
            )
        )
    params_code_description["rrid_entires"] = list(rrid_entires)

    # adding TSR data
    quality_data = project_data["quality"]
    if quality_data.get("enabled", False):
        # some projects may not have a "tsr_current" entry,
        #  because this field is enforced by the frontend
        tsr_data = quality_data.get("tsr_current", {})
        tsr_data_len = len(tsr_data)

        # make sure all 10 entries are present for a valid format
        if tsr_data_len == 10:
            for i in range(1, tsr_data_len + 1):
                tsr_entry_key = "r%.02d" % i
                tsr_entry = tsr_data[tsr_entry_key]

                rating_store_key = f"tsr{i}_rating" if i != 10 else f"tsr{i}a_rating"
                reference_store_key = (
                    f"tsr{i}_reference" if i != 10 else f"tsr{i}a_reference"
                )

                params_code_description[rating_store_key] = tsr_entry["level"]
                params_code_description[reference_store_key] = tsr_entry["references"]
        else:
            log.warning(
                "Skipping TSR entries, not all 10 entries were present: %s",
                quality_data,
            )

    workbench = project_data["workbench"]

    inputs = deque()
    outputs = deque()

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
                service_alias=label,
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
    with non_blocking_process_pool_executor(max_workers=1) as pool:
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

    async def format_export_directory(
        self, app: web.Application, project_id: str, user_id: int, **kwargs
    ) -> None:
        kwargs["manifest_root_folder"] = self.root_folder

        self.code_folder.mkdir(parents=True, exist_ok=True)
        formatter_v1 = FormatterV1(root_folder=self.code_folder, version=self.version)

        # generate structure for directory
        await formatter_v1.format_export_directory(
            app=app, project_id=project_id, user_id=user_id, **kwargs
        )
        # extract data to pass to the rest

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
