import os
from pathlib import Path
from typing import Any, Dict


class DynamicSidecarVolumesPathsResolver:
    BASE_PATH: str = "/dy-volumes"

    @classmethod
    def _name_from_path(cls, path: Path) -> str:
        return str(path).replace(os.sep, "_")

    @classmethod
    def _target(cls, state_path: Path) -> str:
        return f"{cls.BASE_PATH}/{cls._name_from_path(state_path).strip('_')}"

    @classmethod
    def _source(cls, compose_namespace: str, state_path: Path) -> str:
        return f"{compose_namespace}{cls._name_from_path(state_path)}"

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
