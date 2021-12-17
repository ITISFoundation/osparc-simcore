import os
from pathlib import Path
from typing import Any, Dict


class DynamicSidecarVolumesPathsResolver:
    BASE_PATH: Path = Path("/dy-volumes")

    @classmethod
    def target(cls, path: Path) -> str:
        """returns path relative to `/dy-volumes`"""
        target_path = cls.BASE_PATH / path.relative_to("/")
        return f"{target_path}"

    @classmethod
    def _source(cls, compose_namespace: str, path: Path) -> str:
        volume_name = f"{path}".replace(os.sep, "_")
        return f"{compose_namespace}{volume_name}"

    @classmethod
    def mount_entry(
        cls, compose_namespace: str, path: Path, node_uuid: str
    ) -> Dict[str, Any]:
        return {
            "Source": cls._source(compose_namespace, path),
            "Target": cls.target(path),
            "Type": "volume",
            "VolumeOptions": {"Labels": {"uuid": f"{node_uuid}"}},
        }
