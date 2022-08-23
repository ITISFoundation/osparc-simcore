from pathlib import Path
from typing import Union

from pydantic import BaseModel, Field


class BaseTextFile(BaseModel):
    path: Union[str, Path] = Field(
        ..., description="relative path where to store this file"
    )
    text: str = Field(..., description="contens of the text file")

    def store_in_base_path(self, base_path: Path) -> None:
        destination = base_path / Path(self.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.text)


CHANGES_FILE = BaseTextFile(
    path="CHANGES",
    text=(
        "Optional text file that contains information about the "
        "history of the dataset"
    ),
)

README_ROOT_LEVEL_FILE = BaseTextFile(
    path="README",
    text="",
)
README_CODE_FOLDER_FILE = BaseTextFile(
    path="code/README",
    text="Optional folder meant to contain any supporting code",
)

README_DERIVATIVE_FOLDER_FILE = BaseTextFile(
    path="derivative/README",
    text=(
        "Optional folder that contains data derived from the data in "
        "the primary data folder or using the code in the code folder."
    ),
)

README_DOCS_FOLDER_FILE = BaseTextFile(
    path="docs/README",
    text=(
        "Optional folder that contains data derived from the data in "
        "the primary data folder or using the code in the code folder."
    ),
)


def write_text_files(base_path: Path) -> None:
    """Assembles and writes all the text files required by the standard"""
    text_files_to_store = [
        CHANGES_FILE,
        README_ROOT_LEVEL_FILE,
        README_CODE_FOLDER_FILE,
        README_DERIVATIVE_FOLDER_FILE,
        README_DOCS_FOLDER_FILE,
    ]
    for text_file in text_files_to_store:
        text_file.store_in_base_path(base_path)
