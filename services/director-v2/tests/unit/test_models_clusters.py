from pprint import pformat
from typing import Any, Dict, Type

import pytest
from faker import Faker
from pydantic import BaseModel
from simcore_service_director_v2.models.schemas.clusters import (
    ClusterCreate,
    ClusterPatch,
    Scheduler,
    Worker,
    WorkersDict,
)


@pytest.mark.parametrize(
    "model_cls",
    [ClusterCreate, ClusterPatch],
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
    [
        ClusterCreate,
    ],
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


def test_scheduler_constructor_with_default_has_correct_dict(faker: Faker):
    scheduler = Scheduler(status=faker.text())
    assert isinstance(scheduler.workers, WorkersDict)
    assert len(scheduler.workers) == 0


def test_scheduler_constructor_with_no_workers_has_correct_dict(faker: Faker):
    scheduler = Scheduler(status=faker.text(), workers=None)
    assert isinstance(scheduler.workers, WorkersDict)
    assert len(scheduler.workers) == 0


def test_worker_constructor_corrects_negative_used_resources(faker: Faker):
    worker = Worker(
        id=faker.pyint(min_value=1),
        name=faker.name(),
        resources={},
        used_resources={"CPU": -0.0000234},
        memory_limit=faker.pyint(min_value=1),
        metrics={
            "cpu": faker.pyfloat(min_value=0),
            "memory": faker.pyint(min_value=0),
            "num_fds": faker.pyint(),
            "ready": faker.pyint(),
            "executing": faker.pyint(),
            "in_flight": faker.pyint(),
            "in_memory": faker.pyint(),
        },
    )
    assert worker
    assert worker.used_resources["CPU"] == 0
