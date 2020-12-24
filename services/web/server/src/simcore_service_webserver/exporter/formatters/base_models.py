from pathlib import Path
from typing import Dict, Any, Union

import aiofiles
from pydantic import BaseModel, Field, validator


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
        return self.path.exists()

    async def data_from_file(self) -> str:
        async with aiofiles.open(self.path, "r") as input_file:
            return await input_file.read()

    async def data_to_file(self, payload: str) -> None:
        async with aiofiles.open(self.path, "w") as output_file:
            await output_file.write(payload)


class BaseLoadingModel(BaseModel):
    """Used as base for all models which need to be validated to a file"""

    _STORAGE_PATH: Union[str, Path] = ""

    storage_path: BaseModelSavePath = Field(
        None, description="Where the file is peristed or from where is loaded"
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

        storage_path = BaseModelSavePath(
            root_dir=root_dir, path_in_root_dir=cls._STORAGE_PATH
        )

        stored_data = await storage_path.data_from_file()
        new_obj = cls.parse_raw(stored_data)
        new_obj.storage_path = storage_path
        return new_obj

    @classmethod
    async def model_to_file(cls, root_dir: Path, **kwargs: Dict[str, Any]) -> None:
        """Used to generate an existing model from a file"""
        cls.validate_storage_path()

        model_obj = cls.parse_obj(
            dict(
                **kwargs,
                storage_path=dict(
                    root_dir=root_dir, path_in_root_dir=cls._STORAGE_PATH
                ),
            )
        )
        to_store = model_obj.json(exclude={"storage_path"}, by_alias=True)
        await model_obj.storage_path.data_to_file(to_store)
        return model_obj
