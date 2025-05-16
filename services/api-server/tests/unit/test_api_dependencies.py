from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from simcore_service_api_server.api.dependencies.models_schemas_jobs_filters import (
    get_job_metadata_filter,
)
from simcore_service_api_server.models.schemas.jobs_filters import (
    JobMetadataFilter,
    MetadataFilterItem,
)


def test_get_metadata_filter():
    # Test with None input
    assert get_job_metadata_filter(None) is None

    # Test with empty list
    assert get_job_metadata_filter([]) is None

    # Test with valid input (matching the example in the docstring)
    input_data = ["key1:val*", "key2:exactval"]
    result = get_job_metadata_filter(input_data)

    expected = JobMetadataFilter(
        any=[
            MetadataFilterItem(name="key1", pattern="val*"),
            MetadataFilterItem(name="key2", pattern="exactval"),
        ]
    )

    assert result is not None
    assert len(result.any) == 2
    assert result.any[0].name == "key1"
    assert result.any[0].pattern == "val*"
    assert result.any[1].name == "key2"
    assert result.any[1].pattern == "exactval"
    assert result == expected

    # Test with invalid input (missing colon)
    input_data = ["key1val", "key2:exactval"]
    result = get_job_metadata_filter(input_data)

    assert result is not None
    assert len(result.any) == 1
    assert result.any[0].name == "key2"
    assert result.any[0].pattern == "exactval"

    # Test with empty pattern not allowed
    input_data = ["key1:", "key2:exactval"]
    with pytest.raises(ValidationError) as exc_info:
        get_job_metadata_filter(input_data)

    assert exc_info.value.errors()[0]["type"] == "string_too_short"


def test_metadata_filter_in_api_route():
    # Create a test FastAPI app
    app = FastAPI()

    # Define a route that uses the get_metadata_filter dependency
    @app.get("/test-filter")
    def filter_endpoint(
        metadata_filter: Annotated[
            JobMetadataFilter | None, Depends(get_job_metadata_filter)
        ] = None,
    ):
        if not metadata_filter:
            return {"filters": None}

        # Convert to dict for easier comparison in test
        return {
            "filters": {
                "any": [
                    {"name": item.name, "pattern": item.pattern}
                    for item in metadata_filter.any
                ]
            }
        }

    # Create a test client
    client = TestClient(app)

    # Test with no filter
    response = client.get("/test-filter")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"filters": None}

    # Test with single filter
    response = client.get("/test-filter?metadata.any=key1:val*")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "filters": {"any": [{"name": "key1", "pattern": "val*"}]}
    }

    # Test with multiple filters
    response = client.get(
        "/test-filter?metadata.any=key1:val*&metadata.any=key2:exactval"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "filters": {
            "any": [
                {"name": "key1", "pattern": "val*"},
                {"name": "key2", "pattern": "exactval"},
            ]
        }
    }

    # Test with invalid filter (should skip the invalid one)
    response = client.get(
        "/test-filter?metadata.any=invalid&metadata.any=key2:exactval"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "filters": {"any": [{"name": "key2", "pattern": "exactval"}]}
    }

    # Test with URL-encoded characters
    # Use special characters that need encoding: space, &, =, +, /, ?
    encoded_query = "/test-filter?metadata.any=special%20key:value%20with%20spaces&metadata.any=symbols:a%2Bb%3Dc%26d%3F%2F"
    response = client.get(encoded_query)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "filters": {
            "any": [
                {"name": "special key", "pattern": "value with spaces"},
                {"name": "symbols", "pattern": "a+b=c&d?/"},
            ]
        }
    }

    # Test with Unicode characters
    unicode_query = "/test-filter?metadata.any=emoji:%F0%9F%98%8A&metadata.any=international:caf%C3%A9"
    response = client.get(unicode_query)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "filters": {
            "any": [
                {"name": "emoji", "pattern": "😊"},
                {"name": "international", "pattern": "café"},
            ]
        }
    }
