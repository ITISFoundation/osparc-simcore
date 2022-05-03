from pathlib import Path

from .templates.code_description import (
    CodeDescriptionParams,
    CodeDescriptionXLSXDocument,
)
from .templates.dataset_description import (
    DatasetDescriptionParams,
    DatasetDescriptionXLSXDocument,
)
from .templates.directory_manifest import (
    DirectoryManifestParams,
    DirectoryManifestXLSXDocument,
)
from .templates.submission import SubmissionDocumentParams, SubmissionXLSXDocument

MANIFEST_DIRS = ["code", "docs", "derivative"]


def write_xlsx_files(
    base_path: Path,
    submission_params: SubmissionDocumentParams,
    dataset_description_params: DatasetDescriptionParams,
    code_description_params: CodeDescriptionParams,
) -> None:
    submission_xlsx = SubmissionXLSXDocument()
    submission_xlsx.save_document(base_path=base_path, template_data=submission_params)

    dataset_description_xlsx = DatasetDescriptionXLSXDocument()
    dataset_description_xlsx.save_document(
        base_path=base_path, template_data=dataset_description_params
    )

    code_description_xlsx = CodeDescriptionXLSXDocument()
    code_description_xlsx.save_document(
        base_path=base_path, template_data=code_description_params
    )

    # automatically generating file manifests
    generate_manifest_for = [base_path / x for x in MANIFEST_DIRS]
    for dir_path in generate_manifest_for:
        directory_manifest_params = DirectoryManifestParams.compose_from_directory(
            dir_path
        )
        directory_manifest_xlsx = DirectoryManifestXLSXDocument()
        directory_manifest_xlsx.save_document(
            base_path=dir_path, template_data=directory_manifest_params
        )
