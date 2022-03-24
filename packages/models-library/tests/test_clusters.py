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
        example.get("access_rights", {}).pop(owner_gid, None)

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
