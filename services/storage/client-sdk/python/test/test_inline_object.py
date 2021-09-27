# coding: utf-8

"""
    simcore-service-storage API

    API definition for simcore-service-storage service  # noqa: E501

    The version of the OpenAPI document: 0.2.1
    Contact: support@simcore.io
    Generated by: https://openapi-generator.tech
"""


from __future__ import absolute_import

import datetime
import unittest

import simcore_service_storage_sdk
from simcore_service_storage_sdk.models.inline_object import InlineObject  # noqa: E501
from simcore_service_storage_sdk.rest import ApiException


class TestInlineObject(unittest.TestCase):
    """InlineObject unit test stubs"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def make_instance(self, include_optional):
        """Test InlineObject
            include_option is a boolean, when False only required
            params are included, when True both required and
            optional params are included """
        # model = simcore_service_storage_sdk.models.inline_object.InlineObject()  # noqa: E501
        if include_optional :
            return InlineObject(
                source = simcore_service_storage_sdk.models.simcore_project.simcore project(
                    uuid = '07640335-a91f-468c-ab69-a374fa82078d',
                    name = 'Temporal Distortion Simulator',
                    description = 'Dabbling in temporal transitions ...',
                    prj_owner = '0',
                    access_rights = { },
                    creation_date = '2018-07-01T11:13:43Z',
                    last_change_date = '2018-07-01T11:13:43Z',
                    thumbnail = 'https://placeimg.com/171/96/tech/grayscale/?0.jpg',
                    workbench = { },
                    ui = { },
                    tags = [
                        56
                        ],
                    classifiers = some:id:to:a:classifier,
                    dev = simcore_service_storage_sdk.models.dev.dev(),
                    state = null,
                    quality = simcore_service_storage_sdk.models.quality.Quality(), ),
                destination = simcore_service_storage_sdk.models.simcore_project.simcore project(
                    uuid = '07640335-a91f-468c-ab69-a374fa82078d',
                    name = 'Temporal Distortion Simulator',
                    description = 'Dabbling in temporal transitions ...',
                    prj_owner = '0',
                    access_rights = { },
                    creation_date = '2018-07-01T11:13:43Z',
                    last_change_date = '2018-07-01T11:13:43Z',
                    thumbnail = 'https://placeimg.com/171/96/tech/grayscale/?0.jpg',
                    workbench = { },
                    ui = { },
                    tags = [
                        56
                        ],
                    classifiers = some:id:to:a:classifier,
                    dev = simcore_service_storage_sdk.models.dev.dev(),
                    state = null,
                    quality = simcore_service_storage_sdk.models.quality.Quality(), ),
                nodes_map = {
                    'key' : '0'
                    }
            )
        else :
            return InlineObject(
        )

    def testInlineObject(self):
        """Test InlineObject"""
        inst_req_only = self.make_instance(include_optional=False)
        inst_req_and_optional = self.make_instance(include_optional=True)


if __name__ == '__main__':
    unittest.main()
