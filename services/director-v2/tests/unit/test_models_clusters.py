from faker import Faker
from models_library.api_schemas_directorv2.clusters import (
    AvailableResources,
    Scheduler,
    UsedResources,
    Worker,
    WorkerMetrics,
)
from pydantic import ByteSize, TypeAdapter


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
