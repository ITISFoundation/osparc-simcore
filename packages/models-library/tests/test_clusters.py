from contextlib import suppress
from typing import Any, Dict, Type

import pytest
from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_USER_RIGHTS,
    Cluster,
)
from pydantic import BaseModel, ValidationError


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_cluster_access_rights_correctly_created_when_owner_access_rights_not_present(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
):
    for example in model_cls_examples.values():
        owner_gid = example["owner"]
        # remove the owner from the access rights if any
        with suppress(KeyError):
            example.get("access_rights", {}).pop(owner_gid)

        instance = model_cls(**example)
        assert instance.access_rights[owner_gid] == CLUSTER_ADMIN_RIGHTS  # type: ignore


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_cluster_fails_when_owner_has_no_admin_rights(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
):
    for example in model_cls_examples.values():
        owner_gid = example["owner"]
        # ensure there are access rights
        example.setdefault("access_rights", {})
        # set the owner with manager rights
        example["access_rights"][owner_gid] = CLUSTER_MANAGER_RIGHTS
        with pytest.raises(ValidationError):
            model_cls(**example)

        # set the owner with user rights
        example["access_rights"][owner_gid] = CLUSTER_USER_RIGHTS
        with pytest.raises(ValidationError):
            model_cls(**example)


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_export_clusters_to_db(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
):
    for example in model_cls_examples.values():
        owner_gid = example["owner"]
        # remove the owner from the access rights if any
        with suppress(KeyError):
            example.get("access_rights", {}).pop(owner_gid)
        instance = model_cls(**example)

        # for inserts
        cluster_db_dict = instance.to_clusters_db(only_update=True)
        keys_not_in_db = ["id", "access_rights"]

        assert list(cluster_db_dict.keys()) == [
            x for x in example if x not in keys_not_in_db
        ]
