from pathlib import Path

import pytest
from pytest_simcore.k8s_cluster import _find_k8s_dir


def test_find_k8s_dir_walks_up_to_the_repo_root(tmp_path: Path):
    (tmp_path / "k8s").mkdir()
    (tmp_path / "k8s" / "Makefile").touch()
    package_dir = tmp_path / "packages" / "postgres-database"
    package_dir.mkdir(parents=True)

    assert _find_k8s_dir(package_dir) == tmp_path / "k8s"


def test_find_k8s_dir_fails_outside_the_repo(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        _find_k8s_dir(tmp_path)
