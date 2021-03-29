import datetime

from collections import deque
from typing import List, Tuple, Dict
from pathlib import Path

from pydantic import BaseModel, Field, StrictStr

from ..xlsx_base import BaseXLSXCellData, BaseXLSXSheet, BaseXLSXDocument
from ..styling_components import T, TB, Backgrounds, Borders
from .utils import ensure_correct_instance, get_max_array_length, column_iter


def get_files_in_dir(dir_path: Path) -> List[Tuple[Path, str]]:
    str_dir_path = str(dir_path) + "/"
    for entry in dir_path.rglob("*"):
        if entry.is_file():
            relative_file_name = str(entry).replace(str_dir_path, "")
            yield (entry, relative_file_name)


class FileEntryModel(BaseModel):
    filename: StrictStr = Field(..., description="name of the file")
    timestamp: StrictStr = Field(..., description="last change time stamp")
    description: StrictStr = Field("", description="additional information on the file")
    file_type: StrictStr = Field(..., description="mime type of the file")

    additional_metadata: List[StrictStr] = Field(
        [], description="optional field containing Additional metadata fields the file"
    )


class DirectoryManifestParams(BaseModel):
    file_entries: List[FileEntryModel] = Field(description="list of file entries")

    @classmethod
    def compose_from_directory(
        cls, start_path: Path
    ) -> List["DirectoryManifestParams"]:
        import magic  # avoids an issue with a dependency in all [sys] testing cases

        file_entries = deque()
        for file_entry in get_files_in_dir(start_path):
            full_file_path, relative_file_name = file_entry
            last_modified_date = datetime.datetime.fromtimestamp(
                full_file_path.stat().st_mtime
            )
            description = magic.from_file(str(full_file_path))
            str_full_file_path = str(full_file_path)
            file_type = (
                str_full_file_path.split(".")[-1] if "." in str_full_file_path else ""
            )

            file_entry_model = FileEntryModel(
                filename=relative_file_name,
                timestamp=last_modified_date.strftime("%A %d. %B %Y"),
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
    ) -> List[Tuple[str, Dict[str, BaseXLSXCellData]]]:
        params: DirectoryManifestParams = ensure_correct_instance(
            template_data, DirectoryManifestParams
        )
        file_entries: List[FileEntryModel] = params.file_entries

        # it is important for cells to be added to the list left to right and top to bottom
        # this is done to ensure styling is applied consistently, read more inside xlsx_base
        cells = deque()

        # assemble "Additional Metadata x" headers
        # if file_entries is empty this would max function to fail, always concatenate an
        not_empty_file_entries = [x.additional_metadata for x in file_entries] + [[]]
        max_number_of_headers = get_max_array_length(*not_empty_file_entries)
        for k, column_letter in enumerate(column_iter(5, max_number_of_headers)):
            cell_entry = (
                f"{column_letter}1",
                T(f"Additional Metadata {k + 1}")
                | Backgrounds.yellow_dark
                | Borders.light_grid,
            )
            cells.append(cell_entry)

        for row_index, file_entry in zip(range(2, len(file_entries) + 2), file_entries):
            file_entry: FileEntryModel = file_entry

            cells.append((f"A{row_index}", T(file_entry.filename) | Borders.light_grid))
            cells.append(
                (f"B{row_index}", T(file_entry.timestamp) | Borders.light_grid)
            )
            cells.append(
                (f"C{row_index}", T(file_entry.description) | Borders.light_grid)
            )
            cells.append(
                (f"D{row_index}", T(file_entry.file_type) | Borders.light_grid)
            )

            # write additional metadata for each file
            for column_letter, additional_metadata_entry in zip(
                column_iter(5, max_number_of_headers), file_entry.additional_metadata
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
