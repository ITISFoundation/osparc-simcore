from faker import Faker
from simcore_service_storage.modules.celery.tasks import archive


def test_archive(celery_app, celery_worker, faker: Faker):
    result = archive.apply(args=(faker.uuid4(), ["f1", "f2"]))
    assert result.get() == "f1_f2.zip"
