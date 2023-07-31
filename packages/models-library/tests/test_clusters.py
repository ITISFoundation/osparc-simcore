from copy import deepcopy
from typing import Any

import pytest
from faker import Faker
from models_library.clusters import (
    CLUSTER_ADMIN_RIGHTS,
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_USER_RIGHTS,
    DEFAULT_CLUSTER_ID,
    Cluster,
)
from pydantic import BaseModel, ValidationError


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_cluster_access_rights_correctly_created_when_owner_access_rights_not_present(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for example in model_cls_examples.values():
        modified_example = deepcopy(example)
        owner_gid = modified_example["owner"]
        # remove the owner from the access rights if any
        modified_example.get("access_rights", {}).pop(owner_gid, None)

        instance = model_cls(**modified_example)
        if instance.id != DEFAULT_CLUSTER_ID:
            assert instance.access_rights[owner_gid] == CLUSTER_ADMIN_RIGHTS  # type: ignore
        else:
            assert instance.access_rights[owner_gid] == CLUSTER_USER_RIGHTS  # type: ignore


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_cluster_fails_when_owner_has_no_admin_rights_unless_default_cluster(
    model_cls: type[BaseModel],
    model_cls_examples: dict[str, dict[str, Any]],
    faker: Faker,
):
    for example in model_cls_examples.values():
        modified_example = deepcopy(example)
        modified_example["id"] = faker.pyint(min_value=1)
        owner_gid = modified_example["owner"]
        # ensure there are access rights
        modified_example.setdefault("access_rights", {})
        # set the owner with manager rights
        modified_example["access_rights"][owner_gid] = CLUSTER_MANAGER_RIGHTS
        with pytest.raises(ValidationError):
            model_cls(**modified_example)

        # set the owner with user rights
        modified_example["access_rights"][owner_gid] = CLUSTER_USER_RIGHTS
        with pytest.raises(ValidationError):
            model_cls(**modified_example)


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_cluster_fails_when_owner_has_no_user_rights_if_default_cluster(
    model_cls: type[BaseModel],
    model_cls_examples: dict[str, dict[str, Any]],
):
    for example in model_cls_examples.values():
        modified_example = deepcopy(example)
        modified_example["id"] = DEFAULT_CLUSTER_ID
        owner_gid = modified_example["owner"]
        # ensure there are access rights
        modified_example.setdefault("access_rights", {})
        # set the owner with manager rights
        modified_example["access_rights"][owner_gid] = CLUSTER_MANAGER_RIGHTS
        with pytest.raises(ValidationError):
            model_cls(**modified_example)

        # set the owner with user rights
        modified_example["access_rights"][owner_gid] = CLUSTER_ADMIN_RIGHTS
        with pytest.raises(ValidationError):
            model_cls(**modified_example)
