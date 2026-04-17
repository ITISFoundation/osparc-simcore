import pytest


@pytest.fixture
def fake_owner() -> str:
    return "test-owner"


@pytest.fixture
def fake_user_id() -> int:
    return 42
