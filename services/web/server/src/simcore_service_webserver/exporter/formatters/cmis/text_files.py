from typing import Union
from pathlib import Path


class BaseTextFile:
    def _check_attribute(self, attribute_name: str):
        if getattr(self, attribute_name) is None:
            raise ValueError(f"'{attribute_name}' attribute is None, please define it")

    def __init__(self, path: Union[str, Path] = None, text: str = None):
        # gather all class attributes
        # a class attribute is considered a member not starting with "__" or "_"
        for name, value in vars(self.__class__).items():
            if name.startswith("__") or name.startswith("_"):
                continue
            self.__setattr__(name, value)

        self.path = self.__getattribute__("path") if path is None else path
        self.text = self.__getattribute__("text") if text is None else text

        # check mandatory fields are present
        self._check_attribute("path")
        self._check_attribute("text")

    def store_in_base_path(self, base_path: Path) -> None:
        destination = base_path / Path(self.path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.text)


class ChangesFile(BaseTextFile):
    path = "CHANGES"
    text = (
        "Optional text file that contains information about the "
        "history of the dataset"
    )


class ReadmeRootLevelFile(BaseTextFile):
    path = "README"
    text = ""


class ReadmeCodeFolderFile(BaseTextFile):
    path = "code/README"
    text = "Optional folder meant to contain any supporting code"


class ReadmeDerivativeFolderFile(BaseTextFile):
    path = "derivative/README"
    text = (
        "Optional folder that contains data derived from the data in "
        "the primary data folder or using the code in the code folder."
    )


class ReadmeDocsFolderFile(BaseTextFile):
    path = "docs/README"
    text = (
        "Optional folder that contains data derived from the data in "
        "the primary data folder or using the code in the code folder."
    )


def write_text_files(base_path: Path) -> None:
    """Assembles and writes all the text files required by the standard"""
    text_files_to_store = [
        ChangesFile(),
        ReadmeRootLevelFile(),
        ReadmeCodeFolderFile(),
        ReadmeDerivativeFolderFile(),
        ReadmeDocsFolderFile(),
    ]
    for text_file in text_files_to_store:
        text_file.store_in_base_path(base_path)
