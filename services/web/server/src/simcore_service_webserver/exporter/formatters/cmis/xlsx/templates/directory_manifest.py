from simcore_service_webserver.exporter.formatters.cmis.xlsx.xlsx_base import (
    BaseXLSXSheet,
    BaseXLSXDocument,
)
from simcore_service_webserver.exporter.formatters.cmis.xlsx.styling_components import (
    TB,
    Backgrounds,
    Borders,
)


class SheetFirstDirectoryManifest(BaseXLSXSheet):
    name = "Sheet1"
    cell_styles = [
        ("A1", TB("filename") | Backgrounds.blue | Borders.light_grid),
        ("B1", TB("timestamp") | Backgrounds.blue | Borders.light_grid),
        ("C1", TB("description") | Backgrounds.blue | Borders.light_grid),
        ("D1", TB("file type") | Backgrounds.blue | Borders.light_grid),
        *[
            (
                f"{chr(ord('E')+i)}1",
                TB("Additional Metadata")
                | Backgrounds.yellow_dark
                | Borders.light_grid,
            )
            for i in range(12)
        ],
    ]
    column_dimensions = {"A": 15, "B": 40, "C": 25, "D": 10}


class DirectoryManifestXLSXDocument(BaseXLSXDocument):
    file_name = "manifest.xlsx"
    sheet1 = SheetFirstDirectoryManifest()
