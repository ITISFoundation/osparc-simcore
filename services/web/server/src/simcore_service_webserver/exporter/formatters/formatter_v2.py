import asyncio
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

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
)

logger = logging.getLogger(__name__)


async def _write_sds_content(
    base_path: Path, app: web.Application, project_id: str, user_id: int
) -> None:
    # assemble params here
    submission_params = SubmissionDocumentParams(
        award_number="_TODO_REPLACE_ME",
        milestone_archived="_TODO_REPLACE_ME",
        milestone_completion_date="_TODO_REPLACE_ME",
    )
    dataset_description_params = DatasetDescriptionParams(
        name="_TODO_REPLACE_ME", description="_TODO_REPLACE_ME"
    )
    code_description = CodeDescriptionModel()
    code_description_params = CodeDescriptionParams(code_description=code_description)

    # writing with process pool
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

        await _write_sds_content(
            base_path=self.root_folder, app=app, project_id=project_id, user_id=user_id
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
