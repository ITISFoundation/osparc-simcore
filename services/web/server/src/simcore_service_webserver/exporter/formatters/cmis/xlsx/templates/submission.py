from typing import List, Tuple, Dict
from simcore_service_webserver.exporter.formatters.cmis.xlsx.xlsx_base import (
    BaseXLSXCellData,
    BaseXLSXSheet,
    BaseXLSXDocument,
)
from simcore_service_webserver.exporter.formatters.cmis.xlsx.styling_components import (
    T,
    TB,
    Backgrounds,
    Borders,
)


class SheetFirstSubmission(BaseXLSXSheet):
    name = "Sheet1"
    cell_styles = [
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
        self, **template_data_entires
    ) -> List[Tuple[str, Dict[str, BaseXLSXCellData]]]:
        award_number = template_data_entires["award_number"]
        milestone_archived = template_data_entires["milestone_archived"]
        milestone_completion_date = template_data_entires["milestone_completion_date"]
        return [
            ("C2", T(award_number)),
            ("C3", T(milestone_archived)),
            ("C4", T(milestone_completion_date)),
        ]


class SubmissionXLSXDocument(BaseXLSXDocument):
    file_name = "submission.xlsx"
    sheet1 = SheetFirstSubmission()
