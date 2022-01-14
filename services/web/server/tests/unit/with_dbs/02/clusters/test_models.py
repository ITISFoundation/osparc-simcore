from pprint import pformat
from typing import Any, Dict, Type

import pytest
from pydantic import BaseModel
from simcore_service_webserver.clusters.models import ClusterCreate


@pytest.mark.parametrize(
    "model_cls",
    [(ClusterCreate)],
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
    [(ClusterCreate)],
)
def test_cluster_creation_brings_default_thumbail(
    model_cls: Type[BaseModel], model_cls_examples: Dict[str, Dict[str, Any]]
):
    for example in model_cls_examples.values():
        if "thumbnail" in example:
            example.pop("thumbnail")
        instance = model_cls(**example)
        assert instance
        assert instance.thumbnail
