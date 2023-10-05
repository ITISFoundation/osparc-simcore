from abc import abstractmethod
from collections import deque
from typing import Any, ClassVar, Final, cast

from models_library.services import ServiceKey, ServiceVersion
from pydantic import BaseModel, Field, StrictStr

from .core.styling_components import TB, Backgrounds, Borders, Comment, Link, T
from .core.xlsx_base import BaseXLSXCellData, BaseXLSXDocument, BaseXLSXSheet
from .utils import column_generator, ensure_correct_instance


class RRIDEntry(BaseModel):
    rrid_term: StrictStr = Field(..., description="Associated tools or resources used")
    rrid_identifier: StrictStr = Field(
        ..., description="Associated tools or resources identifier (with 'RRID:')"
    )
    # the 2 items below are not enabled for now
    ontological_term: StrictStr = Field(
        "", description="Associated ontological term (human-readable)"
    )
    ontological_identifier: StrictStr = Field(
        "",
        description=(
            "Associated ontological identifier from SciCrunch https://scicrunch.org/sawg"
        ),
    )


class TSROnlYReferenceEntry(BaseModel):
    references: list[str]


class TSRFullEntry(TSROnlYReferenceEntry):
    target_level: int  # max value allowed
    current_level: int  # current selection


class CodeDescriptionModel(BaseModel):
    rrid_entires: list[RRIDEntry] = Field(
        default_factory=list, description="composed from the classifiers"
    )

    # TSR
    tsr_entries: dict[str, TSRFullEntry | TSROnlYReferenceEntry] = Field(
        default_factory=dict, description="list of rules to generate tsr"
    )


class InputsEntryModel(BaseModel):
    service_alias: StrictStr = Field(
        ..., description="Name of the service containing this input, given by the user"
    )
    service_name: StrictStr = Field(
        ..., description="Name of the service containing this input"
    )
    service_key: ServiceKey = Field(
        ..., description="Key of the service containing this input"
    )
    service_version: ServiceVersion = Field(
        ..., description="Version of the service containing this input"
    )
    input_name: StrictStr = Field(
        "", description="An input field to the MSoP submission"
    )
    input_parameter_description: StrictStr = Field(
        "", description="Description of what the parameter represents"
    )
    input_data_type: StrictStr = Field(
        "", description="Data type for the input field (in plain text)"
    )
    input_data_units: StrictStr = Field(
        "", description="Units of data for the input field, if applicable"
    )
    input_data_default_value: StrictStr = Field(
        "",
        description="Default value for the input field, if applicable (doi or value)",
    )
    input_data_constraints: StrictStr = Field(
        "",
        description="Range [min, max] of acceptable parameter values, or other constraints as formulas / sets",
    )


class OutputsEntryModel(BaseModel):
    service_alias: StrictStr = Field(
        ..., description="Name of the service producing this output, given by the user"
    )
    service_name: StrictStr = Field(
        ..., description="Name of the service containing this output"
    )
    service_key: ServiceKey = Field(
        ..., description="Key of the service containing this output"
    )
    service_version: ServiceVersion = Field(
        ..., description="Version of the service containing this output"
    )
    output_name: StrictStr = Field(
        "", description="An output field to the MSoP submission"
    )
    output_parameter_description: StrictStr = Field(
        "", description="Description of what the parameter represents"
    )
    output_data_ontology_identifier: StrictStr = Field(
        "",
        description=(
            "Ontology identifier for the input field, if applicable , "
            "https://scicrunch.org/scicrunch/interlex/search?q=NLXOEN&l=NLXOEN&types=term"
        ),
    )
    output_data_type: StrictStr = Field(
        "", description="Data type for the output field"
    )
    output_data_units: StrictStr = Field(
        "", description="Units of data for the output field, if applicable"
    )
    output_data_constraints: StrictStr = Field(
        "",
        description="Range [min, max] of acceptable parameter values, or other constraints as formulas / sets",
    )


class CodeDescriptionParams(BaseModel):
    code_description: CodeDescriptionModel = Field(
        ..., description="code description data"
    )
    inputs: list[InputsEntryModel] = Field(
        default_factory=list, description="List of inputs, if any"
    )
    outputs: list[OutputsEntryModel] = Field(
        default_factory=list, description="List of outputs, if any"
    )


