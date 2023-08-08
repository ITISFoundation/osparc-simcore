from pprint import pformat
from typing import Any

import pytest
from faker import Faker
from models_library.api_schemas_directorv2.clusters import (
    AvailableResources,
    ClusterCreate,
    ClusterPatch,
    Scheduler,
    UsedResources,
    Worker,
    WorkerMetrics,
)
from pydantic import BaseModel, parse_obj_as


@pytest.mark.parametrize(
    "model_cls",
    [ClusterCreate, ClusterPatch],
)
def test_clusters_model_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
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
    model_cls: type[BaseModel], model_cls_examples: dict[str, dict[str, Any]]
):
    for example in model_cls_examples.values():
        if "thumbnail" in example:
            example.pop("thumbnail")
        instance = model_cls(**example)
        assert instance
        assert instance.thumbnail


def test_scheduler_constructor_with_default_has_correct_dict(faker: Faker):
    scheduler = Scheduler(status=faker.text())
    assert scheduler.workers is not None
    assert len(scheduler.workers) == 0


def test_scheduler_constructor_with_no_workers_has_correct_dict(faker: Faker):
    scheduler = Scheduler(status=faker.text(), workers=None)
    assert scheduler.workers is not None
    assert len(scheduler.workers) == 0


def test_worker_constructor_corrects_negative_used_resources(faker: Faker):
    worker = Worker(
        id=faker.pyint(min_value=1),
        name=faker.name(),
        resources=parse_obj_as(AvailableResources, {}),
        used_resources=parse_obj_as(UsedResources, {"CPU": -0.0000234}),
        memory_limit=faker.pyint(min_value=1),
        metrics=parse_obj_as(
            WorkerMetrics,
            {
                "cpu": faker.pyfloat(min_value=0),
                "memory": faker.pyint(min_value=0),
                "num_fds": faker.pyint(),
                "task_counts": {},
            },
        ),
    )
    assert worker
    assert worker.used_resources["CPU"] == 0
