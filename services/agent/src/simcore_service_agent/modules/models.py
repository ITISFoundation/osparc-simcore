from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, TypeAlias

from servicelib.sidecar_volumes import REGULAR_SOURCE_PORTION_LEN, VolumeUtils

SHARED_STORE_PATH = Path("/dy-volumes/shared-store")

VolumeDict: TypeAlias = dict[str, Any]


@dataclass
class SidecarVolumes:
    store_volume: VolumeDict
    remaining_volumes: list[VolumeDict]

    @classmethod
    def from_volumes(cls, volumes: Iterable[VolumeDict]) -> "SidecarVolumes":
        volumes_common_part: set[str] = {
            v["Name"][:REGULAR_SOURCE_PORTION_LEN] for v in volumes
        }
        if len(volumes_common_part) != 1:
            raise ValueError(f"Volumes do not share the same common part: {volumes=}")

        params = {"store_volume": None, "remaining_volumes": []}

        for volume in volumes:
            reverted_possible_volume_name = volume["Name"][78:]
            possible_volume_name = reverted_possible_volume_name[::-1]
            if possible_volume_name == VolumeUtils.get_name(SHARED_STORE_PATH):
                params["store_volume"] = volume
            else:
                params["remaining_volumes"].append(volume)

        if params["store_volume"] is None:
            raise ValueError(f"No 'store_volume' detected in {volumes=}")

        return cls(**params)

    def __str__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"store_volume={self.store_volume['Name']}, "
            f"remaining_volumes={[v['Name'] for v in self.remaining_volumes]}>"
        )
