import os
from pathlib import Path
from typing import Any, Dict


class DynamicSidecarVolumesPathsResolver:
    BASE_PATH: Path = Path("/dy-volumes")

    @classmethod
    def _target(cls, state_path: Path) -> str:
        target_path = cls.BASE_PATH / state_path.relative_to("/")
        return f"{target_path}"

    @classmethod
    def _source(cls, compose_namespace: str, state_path: Path) -> str:
        volume_name = f"{state_path}".replace(os.sep, "_")
        return f"{compose_namespace}{volume_name}"

    @classmethod
    def mount_entry(
        cls, compose_namespace: str, state_path: Path, node_uuid: str
    ) -> Dict[str, Any]:
        return {
            "Source": cls._source(compose_namespace, state_path),
            "Target": cls._target(state_path),
            "Type": "volume",
            "VolumeOptions": {"Labels": {"uuid": f"{node_uuid}"}},
        }
