from pydantic import BaseModel, Field, StrictStr

from .core.styling_components import TB, Backgrounds, Borders, Comment, Link, T
from .core.xlsx_base import BaseXLSXCellData, BaseXLSXDocument, BaseXLSXSheet
from .utils import column_generator, ensure_correct_instance, get_max_array_length


class ContributorEntryModel(BaseModel):
    contributor: StrictStr = Field(
        ...,
        description=(
            "Name of any contributors to the dataset.  These individuals need not have "
            "been authors on any publications describing the data, but should be "
            "acknowledged for their role in producing and publishing the data set. "
            "If more than one, add each contributor in a new column."
        ),
    )
    orcid_id: StrictStr = Field(
        "",
        description=(
            "ORCID ID. If you don't have an ORCID, we suggest you sign up for one at "
            "https://orcid.org/"
        ),
    )
    affiliation: StrictStr = Field(
        "", description="Institutional affiliation for contributors"
    )
    role: StrictStr = Field(
        "",
        description=(
            "Contributor role, e.g., PrincipleInvestigator, Creator, CoInvestigator, "
            "ContactPerson, DataCollector, DataCurator, DataManager, Distributor, Editor, "
            "Producer, ProjectLeader, ProjectManager, ProjectMember, RelatedPerson, "
            "Researcher, ResearchGroup, Sponsor, Supervisor, WorkPackageLeader, Other. "
            "These roles are provided by the Data Cite schema.  If more than one, add "
            "additional columns"
        ),
    )
    is_contact_person: StrictStr = Field(
        "no",
        description="Yes or No if the contributor is a contact person for the dataset",
    )


class DoiEntryModel(BaseModel):
    originating_article_doi: StrictStr = Field(
        ...,
        description="DOIs of published articles that were generated from this dataset",
    )

    protocol_url_or_doi: StrictStr = Field(
        "",
        description=(
            "URLs (if still private) / DOIs (if public) of protocols from protocols.io "
            "related to this dataset"
        ),
    )


class LinkEntryModel(BaseModel):
    additional_link: StrictStr = Field(
        ...,
        description=(
            "URLs of additional resources used by this dataset (e.g., a link to a "
            "code repository)"
        ),
    )
    link_description: StrictStr = Field(
        "",
        description=(
            "Short description of URL content, you do not need to fill this in "
            "for Originating Article DOI or Protocol URL or DOI "
        ),
    )


class DatasetDescriptionParams(BaseModel):
    name: StrictStr = Field(
        ...,
        description=(
            "Descriptive title for the data set. Equivalent to the title of a scientific "
            "paper. The metadata associated with the published version of this dataset "
            "does not currently make use of this field."
        ),
    )
    description: StrictStr = Field(
        ...,
        description=(
            "NOTE This field is not currently used when publishing a SPARC dataset. "
            "Brief description of the study and the data set. Equivalent to the "
            "abstract of a scientific paper. Include the rationale for the approach, "
            "the types of data collected, the techniques used, formats and number of "
            "files and an approximate size. The metadata associated with the published "
            "version of this dataset does not currently make use of this field."
        ),
    )
    keywords: StrictStr = Field(
        "",
        description="A set of 3-5 keywords other than the above that will aid in search",
    )

    contributor_entries: list[ContributorEntryModel] = Field(
        [], description="list of contributor data"
    )

    acknowledgements: str = Field(
        "Thank you everyone!",
        description="Acknowledgements beyond funding and contributors",
    )
    funding: str = Field("", description="Funding sources")

    doi_entries: list[DoiEntryModel] = Field(
        [], description="data relative to doi entries"
    )
    link_entries: list[LinkEntryModel] = Field(
        [], description="data relative to link entries"
    )

    number_of_subjects: int = Field(
        0,
        description=(
            "Number of unique subjects in this dataset, should match subjects "
            "metadata file."
        ),
    )
    number_of_samples: int = Field(
        0,
        description=(
            "Number of unique samples in this dataset, should match samples metadata "
            "file. Set to zero if there are no samples."
        ),
    )

    # footer in yellow
    completeness_of_dataset: StrictStr = Field(
        "",
        description=(
            "Is the data set as uploaded complete or is it part of an ongoing study. "
            'Use "hasNext" to indicate that you expect more data on different subjects '
            "as a continuation of this study. Use “hasChildren” to indicate that you "
            "expect more data on the same subjects or samples derived from those subjects."
        ),
    )
    parent_dataset_id: StrictStr = Field(
        "",
        description=(
            "If this is a part of a larger data set, or refereces subjects or samples "
            "from a parent dataset, what was the accession number of the prior batch. "
            "You need only give us the number of the last batch, not all batches. If "
            "samples and subjects are from multiple parent datasets please create a "
            "comma separated list of all parent ids."
        ),
    )
    title_for_complete_dataset: StrictStr = Field(
        "", description="Please give us a provisional title for the entire data set."
    )
    metadata_version: StrictStr = Field(
        "1.2.3", description="DO NOT CHANGE, this field is provided other groups"
    )


