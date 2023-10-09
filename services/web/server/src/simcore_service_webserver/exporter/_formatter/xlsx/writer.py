from pathlib import Path

from .code_description import CodeDescriptionParams, CodeDescriptionXLSXDocument
from .dataset_description import (
    DatasetDescriptionParams,
    DatasetDescriptionXLSXDocument,
)
from .manifest import ManifestXLSXDocument


def write_xlsx_files(
    base_path: Path,
    dataset_description_params: DatasetDescriptionParams,
    code_description_params: CodeDescriptionParams,
) -> None:
    dataset_description_xlsx = DatasetDescriptionXLSXDocument()
    dataset_description_xlsx.save_document(
        base_path=base_path, template_data=dataset_description_params
    )

    code_description_xlsx = CodeDescriptionXLSXDocument()
    code_description_xlsx.save_document(
        base_path=base_path, template_data=code_description_params
    )
    manifest_xlsx = ManifestXLSXDocument()
    manifest_xlsx.save_document(base_path=base_path, template_data=None)
