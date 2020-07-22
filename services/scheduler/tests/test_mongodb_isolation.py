# Make sure all tests run against clean instances of MongoDB

import pytest
from async_asgi_testclient import TestClient
from umongo import Document, fields

from scheduler.app import app
from scheduler.dbs.mongo_models import instance


@instance.register
class SampleModel(Document):
    test_data = fields.DictField(required=True)
    name = fields.StrField(required=True)


@pytest.mark.run(order=1)
@pytest.mark.asyncio
async def test_first_to_run_also_spinning_up_mongo():
    # inserting a document and counting the number of inserted documents
    async with TestClient(app) as _:
        sample_document = SampleModel(test_data={"this": "doc1"}, name="first")
        await sample_document.commit()
    assert await SampleModel.count_documents() == 1


@pytest.mark.run(order=2)
@pytest.mark.asyncio
async def test_second_to_run():
    # scond test should yield the same result as above
    async with TestClient(app) as _:
        sample_document = SampleModel(test_data={"this": "doc2"}, name="second")
        await sample_document.commit()
    assert await SampleModel.count_documents() == 1
