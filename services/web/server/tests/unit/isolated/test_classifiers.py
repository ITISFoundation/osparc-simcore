# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


####################################################################################################################
# NOTES

#
# To check times pytest --pdb -vv --durations=0  tests/unit/isolated/test_classifiers.py
#

# - every group define it's own classifiers: get_group_classifier
# - definition of classifiers is outsource to an external entity (e.g. github/gitlab/K-Core) that has a strict/consensual curation workflow in place
# So far
# - github/gitlab approach produces a bundle file with a static list of classifiers
#   - CONS:
#        - if large size, it will not fit the tree!?
#        - static. cannot change except if access to db
# - scicrunch approach provides an API to validate
#
#


# osparc-classifiers
#
# - A user from osparc selects a study/service and wants to add a classifier
# - a list of "official" classifier displays and can select one of them (already in the tree)
# - or propose a new one by introducing its RRID
#    - RRID (research resource [RR] curated and defined in K-Core: https://scicrunch.org/api/1/resource/fields/view/SCR_014398 )
#    -
# - if classifier is valid (API check or cache check)
#     add to validated classifier's cache
# - classifiers tree
#  is defined per group (get_group_classifier)
#     - thye
#       all classifiers in cache, based on some rules (e.g. usage, etc) are used to automaticaly update existing classifiers
#

####################################################################################################################

import os
import re
from enum import IntEnum
from http import HTTPStatus
from pprint import pprint
from typing import Any, List, Optional, Union
from uuid import UUID

import aiohttp
import pytest
from aiohttp import ClientSession
from pydantic import BaseModel, Field, ValidationError


class ValidationResult(IntEnum):
    UNKNOWN = -1
    INVALID = 0
    VALID = 1


RRID_PORTAL_API_KEY = os.environ.get("RRID_PORTAL_API_KEY")
BASE_URL = os.environ.get("SCICRUNCH_API_BASE_URL", "https://scicrunch.org/api/1")

# TODO: emulate server for testing
# TODO:



## MODELS


# NOTE: there is no need to capture everything
# fields = [
#   {
#     "field": "Resource Name",
#     "required": true,
#     "type": "text",
#     "max_number": "1",
#     "value": "Jupyter Notebook",
#     "position": 0,
#     "display": "title",
#     "alt": "The name of the unique resource you are submitting"
#   }, ...
# ]
class FieldItem(BaseModel):
    field: str
    required: bool
    # type: str  # text, textarea, resource-types, ...
    # max_number: str  # convertable to int
    value: Union[str, None, List[Any]] = None
    # position: int
    # display: str  # title, descripiotn, url, text, owner-text
    alt: str  # alternative text


# NOTE: Response looks like
# {
#   "data": {
#     "fields": [ ... ]
#     "version": 2,
#     "curation_status": "Curated",
#     "last_curated_version": 2,
#     "scicrunch_id": "SCR_018315",
#     "original_id": "SCR_018315",
#     "image_src": null,
#     "uuid": "0e88ffa5-752f-5ae6-aab1-b350edbe2ccc",
#     "typeID": 1
#   },
#   "success": true
# }
class ResourceView(BaseModel):
    resource_fields: Optional[List[FieldItem]] = Field(None, alias="fields")
    version: int
    curation_status: str
    last_curated_version: int
    uuid: UUID
    # typeID: int
    image_src: Optional[str] = None
    scicrunch_id: str
    original_id: str

    @property
    def is_curated(self) -> bool:
        return self.curation_status.lower() == "curated"



SPLIT_STRIP_PATTERN = r"[^:\s][^:]*[^:\s]*"


# model used to load from db??
class BasicClassifier(BaseModel):
    """ Default/minimal model for a classifier """
    classifier: str = Field(..., description="Classifier hierarchical classifier", regex=r"[^:]+")
    display_name: str

    # TODO: normalize classifier??
    def split(self) -> List[str]:
        parts = re.findall(SPLIT_STRIP_PATTERN, self.classifier)
        return parts


