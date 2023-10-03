from openpyxl.comments import Comment as PyXLComment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.styles.borders import BORDER_MEDIUM, BORDER_THIN

from .xlsx_base import BaseXLSXCellData

COLOR_BLACK = "FF000000"
COLOR_GRAY = "FFC9C9C9"
COLOR_GRAY_BACKGROUND = "D0D0D0"
COLOR_LINK = "0563C1"
COLOR_BLUE = "8CB3DF"
COLOR_GREEN = "99C87B"
COLOR_GREEN_LIGHT = "BBDAA5"
COLOR_YELLOW = "FEE288"
COLOR_YELLOW_DARK = "FFD254"


class T(BaseXLSXCellData):
    """Helper for inputing text into cells"""

    alignment = Alignment(wrap_text=True)

    def __init__(self, text: str | int | float | None):
        # when text is none write emptystring
        super().__init__(value="" if text is None else text)


class TB(T):
    font = Font(bold=True)


class Comment(BaseXLSXCellData):
    """Used to insert a commnet in a cell"""

    def __init__(self, text: str, author: str, height: int = 100, width: int = 150):
        text += f"\n - {author}"
        super().__init__(
            comment=PyXLComment(text=text, author=author, height=height, width=width)
        )


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
    green_light = BackgroundWithColor(color=COLOR_GREEN_LIGHT)
    yellow = BackgroundWithColor(color=COLOR_YELLOW)
    yellow_dark = BackgroundWithColor(color=COLOR_YELLOW_DARK)
    gray_background = BackgroundWithColor(color=COLOR_GRAY_BACKGROUND)


class BorderWithStyle(BaseXLSXCellData):
    """Base for creating custom borders"""

    def __init__(self, *borders_sides, border_style: str, color: str):
        side = Side(border_style=border_style, color=color)
        super().__init__(border=Border(**{x: side for x in borders_sides}))


def _all_borders() -> list[str]:
    return ["top", "left", "right", "bottom", "outline", "vertical", "horizontal"]


class Borders:
    """Collector for different border styles"""

    light_grid = BorderWithStyle(
        *_all_borders(), border_style=BORDER_THIN, color=COLOR_GRAY
    )

    medium_grid = BorderWithStyle(
        *_all_borders(), border_style=BORDER_THIN, color=COLOR_BLACK
    )

    bold_grid = BorderWithStyle(
        *_all_borders(), border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )

    border_bottom_thick = BorderWithStyle(
        "bottom", border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )
    border_top_thick = BorderWithStyle(
        "top", border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )
    border_left_thick = BorderWithStyle(
        "left", border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )
    border_right_thick = BorderWithStyle(
        "right", border_style=BORDER_MEDIUM, color=COLOR_BLACK
    )

    border_bottom_light = BorderWithStyle(
        "bottom", border_style=BORDER_THIN, color=COLOR_BLACK
    )
    border_bottom_medium = BorderWithStyle(
        "bottom", border_style=BORDER_THIN, color=COLOR_BLACK
    )
    border_top_light = BorderWithStyle(
        "top", border_style=BORDER_THIN, color=COLOR_BLACK
    )
    border_left_light = BorderWithStyle(
        "left", border_style=BORDER_THIN, color=COLOR_BLACK
    )
    border_right_light = BorderWithStyle(
        "right", border_style=BORDER_THIN, color=COLOR_BLACK
    )


class AllignTopCenter(BaseXLSXCellData):
    alignment = Alignment(horizontal="center", vertical="top")


class AllignTop(BaseXLSXCellData):
    alignment = Alignment(vertical="top")
