import datetime

from pydantic import BaseModel, Field, StrictStr, validator

from .core.styling_components import TB, Backgrounds, Borders, T
from .core.xlsx_base import BaseXLSXCellData, BaseXLSXDocument, BaseXLSXSheet
from .utils import ensure_correct_instance


class SubmissionDocumentParams(BaseModel):
    award_number: StrictStr = Field(
        "", description="Grant number supporting the milestone"
    )
    milestone_archived: StrictStr = Field(
        "", description="From milestones supplied to NIH"
    )
    milestone_completion_date: datetime.datetime | None = Field(
        None,
        description=(
            "Date of milestone completion. This date starts the countdown for submission "
            "(30 days after completion), length of embargo and publication date (12 "
            "months from completion of milestone)"
        ),
    )

    @validator("milestone_completion_date")
    @classmethod
    def format_milestone_completion_date(cls, v):
        if v is None:
            return ""
        return v.strftime("%d/%m/%Y")


class SheetFirstSubmission(BaseXLSXSheet):
    name = "Sheet1"
    cell_styles: list[tuple[str, BaseXLSXCellData]] = [
        ("A1", TB("Submission Item")),
        ("B1", TB("Definition")),
        ("C1", TB("Value")),
        ("A2", TB("SPARC Award number")),
        ("B2", T("Grant number supporting the milestone")),
        ("A3", TB("Milestone achieved")),
        ("B3", T("From milestones supplied to NIH")),
        ("A4", TB("Milestone completion date")),
        (
            "B4",
            T(
                "Date of milestone completion. This date starts the countdown for submission (30 days after completion), length of embargo and publication date (12 months from completion of milestone)"
            ),
        ),
        ("A1:C1", Backgrounds.blue),
        ("A1:C4", Borders.light_grid),
    ]
    column_dimensions = {"A": 30, "B": 40, "C": 40}

    def assemble_data_for_template(
        self, template_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        params: SubmissionDocumentParams = ensure_correct_instance(
            template_data, SubmissionDocumentParams
        )

        return [
            ("C2", T(params.award_number)),
            ("C3", T(params.milestone_archived)),
            ("C4", T(f"{params.milestone_completion_date}")),
        ]


class SubmissionXLSXDocument(BaseXLSXDocument):
    file_name = "submission.xlsx"
    sheet1 = SheetFirstSubmission()
