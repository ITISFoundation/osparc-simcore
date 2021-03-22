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


def write_xlsx_files(base_path: Path) -> None:
    # TODO: all the params should be provided to this function as arguments
    # submission
    # TODO: move all this examples to an integration test folder
    submission_params = SubmissionDocumentParams(
        award_number="182y3187236871263",
        milestone_archived="182y3812y38",
        milestone_completion_date="some date here",
    )
    submission_xlsx = SubmissionXLSXDocument()
    submission_xlsx.save_document(base_path=base_path, template_data=submission_params)

    # dataset description
    # TODO: inject more fields and move this to a test
    dataset_description_params = DatasetDescriptionParams(
        name="some study", description="more about this study"
    )
    dataset_description_xlsx = DatasetDescriptionXLSXDocument()
    dataset_description_xlsx.save_document(
        base_path=base_path, template_data=dataset_description_params
    )

    # code description
    # TODO: inject more fields and move this to a test
    dataset_description_params = CodeDescriptionParams(**{"code_description": {}})

    code_description_xlsx = CodeDescriptionXLSXDocument()
    code_description_xlsx.save_document(
        base_path=base_path, template_data=dataset_description_params
    )
