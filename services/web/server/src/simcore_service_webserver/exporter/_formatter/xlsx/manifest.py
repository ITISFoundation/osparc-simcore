from typing import ClassVar

from .core.styling_components import TB, Backgrounds, Borders
from .core.xlsx_base import BaseXLSXCellData, BaseXLSXDocument, BaseXLSXSheet


class Sheet1Manifest(BaseXLSXSheet):
    name = "Sheet1"
    cell_styles: ClassVar[list[tuple[str, BaseXLSXCellData]]] = [
        # header
        ("A1", TB("filename") | Backgrounds.blue | Borders.light_grid),
        ("B1", TB("timestamp") | Backgrounds.green_light | Borders.light_grid),
        ("C1", TB("description") | Backgrounds.green_light | Borders.light_grid),
        ("D1", TB("file type") | Backgrounds.green_light | Borders.light_grid),
        ("E1", TB("Additional Metadata") | Backgrounds.yellow | Borders.light_grid),
        # entry
        ("A2", TB("template.json")),
        (
            "C2",
            TB(
                "Configuration file to view and run the simulation on the oSPARC platform"
            ),
        ),
    ]
    column_dimensions: ClassVar[dict[str, int]] = {
        "A": 15,
        "B": 15,
        "C": 55,
        "D": 10,
        "E": 15,
    }


class ManifestXLSXDocument(BaseXLSXDocument):
    file_name = "manifest.xlsx"
    sheet1 = Sheet1Manifest()
