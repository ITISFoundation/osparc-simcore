from pprint import pformat
from typing import Any, Dict, Type

import pytest
from pydantic import BaseModel, ValidationError
from simcore_service_webserver.clusters.models import (
    CLUSTER_MANAGER_RIGHTS,
    CLUSTER_USER_RIGHTS,
    Cluster,
)


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_clusters_model_examples(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_cluster_fails_when_owner_is_not_present(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
):
    for example in model_cls_examples.values():
        owner_gid = example["owner"]
        # remove the owner from the access rights
        example["access_rights"].pop(owner_gid)
        with pytest.raises(ValidationError):
            model_cls(**example)


@pytest.mark.parametrize(
    "model_cls",
    (Cluster,),
)
def test_cluster_fails_when_owner_has_no_admin_rights(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
):
    for example in model_cls_examples.values():
        owner_gid = example["owner"]
        # set the owner with manager rights
        example["access_rights"][owner_gid] = CLUSTER_MANAGER_RIGHTS
        with pytest.raises(ValidationError):
            model_cls(**example)

        # set the owner with user rights
        example["access_rights"][owner_gid] = CLUSTER_USER_RIGHTS
        with pytest.raises(ValidationError):
            model_cls(**example)
