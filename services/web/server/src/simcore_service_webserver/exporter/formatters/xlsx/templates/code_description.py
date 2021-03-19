from simcore_service_webserver.exporter.formatters.xlsx.xlsx_base import (
    BaseXLSXSheet,
    BaseXLSXDocument,
)
from simcore_service_webserver.exporter.formatters.xlsx.styling_components import (
    T,
    TB,
    Link,
    Backgrounds,
    Borders,
    AllignTopCenter,
    AllignTop,
)


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
    column_dimensions = {"A": 40, "B": 55, "C": 35}


class InputsSheet(BaseXLSXSheet):
    name = "Inputs"
    cell_styles = [
        # column A
        ("A1", T("Field")),
        ("A2", T("Description")),
        ("A3", T("Example")),
        # column B
        ("B1", TB("Service name")),
        ("B2", T("Name of the service containing this input")),
        ("B3", T("MembraneModel")),
        # column C
        ("C1", TB("Service version")),
        ("C2", T("Version of the service containing this input")),
        ("C3", T("1.0.1")),
        # column D
        ("D1", TB("Input Name")),
        ("D2", T("An input field to the MSoP submission")),
        ("D3", T("Membrane Depolarization")),
        # column E
        ("E1", TB("Input Data Ontology Identifier")),
        (
            "E2",
            Link(
                "Ontology identifier for the input field, if applicable",
                "https://scicrunch.org/scicrunch/interlex/search?q=NLXOEN&l=NLXOEN&types=term",
            ),
        ),
        ("E3", T("ILX:0103092")),
        # column F
        ("F1", TB("Input Data Type")),
        ("F2", T("Data type for the input field (in plain text)")),
        ("F3", T(".txt file")),
        # column G
        ("G1", TB("Input Data Units")),
        ("G2", T("Units of data for the input field, if applicable")),
        ("G3", T("millivolts")),
        # column H
        ("H1", TB("Input Data Default Value")),
        ("H2", T("Default value for the input field, if applicable (doi or value)")),
        # background & borders
        ("A1:A3", Backgrounds.gray_background),
        ("B1:H1", Backgrounds.yellow_dark),
        ("B2:H3", Backgrounds.yellow),
        ("A1:H3", Borders.medium_grid),
    ]
    column_dimensions = {
        "A": 10,
        "B": 20,
        "C": 20,
        "D": 20,
        "E": 20,
        "F": 20,
        "G": 20,
        "H": 20,
    }


class OutputsSheet(BaseXLSXSheet):
    name = "Outputs"
    cell_styles = [
        # column A
        ("A1", T("Field")),
        ("A2", T("Description")),
        ("A3", T("Example")),
        # column B
        ("B1", TB("Service name")),
        ("B2", T("Name of the service containing this output")),
        ("B3", T("ThresholdModel")),
        # column C
        ("C1", TB("Service version")),
        ("C2", T("Version of the service containing this output")),
        ("C3", T("1.0.1")),
        # column D
        ("D1", TB("Output Name")),
        ("D2", T("An output field to the MSoP submission")),
        ("D3", T("Excitation Threshold")),
        # column E
        ("E1", TB("Output Data Ontology Identifier")),
        (
            "E2",
            Link(
                "Ontology identifier for the output field, if applicable",
                "https://scicrunch.org/scicrunch/interlex/search?q=NLXOEN&l=NLXOEN&types=term",
            ),
        ),
        ("E3", T("ILX:0110906 ")),
        # column F
        ("F1", TB("Output Data Type")),
        ("F2", T("Data type for the output field")),
        ("F3", T("real number")),
        # column G
        ("G1", TB("Output Data Units")),
        ("G2", T("Units of data for the output field, if applicable")),
        ("G3", T("millivolts")),
        # background & borders
        ("A1:A3", Backgrounds.gray_background),
        ("B1:G1", Backgrounds.yellow_dark),
        ("B2:G3", Backgrounds.yellow),
        ("A1:G3", Borders.medium_grid),
    ]
    column_dimensions = {"A": 10, "B": 20, "C": 20, "D": 20, "E": 20, "F": 20, "G": 20}


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
        # background
        ("A1:F2", Backgrounds.green),
        ("A3:F3", Backgrounds.yellow),
        # borders
        ("A1:F3", Borders.medium_grid),
        # alignment
        ("A1:F2", AllignTopCenter()),
        ("A3:F3", AllignTop()),
    ]
    cell_merge = {"A1:A2"}
    column_dimensions = {"A": 20, "B": 20, "C": 20, "D": 20, "E": 20, "F": 20}


class CodeDescriptionXLSXDocument(BaseXLSXDocument):
    code_description = CodeDescriptionSheet()
    inputs = InputsSheet()
    outputs = OutputsSheet()
    tsr_rating = SheetTSRRating()

    # TODO: attach here methods to populate with data
