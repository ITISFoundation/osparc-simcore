from pathlib import Path


from simcore_service_webserver.exporter.formatters.cmis.xlsx.templates.submission import (
    SubmissionXLSXDocument,
    SubmissionDocumentParams,
)
from simcore_service_webserver.exporter.formatters.cmis.xlsx.templates.dataset_description import (
    DatasetDescriptionXLSXDocument,
    DatasetDescriptionParams,
)

from simcore_service_webserver.exporter.formatters.cmis.xlsx.templates.code_description import (
    CodeDescriptionXLSXDocument,
    CodeDescriptionParams,
)
from simcore_service_webserver.exporter.formatters.cmis.xlsx.templates.directory_manifest import (
    DirectoryManifestXLSXDocument,
    DirectoryManifestParams,
)


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

    # TODO: remove below after testing

    directory_manifest_params = DirectoryManifestParams.compose_from_directory(
        base_path
    )

    dirs_to_generate_manifests= []

    directory_manifest_xlsx = DirectoryManifestXLSXDocument()
    directory_manifest_xlsx.save_document(
        base_path=base_path, template_data=directory_manifest_params
    )
