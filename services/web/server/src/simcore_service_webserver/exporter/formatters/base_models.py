from pathlib import Path
from typing import Dict, Any, Union

import aiofiles
import yaml
from aiohttp import web
from pydantic import BaseModel, Field, validator


def dumps(data: Dict) -> str:
    try:
        return yaml.safe_dump(data)
    except yaml.YAMLError:
        web.HTTPException(reason=f"Could not encode into YAML from '{data}'")


def loads(string_data: str) -> Dict:
    try:
        return yaml.safe_load(string_data)
    except yaml.YAMLError:
        web.HTTPException(reason=f"Could not decode YAML from '{string_data}'")


class BaseModelSavePath(BaseModel):
    root_dir: Path = Field(
        ...,
        description="temporary directory where all data is stored, to be ignored from serialization",
    )
    path_in_root_dir: Path = Field(
        ...,
        description="path to the file where to store this model, to be ignored from serialization",
    )

    @validator("root_dir")
    @classmethod
    def _validate_root_dir(cls, v):
        if not isinstance(v, Path):
            v = Path(v)
        if not v.is_dir():
            raise ValueError(f"Provided path {str(v)} is not a directory!")
        return v

    @validator("path_in_root_dir")
    @classmethod
    def _validate_path_in_root_dir(cls, v):
        if not isinstance(v, Path):
            v = Path(v)
        if v.is_absolute():
            raise ValueError(f"Must provide a relative path, not {str(v)}")

        return v

    @property
    def path(self) -> Path:
        return self.root_dir / self.path_in_root_dir

    def is_store_path_present(self) -> bool:
        """Used to check if the file is present in the expected location"""
        return self.path.is_file()

    async def data_from_file(self) -> Dict:
        async with aiofiles.open(self.path, "r") as input_file:
            return loads(await input_file.read())

    async def data_to_file(self, payload: str) -> None:
        async with aiofiles.open(self.path, "w") as output_file:
            await output_file.write(dumps(payload))


class BaseLoadingModel(BaseModel):
    """Used as base for all models which need to be validated to a file"""

    _STORAGE_PATH: Union[str, Path] = ""

    storage_path: BaseModelSavePath = Field(
        ..., description="Where the file is peristed or from where is loaded"
    )

    @classmethod
    def validate_storage_path(cls):
        if any(
            [
                cls._STORAGE_PATH is None,
                cls._STORAGE_PATH == "",
                not isinstance(cls._STORAGE_PATH, (str, Path)),
            ]
        ):
            message = (
                f"Class {cls.__name__} must implement '_STORAGE_PATH: Union[str, Path]' "
                f"instead of value={cls._STORAGE_PATH}, type={type(cls._STORAGE_PATH)}"
            )
            raise ValueError(message)

    @classmethod
    async def model_from_file(cls, root_dir: Path) -> "Manifest":
        """Used to validate a model from an existing file"""
        cls.validate_storage_path()

        storage_path_dict = dict(root_dir=root_dir, path_in_root_dir=cls._STORAGE_PATH)
        storage_path = BaseModelSavePath(**storage_path_dict)

        dict_data = await storage_path.data_from_file()
        dict_data["storage_path"] = storage_path_dict

        return cls.parse_obj(dict_data)

    @classmethod
    async def model_to_file(cls, root_dir: Path, **kwargs: Dict[str, Any]) -> None:
        """Used to generate an existing model from a file"""
        cls.validate_storage_path()

        manifest_obj = cls.parse_obj(
            dict(
                **kwargs,
                storage_path=dict(
                    root_dir=root_dir, path_in_root_dir=cls._STORAGE_PATH
                ),
            )
        )
        to_store = manifest_obj.dict(exclude={"storage_path"}, by_alias=True)
        await manifest_obj.storage_path.data_to_file(to_store)
        return manifest_obj
