from typing import List, Tuple, Dict
from simcore_service_webserver.exporter.formatters.xlsx.xlsx_base import (
    BaseXLSXCellData,
    BaseXLSXSheet,
    BaseXLSXDocument,
)
from simcore_service_webserver.exporter.formatters.xlsx.styling_components import (
    T,
    TB,
    Backgrounds,
    Borders,
)


class SheetFirstDatasetDescription(BaseXLSXSheet):
    name = "Sheet1"
    cell_styles = []
    column_dimensions = {}


class DatasetDescriptionXLSXDocument(BaseXLSXDocument):
    sheet1 = SheetFirstDatasetDescription()
