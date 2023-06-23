import os
from pathlib import Path
from typing import Final
from uuid import UUID

from attr import dataclass
from pydantic import PositiveInt

from .docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES

_UUID_LEN: Final[PositiveInt] = 36
_UNDER_SCORE_LEN: Final[PositiveInt] = 1
REGULAR_SOURCE_PORTION_LEN: Final[PositiveInt] = (
    len(PREFIX_DYNAMIC_SIDECAR_VOLUMES) + 2 * _UUID_LEN + 3 * _UNDER_SCORE_LEN
)

STORE_FILE_NAME: Final[str] = "data.json"


@dataclass
class VolumeInfo:
    node_uuid: UUID
    run_id: UUID
    possible_volume_name: str


class VolumeUtils:
    _MAX_VOLUME_NAME_LEN: Final[int] = 255

    @classmethod
    def get_name(cls, path: Path) -> str:
        return f"{path}".replace(os.sep, "_")

    @classmethod
    def get_source(cls, path: Path, node_uuid: UUID, run_id: UUID) -> str:
        """Returns a valid and unique volume name that is composed out of identifiers, namely
            - relative target path
            - node_uuid
            - run_id

        Guarantees that the volume name is unique between runs while also
        taking into consideration the limit for the volume name's length
        (255 characters).

        SEE examples in `tests/unit/test_modules_dynamic_sidecar_volumes_resolver.py`
        """
        # NOTE: issues can occur when the paths of the mounted outputs, inputs
        # and state folders are very long and share the same subdirectory path.
        # Reversing volume name to prevent these issues from happening.
        reversed_volume_name = cls.get_name(path)[::-1]
        unique_name = f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_{run_id}_{node_uuid}_{reversed_volume_name}"
        return unique_name[: cls._MAX_VOLUME_NAME_LEN]

    @classmethod
    def get_volume_info(cls, source: str) -> VolumeInfo:
        print(f"{source=}")
        if len(source) <= REGULAR_SOURCE_PORTION_LEN:
            raise ValueError(
                f"source '{source}' must be at least {REGULAR_SOURCE_PORTION_LEN} characters"
            )

        # example: dyv_5813058f-8ec4-4aa9-bae1-f46c01040481_e3d42f3f-e1ad-418b-90e1-c44a95e97b91
        without_volume_name = source[: REGULAR_SOURCE_PORTION_LEN - 1]

        # example:_erots_pmet_
        possible_reverted_volume_name = source[REGULAR_SOURCE_PORTION_LEN:]

        _, run_id_str, node_uuid_str = without_volume_name.split("_")
        possible_volume_name = possible_reverted_volume_name[::-1]

        return VolumeInfo(
            node_uuid=UUID(node_uuid_str),
            run_id=UUID(run_id_str),
            possible_volume_name=possible_volume_name,
        )
