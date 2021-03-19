from simcore_service_webserver.exporter.xlsx_base import (
    BaseXLSXCellData,
    BaseXLSXSheet,
    BaseXLSXDocument,
)

from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.styles.borders import BORDER_THIN, BORDER_MEDIUM


COLOR_BLACK = "FF000000"
COLOR_GRAY = "FFC9C9C9"
COLOR_LINK = "0563C1"
COLOR_BLUE = "8CB3DF"
COLOR_GREEN = "99C87B"
COLOR_LIGHT_GREEN = "BBDAA5"
COLOR_YELLOW = "FEE288"


class T(BaseXLSXCellData):
    """Helper for inputing text into cells"""

    alignment = Alignment(wrap_text=True)

    def __init__(self, text: str):
        super().__init__(value=text)


class TB(T):
    font = Font(bold=True)


class Link(T):
    font = Font(underline="single", color=COLOR_LINK)

    def __init__(self, text: str, link: str):
        super().__init__(text=f'=HYPERLINK("{link}", "{text}")')


class BackgroundWithColor(BaseXLSXCellData):
    def __init__(self, color: str):
        super().__init__(
            fill=PatternFill(start_color=color, end_color=color, fill_type="solid")
        )


class Backgrounds:
    blue = BackgroundWithColor(color=COLOR_BLUE)
    green = BackgroundWithColor(color=COLOR_GREEN)
    light_green = BackgroundWithColor(color=COLOR_LIGHT_GREEN)
    yellow = BackgroundWithColor(color=COLOR_YELLOW)


class BorderWithStyle(BaseXLSXCellData):
    """Base for creating custom borders"""

    def __init__(self, *borders_sides, border_style: str, color: str):
        side = Side(border_style=border_style, color=color)
        super().__init__(border=Border(**{x: side for x in borders_sides}))


class Borders:
    """Collector for different border styles"""

    light_grid = BorderWithStyle(
        "top",
        "left",
        "right",
        "bottom",
        "outline",
        "vertical",
        "horizontal",
        border_style=BORDER_THIN,
        color=COLOR_GRAY,
    )

    bold_grid = BorderWithStyle(
        "top",
        "left",
        "right",
        "bottom",
        "outline",
        "vertical",
        "horizontal",
        border_style=BORDER_MEDIUM,
        color=COLOR_BLACK,
    )

    border_bottom_thick = BorderWithStyle(
        "bottom", border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )
    border_bottom_thick = BorderWithStyle(
        "bottom", border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )
    border_left_thick = BorderWithStyle(
        "left", border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )
    border_right_thick = BorderWithStyle(
        "right", border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )


class AllignTopCenter(BaseXLSXCellData):
    alignment = Alignment(horizontal="center", vertical="top")


class AllignTop(BaseXLSXCellData):
    alignment = Alignment(vertical="top")


class CodeDescriptionSheet(BaseXLSXSheet):
    name = "Code Description"
    cell_styles = [
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
        ("A5:C5", Borders.border_bottom_thick),
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
        ("A7:C7", Backgrounds.light_green),
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
        ("A9:C9", Backgrounds.light_green),
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
        ("A11:C11", Backgrounds.light_green),
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
        ("A13:C13", Backgrounds.light_green),
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
        ("A15:C15", Backgrounds.light_green),
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
        ("A17:C17", Backgrounds.light_green),
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
        ("A19:C19", Backgrounds.light_green),
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
        ("A21:C21", Backgrounds.light_green),
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
        ("A3", T("TSR9: Test Competing Implementations Rating (0-4)")),
        (
            "B23",
            T(
                "Use contrasting MSoP execution strategies to compare the conclusions of the different execution strategies against each other"
            ),
        ),
        ("C23", T(0)),
        ("A23:C23", Backgrounds.light_green),
        ("A4", T("TSR9: Test Competing Implementations Reference")),
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
        ("A25:C25", Backgrounds.light_green),
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
        # adding gird and borders for the TSR
        ("A6:C27", Borders.light_grid),
    ]
    column_dimensions = {"A": 40, "B": 55, "C": 35}


class SheetTSRRating(BaseXLSXSheet):
    name = "TSR Rating Rubric"
    cell_styles = [
        ("A1", T("Conformance Level")),
        ("A3", T("Description")),
        ("B1", T("Comprehensive")),
        ("B2", T(4)),
        (
            "B3",
            T(
                "Can be understood by non MS&P practitioners familiar with the application domain and the intended context of use"
            ),
        ),
        ("C1", T("Extensive")),
        ("C2", T(3)),
        (
            "C3",
            T(
                "Can be understood by MS&P practitions not familiar with the application domain and the intended context of use"
            ),
        ),
        ("D1", T("Adequate")),
        ("D2", T(2)),
        (
            "D3",
            T(
                "Can be understood by MS&P practitioners familiar with the application domain and the intended context of use"
            ),
        ),
        ("E1", T("Partial")),
        ("E2", T(1)),
        (
            "E3",
            T(
                "Unclear to the MS&P practitioners familiar with the application domain and the intended context of use"
            ),
        ),
        ("F1", T("Insufficient")),
        ("F2", T(0)),
        (
            "F3",
            T(
                "Missing or grossly incomplete information to properly evaluate the conformance with the rule"
            ),
        ),
        # background & Alignment
        ("A1:F2", Backgrounds.green),
        ("A3:F3", Backgrounds.yellow),
        # Borders
        ("A1:F3", Borders.light_grid),
        # Alignment
        ("A1:F2", AllignTopCenter()),
        ("A3:F3", AllignTop()),
    ]
    cell_merge = {"A1:A2"}
    column_dimensions = {"A": 20, "B": 20, "C": 20, "D": 20, "E": 20, "F": 20}


class CodeDescriptionXLSXDocument(BaseXLSXDocument):
    code_description = CodeDescriptionSheet()
    tsr_rating = SheetTSRRating()


if __name__ == "__main__":
    document = CodeDescriptionXLSXDocument()
    document.save_document("test.xlsx")
