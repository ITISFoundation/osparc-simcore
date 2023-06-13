import datetime
from collections import deque
from pathlib import Path
from typing import Iterable

import magic
from pydantic import BaseModel, Field, StrictStr, validator

from .core.styling_components import TB, Backgrounds, Borders, T
from .core.xlsx_base import BaseXLSXCellData, BaseXLSXDocument, BaseXLSXSheet
from .utils import column_generator, ensure_correct_instance, get_max_array_length

# replaces lib-magic's description with these
DESCRIPTION_OVERWRITES: dict[str, str] = {
    "project.json": "serialized pipeline service list and connections",
    "README": "file containing information on this directory's content",
}


def _get_files_in_dir(dir_path: Path) -> Iterable[tuple[Path, str]]:
    str_dir_path = str(dir_path) + "/"
    for entry in dir_path.rglob("*"):
        if entry.is_file():
            relative_file_name = str(entry).replace(str_dir_path, "")
            yield (entry, relative_file_name)


class FileEntryModel(BaseModel):
    filename: StrictStr = Field(..., description="name of the file")
    timestamp: datetime.datetime = Field(..., description="last change time stamp")
    description: StrictStr = Field("", description="additional information on the file")
    file_type: StrictStr = Field(..., description="mime type of the file")

    additional_metadata: list[StrictStr] = Field(
        [], description="optional field containing Additional metadata fields the file"
    )

    # pylint: disable=unused-argument
    @validator("timestamp")
    @classmethod
    def format_timestamp(cls, v, values):
        return v.strftime("%A %d. %B %Y")


class DirectoryManifestParams(BaseModel):
    file_entries: list[FileEntryModel] = Field(description="list of file entries")

    @classmethod
    def compose_from_directory(cls, start_path: Path) -> "DirectoryManifestParams":
        file_entries: deque[FileEntryModel] = deque()
        for file_entry in _get_files_in_dir(start_path):
            full_file_path, relative_file_name = file_entry
            last_modified_date = datetime.datetime.fromtimestamp(
                full_file_path.stat().st_mtime
            )
            description = (
                DESCRIPTION_OVERWRITES[relative_file_name]
                if relative_file_name in DESCRIPTION_OVERWRITES
                else magic.from_file(str(full_file_path))
            )
            str_full_file_path = str(full_file_path)
            file_type = (
                str_full_file_path.split(".")[-1] if "." in str_full_file_path else ""
            )

            file_entry_model = FileEntryModel(
                filename=relative_file_name,
                timestamp=last_modified_date,
                description=description,
                file_type=file_type,
            )

            file_entries.append(file_entry_model)

        return cls(file_entries=list(file_entries))


class SheetFirstDirectoryManifest(BaseXLSXSheet):
    name = "Sheet1"
    cell_styles = [
        ("A1", TB("filename") | Backgrounds.blue | Borders.light_grid),
        ("B1", TB("timestamp") | Backgrounds.blue | Borders.light_grid),
        ("C1", TB("description") | Backgrounds.blue | Borders.light_grid),
        ("D1", TB("file type") | Backgrounds.blue | Borders.light_grid),
    ]
    column_dimensions = {"A": 15, "B": 40, "C": 25, "D": 10}

    def assemble_data_for_template(
        self, template_data: BaseModel
    ) -> list[tuple[str, BaseXLSXCellData]]:
        params: DirectoryManifestParams = ensure_correct_instance(
            template_data, DirectoryManifestParams
        )
        file_entries: list[FileEntryModel] = params.file_entries

        # it is important for cells to be added to the list left to right and top to bottom
        # this is done to ensure styling is applied consistently, read more inside xlsx_base
        cells: deque[tuple[str, BaseXLSXCellData]] = deque()

        # assemble "Additional Metadata x" headers
        # if file_entries is empty this would max function to fail, always concatenate an
        not_empty_file_entries = [x.additional_metadata for x in file_entries] + [[]]
        max_number_of_headers = get_max_array_length(*not_empty_file_entries)
        for k, column_letter in enumerate(column_generator(5, max_number_of_headers)):
            cell_entry = (
                f"{column_letter}1",
                T(f"Additional Metadata {k + 1}")
                | Backgrounds.yellow_dark
                | Borders.light_grid,
            )
            cells.append(cell_entry)

        file_entry: FileEntryModel
        for row_index, file_entry in zip(range(2, len(file_entries) + 2), file_entries):
            cells.append((f"A{row_index}", T(file_entry.filename) | Borders.light_grid))
            cells.append(
                (f"B{row_index}", T(f"{file_entry.timestamp}") | Borders.light_grid)
            )
            cells.append(
                (f"C{row_index}", T(file_entry.description) | Borders.light_grid)
            )
            cells.append(
                (f"D{row_index}", T(file_entry.file_type) | Borders.light_grid)
            )

            # write additional metadata for each file
            for column_letter, additional_metadata_entry in zip(
                column_generator(5, max_number_of_headers),
                file_entry.additional_metadata,
            ):
                cell_entry = (
                    f"{column_letter}{row_index}",
                    T(additional_metadata_entry) | Borders.light_grid,
                )
                cells.append(cell_entry)

        return list(cells)


class DirectoryManifestXLSXDocument(BaseXLSXDocument):
    file_name = "manifest.xlsx"
    sheet1 = SheetFirstDirectoryManifest()
