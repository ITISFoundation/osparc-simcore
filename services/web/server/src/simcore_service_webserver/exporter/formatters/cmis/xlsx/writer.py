from pathlib import Path

from simcore_service_webserver.exporter.formatters.cmis.xlsx.templates.submission import (
    SubmissionXLSXDocument,
)


def write_xlsx_files(base_path: Path) -> None:
    submission_params = dict(
        award_number="182y3187236871263",
        milestone_archived="182y3812y38",
        milestone_completion_date="adssadsd",
    )

    document = SubmissionXLSXDocument()