class SheetFirstDatasetDescription(BaseXLSXSheet):
    name = "Sheet1"
    cell_styles: list[tuple[str, BaseXLSXCellData]] = [
        (
            "A1",
            TB("Metadata element")
            | Comment(
                "This metadata will be made available to the public as soon as the data set it submitted.",
                "M Martone",
            ),
        ),
        ("B1", TB("Description")),
        ("C1", TB("Example")),
        ("A2", TB("Name")),
        (
            "B2",
            T(
                "Descriptive title for the data set. Equivalent to the title of a scientific paper. The metadata associated with the published version of this dataset does not currently make use of this field."
            ),
        ),
        ("C2", T("My SPARC dataset")),
        ("A3", TB("Description")),
        (
            "B3",
            T(
                "NOTE This field is not currently used when publishing a SPARC dataset. Brief description of the study and the data set. Equivalent to the abstract of a scientific paper. Include the rationale for the approach, the types of data collected, the techniques used, formats and number of files and an approximate size. The metadata associated with the published version of this dataset does not currently make use of this field."
            ),
        ),
        ("C3", T("A really cool dataset that I collected to answer some question.")),
        ("A4", TB("Keywords")),
        (
            "B4",
            T("A set of 3-5 keywords other than the above that will aid in search"),
        ),
        ("C4", T("spinal cord, electrophysiology, RNA-seq, mouse")),
        ("A5", TB("Contributors")),
        (
            "B5",
            T(
                "Name of any contributors to the dataset.  These individuals need not have been authors on any publications describing the data, but should be acknowledged for their role in producing and publishing the data set.  If more than one, add each contributor in a new column."
            ),
        ),
        ("C5", T("Last, First Middle")),
        ("A6", TB("Contributor ORCID ID")),
        (
            "B6",
            Link(
                "ORCID ID. If you don't have an ORCID, we suggest you sign up for one.",
                "https://orcid.org/",
            ),
        ),
        ("C6", T("https://orcid.org/0000-0002-5497-0243")),
        ("A7", TB("Contributor Affiliation")),
        ("B7", T("Institutional affiliation for contributors")),
        ("C7", T("https://ror.org/0168r3w48")),
        ("A8", TB("Contributor Role")),
        (
            "B8",
            T(
                "Contributor role, e.g., PrincipleInvestigator, Creator, CoInvestigator, ContactPerson, DataCollector, DataCurator, DataManager, Distributor, Editor, Producer, ProjectLeader, ProjectManager, ProjectMember, RelatedPerson, Researcher, ResearchGroup, Sponsor, Supervisor, WorkPackageLeader, Other.  These roles are provided by the Data Cite schema.  If more than one, add additional columns"
            ),
        ),
        ("C8", T("Data Collector")),
        ("A9", TB("Is Contact Person")),
        (
            "B9",
            T("Yes or No if the contributor is a contact person for the dataset"),
        ),
        ("C9", T("Yes")),
        ("A10", TB("Acknowledgements")),
        ("B10", T("Acknowledgements beyond funding and contributors")),
        ("C10", T("Thank you everyone!")),
        ("A11", TB("Funding")),
        ("B11", T("Funding sources")),
        ("C11", T("OT2OD025349")),
        ("A12", TB("Originating Article DOI")),
        ("B12", T("DOIs of published articles that were generated from this dataset")),
        (
            "C12",
            Link("https://doi.org/10.13003/5jchdy", "https://doi.org/10.13003/5jchdy"),
        ),
        ("A13", TB("Protocol URL or DOI")),
        (
            "B13",
            T(
                "URLs (if still private) / DOIs (if public) of protocols from protocols.io related to this dataset"
            ),
        ),
        # ("C13", T("")),
        ("A14", TB("Additional Links")),
        (
            "B14",
            T(
                "URLs of additional resources used by this dataset (e.g., a link to a code repository)"
            ),
        ),
        (
            "C14",
            Link(
                "https://github.com/myuser/code-for-really-cool-data",
                "https://github.com/myuser/code-for-really-cool-data",
            ),
        ),
        ("A15", TB("Link Description")),
        (
            "B15",
            T(
                "Short description of URL content, you do not need to fill this in for Originating Article DOI or Protocol URL or DOI "
            ),
        ),
        ("C15", T("link to GitHub repository for code used in this study")),
        ("A16", TB("Number of subjects")),
        (
            "B16",
            T(
                "Number of unique subjects in this dataset, should match subjects metadata file."
            ),
        ),
        # ("C16", T("")),
        ("A17", TB("Number of samples")),
        (
            "B17",
            T(
                "Number of unique samples in this dataset, should match samples metadata file. Set to zero if there are no samples."
            ),
        ),
        # ("C17", T("")),
        ("A18", TB("Completeness of data set")),
        (
            "B18",
            T(
                'Is the data set as uploaded complete or is it part of an ongoing study.  Use "hasNext" to indicate that you expect more data on different subjects as a continuation of this study. Use “hasChildren” to indicate that you expect more data on the same subjects or samples derived from those subjects.'
            ),
        ),
        ("C18", T("hasNext, hasChildren")),
        ("A19", TB("Parent dataset ID")),
        (
            "B19",
            T(
                "If this is a part of a larger data set, or refereces subjects or samples from a parent dataset, what was the accession number of the prior batch.  You need only give us the number of the last batch, not all batches. If samples and subjects are from multiple parent datasets please create a comma separated list of all parent ids."
            ),
        ),
        ("C19", T("N:dataset:c5c2f40f-76be-4979-bfc4-b9f9947231cf")),
        ("A20", TB("Title for complete data set")),
        ("B20", T("Please give us a provisional title for the entire data set.")),
        # ("C20", T("ì")),
        ("A21", TB("Metadata Version DO NOT CHANGE")),
        ("B21", T("1.2.3")),
        ("C21", T("1.2.3")),
        ## borders and styles
        ("A1:C1", Backgrounds.blue),
        ("A2:C17", Backgrounds.green),
        ("A18:C21", Backgrounds.yellow_dark),
        ("A1:C21", Borders.medium_grid),
    ]
    column_dimensions = {"A": 30, "B": 55, "C": 40}

    def assemble_data_for_template(
        self, template_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        params: DatasetDescriptionParams = ensure_correct_instance(
            template_data, DatasetDescriptionParams
        )

        # it is important for cells to be added to the list left to right and top to bottom
        # this is done to ensure styling is applied consistently, read more inside xlsx_base
        cells = []

        # assemble "Value x" headers
        max_number_of_headers = max(
            1,
            get_max_array_length(
                params.contributor_entries, params.doi_entries, params.link_entries
            ),
        )

        for k, column_letter in enumerate(column_generator(4, max_number_of_headers)):
            cell_entry = (
                f"{column_letter}1",
                T(f"Value {k + 1}") | Backgrounds.blue | Borders.medium_grid,
            )
            cells.append(cell_entry)

        # first batch of static cells
        static_cells_first_batch = [
            ("D2", T(params.name) | Borders.light_grid),
            ("D3", T(params.description) | Borders.light_grid),
            ("D4", T(params.keywords) | Borders.light_grid),
        ]
        cells.extend(static_cells_first_batch)

        # adding contributors entries horizontally
        contributor_entry: ContributorEntryModel
        for column_letter, contributor_entry in zip(
            column_generator(4, len(params.contributor_entries)),
            params.contributor_entries,
        ):
            cells.append(
                (
                    f"{column_letter}5",
                    T(contributor_entry.contributor) | Borders.light_grid,
                )
            )
            cells.append(
                (
                    f"{column_letter}6",
                    T(contributor_entry.orcid_id) | Borders.light_grid,
                )
            )
            cells.append(
                (
                    f"{column_letter}7",
                    T(contributor_entry.affiliation) | Borders.light_grid,
                )
            )
            cells.append(
                (f"{column_letter}8", T(contributor_entry.role) | Borders.light_grid)
            )
            cells.append(
                (
                    f"{column_letter}9",
                    T(contributor_entry.is_contact_person) | Borders.light_grid,
                )
            )

        # more static fields in the middle
        static_cells_second_batch = [
            ("D10", T(params.acknowledgements) | Borders.light_grid),
            ("D11", T(params.funding) | Borders.light_grid),
        ]
        cells.extend(static_cells_second_batch)

        # adding doi entries horizontally
        doi_entry: DoiEntryModel
        for column_letter, doi_entry in zip(
            column_generator(4, len(params.doi_entries)), params.doi_entries
        ):
            cells.append(
                (
                    f"{column_letter}12",
                    T(doi_entry.originating_article_doi) | Borders.light_grid,
                )
            )
            cells.append(
                (
                    f"{column_letter}13",
                    T(doi_entry.protocol_url_or_doi) | Borders.light_grid,
                )
            )

        # adding link entries horizontally
        link_entry: LinkEntryModel
        for column_letter, link_entry in zip(
            column_generator(4, len(params.link_entries)), params.link_entries
        ):
            cells.append(
                (
                    f"{column_letter}14",
                    T(link_entry.additional_link) | Borders.light_grid,
                )
            )
            cells.append(
                (
                    f"{column_letter}15",
                    T(link_entry.link_description) | Borders.light_grid,
                )
            )

        # last part of static cells
        static_cells_third_batch = [
            ("D16", T(params.number_of_subjects) | Borders.light_grid),
            ("D17", T(params.number_of_samples) | Borders.light_grid),
            ("D18", T(params.completeness_of_dataset) | Borders.light_grid),
            ("D19", T(params.parent_dataset_id) | Borders.light_grid),
            ("D20", T(params.title_for_complete_dataset) | Borders.light_grid),
            ("D21", T(params.metadata_version) | Borders.light_grid),
        ]
        cells.extend(static_cells_third_batch)

        return cells


class DatasetDescriptionXLSXDocument(BaseXLSXDocument):
    file_name = "dataset_description.xlsx"
    sheet1 = SheetFirstDatasetDescription()
