import pytest
from models_library.celery import OwnerMetadata
from models_library.users import UserID


class MyOwnerMetadata(OwnerMetadata):
    user_id: UserID


@pytest.fixture
def fake_owner_metadata() -> OwnerMetadata:
    return MyOwnerMetadata(user_id=42, owner="test-owner")
