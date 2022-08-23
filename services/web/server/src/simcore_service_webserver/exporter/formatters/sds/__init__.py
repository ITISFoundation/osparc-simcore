from pathlib import Path

from .text_files import write_text_files
from .xlsx import write_xlsx_files
from .xlsx.templates.code_description import CodeDescriptionParams
from .xlsx.templates.dataset_description import DatasetDescriptionParams
from .xlsx.templates.submission import SubmissionDocumentParams


def write_sds_directory_content(
    base_path: Path,
    submission_params: SubmissionDocumentParams,
    dataset_description_params: DatasetDescriptionParams,
    code_description_params: CodeDescriptionParams,
) -> None:
    write_text_files(base_path=base_path)
    write_xlsx_files(
        base_path=base_path,
        submission_params=submission_params,
        dataset_description_params=dataset_description_params,
        code_description_params=code_description_params,
    )


__all__ = ["write_sds_directory_content"]
