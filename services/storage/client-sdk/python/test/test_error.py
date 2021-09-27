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
from simcore_service_storage_sdk.models.error import Error  # noqa: E501
from simcore_service_storage_sdk.rest import ApiException


class TestError(unittest.TestCase):
    """Error unit test stubs"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def make_instance(self, include_optional):
        """Test Error
        include_option is a boolean, when False only required
        params are included, when True both required and
        optional params are included"""
        # model = simcore_service_storage_sdk.models.error.Error()  # noqa: E501
        if include_optional:
            return Error(
                logs=[
                    {
                        "message": "Hi there, Mr user",
                        "level": "INFO",
                        "logger": "user-logger",
                    }
                ],
                errors=[
                    simcore_service_storage_sdk.models.error_item.ErrorItem(
                        code="0",
                        message="0",
                        resource="0",
                        field="0",
                    )
                ],
                status=56,
            )
        else:
            return Error()

    def testError(self):
        """Test Error"""
        inst_req_only = self.make_instance(include_optional=False)
        inst_req_and_optional = self.make_instance(include_optional=True)


if __name__ == "__main__":
    unittest.main()