class SheetCodeDescription(BaseXLSXSheet):
    name = "Code Description"
    cell_styles: ClassVar[list[tuple[str, BaseXLSXCellData]]] = [
        ## Header
        ("A1", TB("Metadata element")),
        ("B1", TB("Description")),
        ("C1", TB("Example")),
        ("A1:C1", Backgrounds.blue),
        ## Classifiers section
        ("A2", TB("RRID Term")),
        ("B2", T("Associated tools or resources used")),
        ("C2", T("ImageJ")),
        ("A3", TB("RRID Identifier")),
        ("B3", T("Associated tools or resources identifier (with 'RRID:')")),
        ("C3", T("RRID:SCR_003070")),
        ("A4", TB("Ontological term")),
        ("B4", T("Associated ontological term (human-readable)")),
        ("C4", T("Heart")),
        ("A5", TB("Ontological Identifier")),
        (
            "B5",
            Link(
                "Associated ontological identifier from SciCrunch",
                "https://scicrunch.org/sawg",
            ),
        ),
        ("C5", T("UBERON:0000948")),
        ("A2:C5", Backgrounds.green),
        # borders for headers section
        ("A5:C5", Borders.border_bottom_thick),
        ("B1:B5", Borders.border_left_light),
        ("B1:B5", Borders.border_right_light),
        ("A1:C5", Borders.light_grid),
        ## TSR section
        (
            "A6",
            Link(
                "Ten Simple Rules (TSR)",
                "https://www.imagwiki.nibib.nih.gov/content/10-simple-rules-conformance-rubric",
            ),
        ),
        (
            "B6",
            T(
                "The TSR is a communication tool for modelers to organize their model development process and present it coherently."
            ),
        ),
        ("C6", Link("Rating (0-4)", "#'TSR Rating Rubric'!A1")),
        ("A6:C6", Backgrounds.green),
        # TSR1
        ("A7", T("TSR1: Define Context Clearly Rating (0-4)")),
        (
            "B7",
            T(
                "Develop and document the subject, purpose and intended use(s) of model, simulation or data processing (MSoP) submission"
            ),
        ),
        ("C7", T(3)),
        ("A7:C7", Backgrounds.green_light),
        ("A8", T("TSR1: Define Context Clearly Reference")),
        ("B8", T("Reference to context of use")),
        (
            "C8",
            Link(
                "https://journals.plos.org/plosone/doi?id=10.1371/journal.pone.0180194",
                "https://journals.plos.org/plosone/doi?id=10.1371/journal.pone.0180194",
            ),
        ),
        ("A8:C8", Backgrounds.yellow),
        # TSR2
        ("A9", T("TSR2: Use Appropriate Data Rating (0-4)")),
        (
            "B9",
            T(
                "Employ relevant and traceable information in the development or operation of the MSoP submission"
            ),
        ),
        ("C9", T(2)),
        ("A9:C9", Backgrounds.green_light),
        ("A10", T("TSR2: Use Appropriate Data Reference")),
        (
            "B10",
            T(
                "Reference to relevant and traceable information employed in the development or operation"
            ),
        ),
        (
            "C10",
            Link(
                "https://github.com/example_user/example_project/README",
                "https://github.com/example_user/example_project/README",
            ),
        ),
        ("A10:C10", Backgrounds.yellow),
        # TSR3
        ("A11", T("TSR3: Evaluate Within Context Rating (0-4)")),
        (
            "B11",
            T(
                "Verification, validation, uncertainty quantification and sensitivity analysis of the submission are accomplished with respect ot the reality of interest and intended use(s) of MSoP"
            ),
        ),
        ("C11", T(3)),
        ("A11:C11", Backgrounds.green_light),
        ("A12", T("TSR3: Evaluate Within Context Reference")),
        (
            "B12",
            T(
                "Reference to verification, validation, uncertainty quantification and sensitivity analysis"
            ),
        ),
        (
            "C12",
            Link("https://doi.org/10.0000/0000", "https://doi.org/10.0000/0000"),
        ),
        ("A12:C12", Backgrounds.yellow),
        # TSR4
        ("A13", T("TSR4: List Limitations Explicitly Rating (0-4)")),
        (
            "B13",
            T(
                "Restrictions, constraints or qualifications for, or on, the use of the submission are available for consideration by the users"
            ),
        ),
        ("C13", T(0)),
        ("A13:C13", Backgrounds.green_light),
        ("A14", T("TSR4: List Limitations Explicitly Reference")),
        (
            "B14",
            T("Reference to restrictions, constraints or qualifcations for use"),
        ),
        (
            "C14",
            Link("https://doi.org/10.0000/0000", "https://doi.org/10.0000/0000"),
        ),
        ("A14:C14", Backgrounds.yellow),
        # TSR5
        ("A15", T("TSR5: Use Version Control Rating (0-4)")),
        (
            "B15",
            T(
                "Implement a system to trace the time history of MSoP activities, including delineation of contributors' efforts"
            ),
        ),
        ("C15", T(4)),
        ("A15:C15", Backgrounds.green_light),
        ("A16", T("TSR5: Use Version Control Reference")),
        (
            "B16",
            T("Reference to version control system"),
        ),
        (
            "C16",
            Link(
                "https://github.com/example_user/example_project",
                "https://github.com/example_user/example_project",
            ),
        ),
        ("A16:C16", Backgrounds.yellow),
        # TSR6
        ("A17", T("TSR6: Document Adequately Rating (0-4)")),
        (
            "B17",
            T(
                "Maintain up-to-date informative records of all MSoP activities, including simulation code, model mark-up, scope and intended use of the MSoP activities, as well as users' and developers' guides"
            ),
        ),
        ("C17", T(4)),
        ("A17:C17", Backgrounds.green_light),
        ("A18", T("TSR6: Document Adequately Reference")),
        (
            "B18",
            T("Reference to documentation described above"),
        ),
        (
            "C18",
            Link(
                "https://github.com/example_user/example_project/README",
                "https://github.com/example_user/example_project/README",
            ),
        ),
        ("A18:C18", Backgrounds.yellow),
        # TSR7
        ("A19", T("TSR7: Disseminate Broadly Rating (0-4)")),
        (
            "B19",
            T(
                "Publish all components of MSoP including simulation software, models, simulation scenarios and results"
            ),
        ),
        ("C19", T(4)),
        ("A19:C19", Backgrounds.green_light),
        ("A20", T("TSR7: Disseminate Broadly Reference")),
        (
            "B20",
            T("Reference to publications"),
        ),
        (
            "C20",
            Link("https://doi.org/10.0000/0000", "https://doi.org/10.0000/0000"),
        ),
        ("A20:C20", Backgrounds.yellow),
        # TSR8
        ("A21", T("TSR8: Get Independent Reviews Rating (0-4)")),
        (
            "B21",
            T(
                "Have the MSoP submission reviewed by nonpartisan third-party users and developers"
            ),
        ),
        ("C21", T(2)),
        ("A21:C21", Backgrounds.green_light),
        ("A22", T("TSR8: Get Independent Reviews Reference")),
        (
            "B22",
            T("Reference to independent reviews"),
        ),
        (
            "C22",
            Link(
                "https://github.com/example_user/example_repository/pull/1",
                "https://github.com/example_user/example_repository/pull/1",
            ),
        ),
        ("A22:C22", Backgrounds.yellow),
        # TSR9
        ("A23", T("TSR9: Test Competing Implementations Rating (0-4)")),
        (
            "B23",
            T(
                "Use contrasting MSoP execution strategies to compare the conclusions of the different execution strategies against each other"
            ),
        ),
        ("C23", T(0)),
        ("A23:C23", Backgrounds.green_light),
        ("A24", T("TSR9: Test Competing Implementations Reference")),
        (
            "B24",
            T("Reference to implementations tested"),
        ),
        ("A24:C24", Backgrounds.yellow),
        # TSR10
        ("A25", T("TSR10a: Conform to Standards Rating (0-4)")),
        (
            "B25",
            T(
                "Adopt and promote generally applicable and discipline-specific operating procedures, guidelines and regulation accepted as best practices"
            ),
        ),
        ("C25", T(4)),
        ("A25:C25", Backgrounds.green_light),
        ("A26", T("TSR10a: Conform to Standards Reference")),
        (
            "B26",
            T("Reference to conformance to standards"),
        ),
        (
            "C26",
            Link(
                "https://models.physiomeproject.org/workspace/author_2021/@@rawfile/xx/my_model.cellml",
                "https://models.physiomeproject.org/workspace/author_2021/@@rawfile/xx/my_model.cellml",
            ),
        ),
        ("A26:C26", Backgrounds.yellow),
        ("A27", T("TSR10b: Relevant standards")),
        (
            "B27",
            T("Reference to relevant standards"),
        ),
        (
            "C27",
            Link("https://www.cellml.org", "https://www.cellml.org"),
        ),
        ("A27:C27", Backgrounds.yellow),
        # adding borders to TSR
        ("A6:A27", Borders.border_left_light),
        ("B6:B27", Borders.border_left_light),
        ("B6:B27", Borders.border_right_light),
        ("C6:C27", Borders.border_right_light),
        ("A7:C7", Borders.border_top_light),
        ("A9:C9", Borders.border_top_light),
        ("A11:C11", Borders.border_top_light),
        ("A13:C13", Borders.border_top_light),
        ("A15:C15", Borders.border_top_light),
        ("A17:C17", Borders.border_top_light),
        ("A19:C19", Borders.border_top_light),
        ("A21:C21", Borders.border_top_light),
        ("A23:C23", Borders.border_top_light),
        ("A25:C25", Borders.border_top_light),
        ("A27:C27", Borders.border_bottom_thick),
        ("A6:C27", Borders.light_grid),
        ## Annotations
        ("A28", TB("Annotations")),
        ("A28:C28", Backgrounds.green),
        # Ann1
        ("A29", T("Ann1: Code Verification Status")),
        (
            "B29",
            T(
                "Provide assurance that the MSoP submissions is free of bugs in the source code and numerical algorithms (yes/no)"
            ),
        ),
        ("C29", T("yes")),
        ("A29:C29", Backgrounds.green_light),
        ("A30", T("Ann1: Reference to Code Verification")),
        (
            "B30",
            T("Link to the verification documentation"),
        ),
        (
            "C30",
            Link(
                "https://github.com/example_user/example_repository/tests.py",
                "https://github.com/example_user/example_repository/tests.py",
            ),
        ),
        ("A30:C30", Backgrounds.yellow),
        # Ann2
        ("A31", T("Ann2: Code Validation Status")),
        (
            "B31",
            T(
                "Assess the degree to which a computer model and simulation framework is able to simulate a reality of interest"
            ),
        ),
        ("C31", T("yes")),
        ("A31:C31", Backgrounds.green_light),
        ("A32", T("Ann2: Reference to Code Validation")),
        ("B32", T("Reference to assessment")),
        (
            "C32",
            Link("https://doi.org/10.0000/0000", "https://doi.org/10.0000/0000"),
        ),
        ("A32:C32", Backgrounds.yellow),
        # Ann3
        ("A33", T("Ann3: Certification Status")),
        (
            "B33",
            T("The code has been certified externally (yes/no)"),
        ),
        ("C33", T("yes")),
        ("A33:C33", Backgrounds.green_light),
        ("A34", T("Ann3: Reference to Certification")),
        ("B34", T("Reference to the certification, if it has been certified")),
        (
            "C34",
            Link(
                "https://github.com/exampleuser/certifier.md",
                "https://github.com/exampleuser/certifier.md",
            ),
        ),
        ("A34:C34", Backgrounds.yellow),
        # Ann4
        ("A35", T("Ann4: Onboarded to o²S²PARC Status")),
        (
            "B35",
            T(
                "The MSoP submission has been integrated into the o²S²PARC platform and is publicly available"
            ),
        ),
        ("C35", T("yes")),
        ("A35:C35", Backgrounds.green_light),
        ("A36", T("Ann4: Reference to onboarded MSoP submission on o²S²PARC")),
        (
            "B36",
            T("The name of the onboarded service or template on the o²S²PARC platform"),
        ),
        ("C36", T("My Wonderful Model Service")),
        ("A36:C36", Backgrounds.yellow),
        # Ann4
        ("A37", T("Ann5: Testing on o²S²PARC Status")),
        (
            "B37",
            T(
                "The MSoP submission includes unit and integration testing on the o²S²PARC platform"
            ),
        ),
        ("C37", T("no")),
        ("A37:C37", Backgrounds.green_light),
        ("A38", T("Ann5: Testing on o²S²PARC Reference")),
        (
            "B38",
            T("Reference to the tests run on the onboarded MSoP submission"),
        ),
        ("A38:C38", Backgrounds.yellow),
        # ann boders
        ("A28:A38", Borders.border_left_light),
        ("B28:B38", Borders.border_left_light),
        ("B28:B38", Borders.border_right_light),
        ("C28:C38", Borders.border_right_light),
        ("A29:C29", Borders.border_top_light),
        ("A31:C31", Borders.border_top_light),
        ("A33:C33", Borders.border_top_light),
        ("A35:C35", Borders.border_top_light),
        ("A37:C37", Borders.border_top_light),
        ("A28:C38", Borders.light_grid),
        ## Footer
        ("A39", TB("Inputs")),
        (
            "B39",
            Link("Model/Simulation/Data Processing Inputs (if any)", "#'Inputs'!A1"),
        ),
        ("A40", TB("Outputs")),
        (
            "B40",
            Link("Model/Simulation/Data Processing Outputs (if any)", "#'Outputs'!A1"),
        ),
        ("A41", TB("Representation in CellML")),
        ("B41", TB("Analogous CellML/SED-ML model representation, if any")),
        (
            "C41",
            Link(
                "https://models.physiomeproject.org/workspace/author_2021/@@rawfile/xx/my_model.cellml",
                "https://models.physiomeproject.org/workspace/author_2021/@@rawfile/xx/my_model.cellml",
            ),
        ),
        # background and borders
        ("A39:C41", Backgrounds.yellow_dark),
        ("A39:C39", Borders.border_top_thick),
        ("A39:C41", Borders.medium_grid),
    ]
    column_dimensions: ClassVar[dict[str, int]] = {"A": 40, "B": 55, "C": 35}

    def assemble_data_for_template(
        self, template_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        params: CodeDescriptionParams = ensure_correct_instance(
            template_data, CodeDescriptionParams
        )
        code_description: CodeDescriptionModel = params.code_description

        # it is important for cells to be added to the list left to right and top to bottom
        # this is done to ensure styling is applied consistently, read more inside xlsx_base
        cells: deque[tuple[str, BaseXLSXCellData]] = deque()

        # assemble "Value x" headers
        max_number_of_headers = max(1, len(code_description.rrid_entires))
        for k, column_letter in enumerate(column_generator(4, max_number_of_headers)):
            cell_entry = (
                f"{column_letter}1",
                T(f"Value {k + 1}") | Backgrounds.blue | Borders.medium_grid,
            )
            cells.append(cell_entry)

        # assemble RRIDs
        rrid_entry: RRIDEntry
        for column_letter, rrid_entry in zip(
            column_generator(4, len(code_description.rrid_entires)),
            code_description.rrid_entires,
            strict=False,
        ):
            cells.append(
                (f"{column_letter}2", T(rrid_entry.rrid_term) | Borders.light_grid)
            )
            cells.append(
                (
                    f"{column_letter}3",
                    T(rrid_entry.rrid_identifier) | Borders.light_grid,
                )
            )
            cells.append(
                (
                    f"{column_letter}4",
                    T(rrid_entry.ontological_term) | Borders.light_grid,
                )
            )
            cells.append(
                (
                    f"{column_letter}5",
                    T(rrid_entry.ontological_identifier) | Borders.light_grid,
                )
            )

        static_cells = [
            # TSR data
            ("D7", T(code_description.tsr1_rating) | Borders.light_grid),
            ("D8", T(code_description.tsr1_reference) | Borders.light_grid),
            ("D9", T(code_description.tsr2_rating) | Borders.light_grid),
            ("D10", T(code_description.tsr2_reference) | Borders.light_grid),
            ("D11", T(code_description.tsr3_rating) | Borders.light_grid),
            ("D12", T(code_description.tsr3_reference) | Borders.light_grid),
            ("D13", T(code_description.tsr4_rating) | Borders.light_grid),
            ("D14", T(code_description.tsr4_reference) | Borders.light_grid),
            ("D15", T(code_description.tsr5_rating) | Borders.light_grid),
            ("D16", T(code_description.tsr5_reference) | Borders.light_grid),
            ("D17", T(code_description.tsr6_rating) | Borders.light_grid),
            ("D18", T(code_description.tsr6_reference) | Borders.light_grid),
            ("D19", T(code_description.tsr7_rating) | Borders.light_grid),
            ("D20", T(code_description.tsr7_reference) | Borders.light_grid),
            ("D21", T(code_description.tsr8_rating) | Borders.light_grid),
            ("D22", T(code_description.tsr8_reference) | Borders.light_grid),
            ("D23", T(code_description.tsr9_rating) | Borders.light_grid),
            ("D24", T(code_description.tsr9_reference) | Borders.light_grid),
            ("D25", T(code_description.tsr10a_rating) | Borders.light_grid),
            ("D26", T(code_description.tsr10a_reference) | Borders.light_grid),
            ("D27", T(code_description.tsr10b_relevant_standards) | Borders.light_grid),
            # Annotations
            ("D29", T(code_description.ann1_status) | Borders.light_grid),
            ("D30", T(code_description.ann1_reference) | Borders.light_grid),
            ("D31", T(code_description.ann2_status) | Borders.light_grid),
            ("D32", T(code_description.ann2_reference) | Borders.light_grid),
            ("D33", T(code_description.ann3_status) | Borders.light_grid),
            ("D34", T(code_description.ann3_reference) | Borders.light_grid),
            ("D35", T(code_description.ann4_status) | Borders.light_grid),
            ("D36", T(code_description.ann4_reference) | Borders.light_grid),
            ("D37", T(code_description.ann5_status) | Borders.light_grid),
            ("D38", T(code_description.ann5_reference) | Borders.light_grid),
            # other
            (
                "D41",
                T(code_description.reppresentation_in_cell_ml) | Borders.light_grid,
            ),
        ]

        cells.extend(static_cells)
        return list(cells)


def _include_ports_from_this_service(service_key: ServiceKey) -> bool:
    return service_key.startswith(
        (
            "simcore/services/frontend/parameter/",
            "simcore/services/frontend/iterator-consumer/probe/",
        )
    )


def _format_value_label(index: int) -> str:
    return f"Value {index+1}" if index > 0 else "Value"


class BaseSheetDivisionParts(BaseModel):
    total_columns: int

    @abstractmethod
    def get_cell_styles(
        self, o: int, sheet_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        """provides the offset so that edits to sections are easier to apply"""


class RRIDSheetPart(BaseSheetDivisionParts):
    total_columns: int = 5

    def get_cell_styles(
        self, o: int, sheet_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        static_cells: list[tuple[str, BaseXLSXCellData]] = [
            # A column
            (f"A{o+1}", TB("Metadata element")),
            (f"A{o+2}", TB("RRID Term")),
            (f"A{o+3}", TB("RRID Identifier")),
            (f"A{o+4}", TB("Ontology Term")),
            (f"A{o+5}", TB("Ontology Identifier")),
            # B column
            (f"B{o+1}", TB("Description")),
            (
                f"B{o+2}",
                T(
                    "Tools or resources used as part of the model, simulation, or data processing (henceforth referred to as project)"
                ),
            ),
            (
                f"B{o+3}",
                T(
                    "Resources identifier (with 'RRID:')  associated with the project submission and its tools and resources"
                ),
            ),
            (
                f"B{o+4}",
                T(
                    "Ontology term (human-readable)  associated with the project submission"
                ),
            ),
            (
                f"B{o+5}",
                Link(
                    "Associated ontology identifier from SciCrunch",
                    "https://scicrunch.org/sawg",
                ),
            ),
            # C column
            (f"C{o+1}", TB("Example")),
            (f"C{o+2}", T("ImageJ")),
            (f"C{o+3}", T("RRID:SCR_003070")),
            (f"C{o+4}", T("Heart")),
            (f"C{o+5}", T("UBERON:0000948")),
        ]

        # add data to this
        rrid_entires: list[RRIDEntry] = cast(list[RRIDEntry], sheet_data)

        rrid_cells: list[tuple[str, BaseXLSXCellData]] = []
        for column_letter, (i, rrid_entry) in zip(
            column_generator(4, len(rrid_entires)), enumerate(rrid_entires), strict=True
        ):
            rrid_cells.append(
                (
                    f"{column_letter}{o+1}",
                    TB(_format_value_label(i))
                    | (Backgrounds.blue if i == 0 else Backgrounds.green_light)
                    | Borders.medium_grid,
                )
            )
            rrid_cells.append((f"{column_letter}{o+2}", T(rrid_entry.rrid_term)))
            rrid_cells.append(
                (
                    f"{column_letter}{o+3}",
                    T(rrid_entry.rrid_identifier) | Borders.border_bottom_light,
                )
            )
            rrid_cells.append((f"{column_letter}{o+4}", T(rrid_entry.ontological_term)))
            rrid_cells.append(
                (f"{column_letter}{o+5}", T(rrid_entry.ontological_identifier))
            )

        # apply styles last or it will not render as expected
        styles = [
            (f"A{o+1}:C{o+1}", Backgrounds.blue),
            (f"A{o+2}:B{o+5}", Backgrounds.yellow_dark),
            (f"A{o+1}:B{o+5}", Borders.medium_grid),
        ]
        for column_letter in column_generator(3, len(rrid_entires) + 1):
            styles.append(  # noqa: PERF401
                (f"{column_letter}{o+3}", Borders.border_bottom_light)
            )

        return static_cells + rrid_cells + styles


_SORTED_REFERENCE_ITEMS: Final[list[str]] = [
    "r01",
    "r02",
    "r03",
    "r03b",
    "r03c",
    "r04",
    "r05",
    "r06",
    "r07",
    "r07b",
    "r07c",
    "r07d",
    "r07e",
    "r08",
    "r08b",
    "r09",
    "r10",
    "r10b",
]


class TSRSheetPart(BaseSheetDivisionParts):
    total_columns: int = 20

    def get_cell_styles(
        self, o: int, sheet_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        static_cells: list[tuple[str, BaseXLSXCellData]] = [
            # HEADERS
            (f"A{o+1}", T("Ten Simple Rules (TSR)")),
            (
                f"B{o+1}",
                Link(
                    "See TSR conformance for a definition of the Levels",
                    "https://www.imagwiki.nibib.nih.gov/content/10-simple-rules-conformance-rubric",
                ),
            ),
            (f"C{o+1}", T("Example")),
            (f"A{o+2}", T("TSR Column Type")),
            (
                f"B{o+2}",
                T(
                    "Column type. Valid values are: Link, Text, Rating, Target, Target Justification"
                )
                | Comment(
                    (
                        "Note that the actual requirements for TSR rows are a bit more complex. "
                        "For example, the at least one link column must always be present, but for any "
                        "given row it may be empty if there is a text column present with a value."
                    ),
                    "",
                    width=400,
                ),
            ),
            (f"C{o+2}", T("Link")),
            # TSR Legend
            (f"A{o+3}", T("TSR1: Clearly Defined Context")),
            (f"B{o+3}", T("Description of use cases for the project.")),
            (f"C{o+3}", T("https://doi.org/10.1101/2021.02.10.430563")),
            (f"A{o+4}", T("TSR2: Use of Appropriate Data")),
            (
                f"B{o+4}",
                T(
                    "Links to data that was used to create, validate, test, etc. the project."
                ),
            ),
            (f"C{o+4}", T("https://sparc.science/data?type=dataset")),
            (f"A{o+5}", T("TSR3a: Verification")),
            (f"B{o+5}", T("Link to test suite for project.")),
            (
                f"C{o+5}",
                T("https://github.com/SciCrunch/sparc-curation/tree/master/test"),
            ),
            (f"A{o+6}", T("TSR3b: Verification Results")),
            (
                f"B{o+6}",
                T(
                    "Link to test results from running the tests for the project, e.g., "
                    "on the o²S²PARC platform"
                ),
            ),
            (f"A{o+7}", T("TSR3c: Evaluation Within Context")),
            (
                f"B{o+7}",
                T(
                    "Link to scientific validation (experimental comparator), sensitivity "
                    "analysis and uncertainty quantification for the project in the context "
                    "of the use cases described in TSR1."
                ),
            ),
            (f"A{o+8}", T("TSR4: Explicitly Listed Limitations")),
            (
                f"B{o+8}",
                T(
                    "Link to documentation of known issues and limitations of the project."
                ),
            ),
            (f"A{o+9}", T("TSR5: Version Control")),
            (
                f"B{o+9}",
                T(
                    "Link to primary forge repository for the project. For example, o²S²PARC, github, or gitlab instance."
                ),
            ),
            (f"C{o+9}", T("https://github.com/SciCrunch/sparc-curation")),
            (f"A{o+10}", T("TSR6: Adequate Documentation")),
            (
                f"B{o+10}",
                T("Link to user and/or developer documentation for the project."),
            ),
            (
                f"C{o+10}",
                T("https://github.com/SciCrunch/sparc-curation/blob/master/README.md"),
            ),
            (f"A{o+11}", T("TSR7a: Broad Dissemination: Releases")),
            (
                f"B{o+11}",
                T(
                    "Link to the download or release page for the project, e.g., on the SPARC Portal."
                ),
            ),
            (f"C{o+11}", T("https://github.com/SciCrunch/sparc-curation/releases")),
            (f"A{o+12}", T("TSR7b: Broad Dissemination: Issues")),
            (f"B{o+12}", T("Link to project issue tracker.")),
            (f"C{o+12}", T("https://github.com/SciCrunch/sparc-curation/issues")),
            (f"A{o+13}", T("TSR7c: Broad Dissemination: License")),
            (f"B{o+13}", T("Link to project license.")),
            (
                f"C{o+13}",
                T("https://github.com/SciCrunch/sparc-curation/blob/master/LICENSE"),
            ),
            (f"A{o+14}", T("TSR7d: Broad Dissemination: Packages")),
            (
                f"B{o+14}",
                T(
                    "Link to language ecosystem package repository. For example, PyPI for python projects."
                ),
            ),
            (f"C{o+14}", T("https://pypi.org/project/sparcur/")),
            (f"A{o+15}", T("TSR7e: Broad Dissemination: Interactive")),
            (
                f"B{o+15}",
                T(
                    "Link to the project on an interactive software hosting platform e.g. o²S²PARC"
                ),
            ),
            (
                f"C{o+15}",
                T(
                    "https://github.com/tgbugs/dockerfiles/blob/master/source.org#sparcron-user"
                ),
            ),
            (f"A{o+16}", T("TSR8a: Independent Reviews")),
            (
                f"B{o+16}",
                T(
                    "Links to reviews of project by independent members of the community."
                ),
            ),
            (f"C{o+16}", T("https://www.incf.org/sparc-data-structure")),
            (f"A{o+17}", T("TSR8b: External Certification")),
            (f"B{o+17}", T("Link to external certification of project.")),
            (
                f"C{o+17}",
                T("https://www.nlm.nih.gov/NIHbmic/domain_specific_repositories.html"),
            ),
            (f"A{o+18}", T("TSR9: Competing Implementation Testing")),
            (
                f"B{o+18}",
                T(
                    "Link to benchmarking against other projects operating in the same domain."
                ),
            ),
            (f"A{o+19}", T("TSR10a: Relevant standards")),
            (
                f"B{o+19}",
                T(
                    "List and/or link to standards/guidelines that this project conforms to or implements."
                ),
            ),
            (f"A{o+20}", T("TSR10b: Standards Adherence")),
            (f"A{o+20}", T("Link to demonstration that project conforms to standard.")),
        ]

        tsr_entries = cast(dict[str, TSRFullEntry | TSROnlYReferenceEntry], sheet_data)

        rating_and_target_values: list[tuple[str, BaseXLSXCellData]] = [
            (f"D{o+2}", T("Rating")),
            (f"E{o+2}", T("Target")),
            (f"D{o+3}", T(tsr_entries["r01"].current_level)),
            (f"E{o+3}", T(tsr_entries["r01"].target_level)),
            (f"D{o+4}", T(tsr_entries["r02"].current_level)),
            (f"E{o+4}", T(tsr_entries["r02"].target_level)),
            (f"D{o+5}", T(tsr_entries["r03"].current_level)),
            (f"E{o+5}", T(tsr_entries["r03"].target_level)),
            (f"D{o+8}", T(tsr_entries["r04"].current_level)),
            (f"E{o+8}", T(tsr_entries["r04"].target_level)),
            (f"D{o+9}", T(tsr_entries["r05"].current_level)),
            (f"E{o+9}", T(tsr_entries["r05"].target_level)),
            (f"D{o+10}", T(tsr_entries["r06"].current_level)),
            (f"E{o+10}", T(tsr_entries["r06"].target_level)),
            (f"D{o+11}", T(tsr_entries["r07"].current_level)),
            (f"E{o+11}", T(tsr_entries["r07"].target_level)),
            (f"D{o+16}", T(tsr_entries["r08"].current_level)),
            (f"E{o+16}", T(tsr_entries["r08"].target_level)),
            (f"D{o+18}", T(tsr_entries["r09"].current_level)),
            (f"E{o+18}", T(tsr_entries["r09"].target_level)),
            (f"D{o+19}", T(tsr_entries["r10"].current_level)),
            (f"E{o+19}", T(tsr_entries["r10"].target_level)),
        ]

        max_references_length = max(
            len(tsr_entries[k].references) for k in _SORTED_REFERENCE_ITEMS
        )

        value_labels_cells: list[tuple[str, BaseXLSXCellData]] = [
            (f"{c}{o+1}", T(_format_value_label(i)) | Backgrounds.gray_background)
            for i, c in enumerate(column_generator(4, max_references_length + 2))
        ]
        link_labels_cells: list[tuple[str, BaseXLSXCellData]] = [
            (f"{c}{o+2}", T("Link")) for c in column_generator(6, max_references_length)
        ]

        references_cells: list[tuple[str, BaseXLSXCellData]] = []
        for i, key in enumerate(_SORTED_REFERENCE_ITEMS):
            references = tsr_entries[key].references
            for c, reference in zip(
                column_generator(6, len(references)), references, strict=True
            ):
                references_cells.append((f"{c}{o+3+i}", T(reference)))

        items_already_converted_cells: list[tuple[str, BaseXLSXCellData]] = [
            (f"D{o+6}", T("All TSR3 items are covered by the rating on the TSR3a row")),
            (f"D{o+6}:E{o+7}", Backgrounds.gray_background),
            (
                f"D{o+12}",
                T("All TSR7 items are covered by the rating on the TSR7a row"),
            ),
            (f"D{o+12}:E{o+16}", Backgrounds.gray_background),
            (
                f"D{o+17}",
                T("All TSR8 items are covered by the rating on the TSR8a row"),
            ),
            (f"D{o+17}:E{o+17}", Backgrounds.gray_background),
            (
                f"D{o+20}",
                T("All TSR10 items are covered by the rating on the TSR10a row"),
            ),
            (f"D{o+20}:E{o+20}", Backgrounds.gray_background),
        ]

        style_cells: list[tuple[str, BaseXLSXCellData]] = [
            (f"A{o+1}:C{o+1}", Backgrounds.gray_background),
            (f"A{o+2}:B{o+3}", Backgrounds.blue),
            (f"A{o+4}:B{o+7}", Backgrounds.green_light),
            (f"A{o+8}:B{o+8}", Backgrounds.blue),
            (f"A{o+9}:B{o+9}", Backgrounds.green_light),
            (f"A{o+10}:B{o+10}", Backgrounds.blue),
            (f"A{o+11}:B{o+20}", Backgrounds.green_light),
            (f"A{o+1}:B{o+20}", Borders.medium_grid),
        ]

        return (
            static_cells
            + rating_and_target_values
            + value_labels_cells
            + link_labels_cells
            + references_cells
            + items_already_converted_cells
            + style_cells
        )


class InputsOutputsSheetPart(BaseSheetDivisionParts):
    total_columns: int = 14

    def get_cell_styles(
        self, o: int, sheet_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        static_cells: list[tuple[str, BaseXLSXCellData]] = [
            # A column
            (f"A{o+1}", T("Input/Output Information") | Backgrounds.gray_background),
            (f"A{o+2}", T("Number of Inputs") | Backgrounds.green),
            (f"A{o+3}", T("Input Parameter name") | Backgrounds.green),
            (f"A{o+4}", T("Input Parameter type") | Backgrounds.green),
            (f"A{o+5}", T("Input Parameter description") | Backgrounds.green),
            (f"A{o+6}", T("Input Units") | Backgrounds.green),
            (f"A{o+7}", T("Input Default value") | Backgrounds.yellow_dark),
            (f"A{o+8}", T("Input Constraints") | Backgrounds.yellow_dark),
            (f"A{o+9}", T("Number of Outputs") | Backgrounds.green),
            (f"A{o+10}", T("Output Parameter name") | Backgrounds.green),
            (f"A{o+11}", T("Output Parameter type") | Backgrounds.green),
            (f"A{o+12}", T("Output Parameter description") | Backgrounds.green),
            (f"A{o+13}", T("Output Units") | Backgrounds.green),
            (f"A{o+14}", T("Output Constraints") | Backgrounds.yellow_dark),
            # B column
            (f"B{o+1}", T("Description") | Backgrounds.gray_background),
            (
                f"B{o+2}",
                T(
                    'In  o²S²PARC, "number of inputs" is equivalent to the number of parameterized'
                    " input ports (i.e., service ports in the pipeline with attached 'Parameter' nodes). "
                    "For custom code, number of inputs is the number of input parameters for the code. "
                    "E.g. [out1, out2]=mymodel(param1, param2, param3) has 3 inputs even if a single "
                    "parameter is a matrix of multiple values."
                )
                | Backgrounds.green,
            ),
            (f"B{o+3}", T("Name of the parameter") | Backgrounds.green),
            (
                f"B{o+4}",
                T(
                    "Type (bool, int/enum, real, complex/phasor, vector, array, table, field, structure, file, other)"
                )
                | Backgrounds.green,
            ),
            (
                f"B{o+5}",
                T("Description of what the parameter represents") | Backgrounds.green,
            ),
            (f"B{o+6}", T("string or 'N/A'") | Backgrounds.green),
            (f"B{o+7}", T("Default value for the parameter") | Backgrounds.yellow_dark),
            (f"B{o+8}", T("Input Constraints") | Backgrounds.yellow_dark),
            (
                f"B{o+9}",
                T(
                    "Range [min, max] of acceptable parameter values, or other constraints as formulas / sets"
                )
                | Backgrounds.green,
            ),
            (
                f"B{o+10}",
                T(
                    'In  o²S²PARC, "number of outputs" is equivalent to number of output ports with '
                    "attached 'Probes'. For custom code, number of inputs is the number of input parameters "
                    "for the code. E.g. [out1, out2]=mymodel(param1, param2, param3) has 2 outputs even if "
                    "a single output is a matrix of multiple values."
                )
                | Backgrounds.green,
            ),
            (f"B{o+11}", T("Name of the parameter") | Backgrounds.green),
            (
                f"B{o+12}",
                T(
                    "Type (bool, int/enum, real, complex/phasor, vector, time series, array, table, field, structure, file, other)"
                )
                | Backgrounds.green,
            ),
            (f"B{o+13}", T("string or 'N/A'") | Backgrounds.green),
            (
                f"B{o+14}",
                T(
                    "Range [min, max] of possible output values, or other constraints as formulas / sets"
                )
                | Backgrounds.yellow_dark,
            ),
            # C column
            (f"C{o+1}", T("Example")),
            (f"C{o+2}", T("1")),
            (f"C{o+3}", T("Stimulation amplitude")),
            (f"C{o+4}", T("real")),
            (f"C{o+5}", T("Current injected through a stimulation electrode")),
            (f"C{o+6}", T("milliAmpere")),
            (f"C{o+7}", T("0.07")),
            (f"C{o+8}", T("[0.05, 0.1]")),
            (f"C{o+9}", T("0")),
            (f"C{o+10}", T("Recruitment level")),
            (f"C{o+11}", T("real")),
            (f"C{o+12}", T("Percentage of activated nerve fibers")),
            (f"C{o+13}", T("%")),
            (f"C{o+14}", T("[0.05, 0.1]")),
        ]

        code_description_params: CodeDescriptionParams = cast(
            CodeDescriptionParams, sheet_data
        )

        # formatted inputs

        inputs: list[InputsEntryModel] = [
            x
            for x in code_description_params.inputs
            if _include_ports_from_this_service(x.service_key)
        ]

        inputs_cells: list[tuple[str, BaseXLSXCellData]] = [
            (f"D{o+2}", T(len(inputs))),
        ]

        for column_letter, input_entry in zip(
            column_generator(4, len(inputs)), inputs, strict=True
        ):
            inputs_cells.append((f"{column_letter}{o+3}", T(input_entry.input_name)))
            inputs_cells.append(
                (f"{column_letter}{o+4}", T(input_entry.input_data_type))
            )
            inputs_cells.append(
                (f"{column_letter}{o+5}", T(input_entry.input_parameter_description))
            )
            inputs_cells.append(
                (f"{column_letter}{o+6}", T(input_entry.input_data_units))
            )
            inputs_cells.append(
                (f"{column_letter}{o+7}", T(input_entry.input_data_default_value))
            )
            inputs_cells.append(
                (f"{column_letter}{o+8}", T(input_entry.input_data_constraints))
            )

        # formatted outputs

        outputs: list[OutputsEntryModel] = [
            x
            for x in code_description_params.outputs
            if _include_ports_from_this_service(x.service_key)
        ]

        outputs_cells: list[tuple[str, BaseXLSXCellData]] = [
            (f"D{o+9}", T(len(outputs)))
        ]

        for column_letter, output_entry in zip(
            column_generator(4, len(outputs)), outputs, strict=True
        ):
            inputs_cells.append((f"{column_letter}{o+10}", T(output_entry.output_name)))
            inputs_cells.append(
                (f"{column_letter}{o+11}", T(output_entry.output_data_type))
            )
            inputs_cells.append(
                (f"{column_letter}{o+12}", T(output_entry.output_parameter_description))
            )
            inputs_cells.append(
                (f"{column_letter}{o+13}", T(output_entry.output_data_units))
            )
            inputs_cells.append(
                (f"{column_letter}{o+13}", T(output_entry.output_data_constraints))
            )

        # write top "value n" labels
        value_labels: list[tuple[str, BaseXLSXCellData]] = []
        for i, column_letter in enumerate(
            column_generator(4, max(len(inputs), len(outputs)))
        ):
            value_labels.append(
                (
                    f"{column_letter}{o+1}",
                    TB(_format_value_label(i)) | Backgrounds.gray_background,
                )
            )

        styles: list[tuple[str, BaseXLSXCellData]] = [
            (f"A{o+1}:C{o+1}", Backgrounds.gray_background),
            (f"A{o+2}:B{o+14}", Borders.medium_grid),
            (f"C{o+8}", Borders.border_bottom_medium),
        ]

        return static_cells + inputs_cells + outputs_cells + value_labels + styles


class SheetCodeDescriptionV2(BaseXLSXSheet):
    name = "Sheet1"
    cell_styles: ClassVar[list[tuple[str, BaseXLSXCellData]]] = []

    def assemble_data_for_template(
        self, template_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        code_description_params: CodeDescriptionParams = ensure_correct_instance(
            template_data, CodeDescriptionParams
        )

        cells: list[tuple[str, BaseXLSXCellData]] = []

        offset_index: int = 0

        entries: list[tuple[BaseSheetDivisionParts, Any]] = [
            (RRIDSheetPart(), code_description_params.code_description.rrid_entires),
            (TSRSheetPart(), code_description_params.code_description.tsr_entries),
            (InputsOutputsSheetPart(), code_description_params),
        ]
        for sheet_division, sheet_data in entries:
            cells.extend(sheet_division.get_cell_styles(offset_index, sheet_data))
            offset_index += sheet_division.total_columns

        return cells

    column_dimensions: ClassVar[dict[str, int]] = {
        "A": 40,
        "B": 40,
        "C": 40,
        "D": 40,
    }


class CodeDescriptionXLSXDocument(BaseXLSXDocument):
    file_name = "code_description.xlsx"
    sheet1 = SheetCodeDescriptionV2()
