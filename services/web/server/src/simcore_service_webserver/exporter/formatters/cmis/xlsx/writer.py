from pathlib import Path

from pydantic import BaseModel, Field, StrictStr

from simcore_service_webserver.exporter.formatters.cmis.xlsx.templates.submission import (
    SubmissionXLSXDocument,
)
from simcore_service_webserver.exporter.formatters.cmis.xlsx.templates.dataset_description import (
    DatasetDescriptionXLSXDocument,
)


class SubmissionDocumentParams(BaseModel):
    award_number: StrictStr = Field(
        ..., description="Grant number supporting the milestone"
    )
    milestone_archived: StrictStr = Field(
        ..., description="From milestones supplied to NIH"
    )
    milestone_completion_date: StrictStr = Field(
        ...,
        description=(
            "Date of milestone completion. This date starts the countdown for submission "
            "(30 days after completion), length of embargo and publication date (12 "
            "months from completion of milestone)"
        ),
    )


def write_xlsx_files(base_path: Path) -> None:
    submission_params = SubmissionDocumentParams(
        award_number="182y3187236871263",
        milestone_archived="182y3812y38",
        milestone_completion_date="some date here",
    )

    submission_xlsx = SubmissionXLSXDocument()
    submission_xlsx.save_document(base_path=base_path, **submission_params.dict())

    dataset_description_params = {}

    dataset_description_xlsx = DatasetDescriptionXLSXDocument()
    dataset_description_xlsx.save_document(
        base_path=base_path, **dataset_description_params
    )
