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
from models_library.clusters import ClusterTypeInModel
from pydantic import BaseModel, ByteSize, TypeAdapter
from simcore_postgres_database.models.clusters import ClusterType


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
        id=f"{faker.pyint(min_value=1)}",
        name=faker.name(),
        resources=TypeAdapter(AvailableResources).validate_python({}),
        used_resources=TypeAdapter(UsedResources).validate_python({"CPU": -0.0000234}),
        memory_limit=ByteSize(faker.pyint(min_value=1)),
        metrics=WorkerMetrics.model_validate(
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


def test_cluster_type_in_model_includes_postgres_database_model():
    models_library_cluster_types_names: set[str] = {
        t.name for t in set(ClusterTypeInModel)
    }
    postgres_library_cluster_types_names: set[str] = {t.name for t in set(ClusterType)}
    assert postgres_library_cluster_types_names.issubset(
        models_library_cluster_types_names
    )

    models_library_cluster_types_values: set[str] = {
        t.value for t in set(ClusterTypeInModel)
    }  # type: ignore
    postgres_library_cluster_types_values: set[str] = {
        t.value for t in set(ClusterType)
    }
    assert postgres_library_cluster_types_values.issubset(
        models_library_cluster_types_values
    )