class KCoreClassifier(BasicClassifier):
    # If curated by K-Core
    rrid: str = Field(..., description="Research Resource Identifier as defined in https://scicrunch.org/resources", regex=r"^SRC_\d+$")



def create_valid_classifiers_tree():
    # builds a tree view with a selection of classifiers
    #  - needs a criteria to decide what to include

    # classifiers in tree ARE VALID (no need for extra validation)
    #

    pass



def test_classifier_model():
    classifier = BasicClassifier(classifier="a: b: cc 23", display_name="A B C")

    assert classifier.split() == ["a", "b", "cc 23"]

    classifier = BasicClassifier(classifier="a: b: cc 23", display_name="A B C", rrid="SRC_1234")

    assert classifier.split() == ["a", "b", "cc 23"]


## FREE HELPER FUNCTIONS

async def get_resource_fields(client: ClientSession, rrid: str) -> ResourceView:
    async with client.get(
        f"{BASE_URL}/resource/fields/view/{rrid}",
        params={"key": RRID_PORTAL_API_KEY},
        raise_for_status=True,
    ) as resp:
        body = await resp.json()
        assert body.get("success")
        return ResourceView(**body.get("data", {}))


async def get_all_versions(client: ClientSession, rrid: str) -> List:
    async with client.get(
        f"{BASE_URL}/resource/versions/all/{rrid}",
        params={"key": RRID_PORTAL_API_KEY},
        raise_for_status=True,
    ) as resp:
        body = await resp.json()
        return body.get("data") if body.get("success") else []


async def validate_rrid(client: ClientSession, rrid: str) -> ValidationResult:
    if rrid.startswith("SCR_"):
        try:
            versions = await get_all_versions(client, rrid)
            return ValidationResult.VALID if versions else ValidationResult.INVALID

        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.BAD_REQUEST:
                return ValidationResult.INVALID
            return ValidationResult.UNKNOWN

        except aiohttp.ClientError:
            # connection handling and server response misbehaviors
            # ClientResposeError over 300
            # raises? --> does NOT mean it is invalid but that cannot determine validity right now!!!
            # - server not reachable: down, wrong address
            # - timeout: server slowed down (retry?)
            return ValidationResult.UNKNOWN

        except ValidationError as err:
            print(err)
            return ValidationResult.INVALID

    return ValidationResult.INVALID

#---------------------

@pytest.mark.skipif( RRID_PORTAL_API_KEY is None, reason="Testing agains actual service is intended for manual exploratory testing")
async def test_scicrunch_api_specs(loop):
    async with ClientSession() as client:
        resp = await client.get("https://scicrunch.org/swagger-docs/swagger.json")
        openapi_specs = await resp.json()
        pprint(openapi_specs["info"])
        assert openapi_specs["info"]["version"] == 1


@pytest.mark.skipif( RRID_PORTAL_API_KEY is None, reason="Testing agains actual service is intended for manual exploratory testing")
@pytest.mark.parametrize(
    "classifier,rrid",
    [
        ("Jupyter Notebook", "SCR_018315"),
        ("Language::Python", "SCR_008394"),
        ("Language::Octave", "SCR_014398"),
        (None, "RRID:SCR_014398"),
        (None, "SCR_INVALID_XXXXX"),
        (None, "ANOTHER_INVALID_RRID"),
    ],
)
async def test_resource_online_validation(classifier, rrid, loop):
    async with ClientSession() as client:

        validation_result = await validate_rrid(client, rrid)

        assert validation_result == (
            ValidationResult.VALID if classifier else ValidationResult.INVALID
        ), f"{classifier} with rrid={rrid} is undefined"

        if validation_result == ValidationResult.VALID:
            resource = await get_resource_fields(client, rrid)

            assert resource.scicrunch_id == rrid
