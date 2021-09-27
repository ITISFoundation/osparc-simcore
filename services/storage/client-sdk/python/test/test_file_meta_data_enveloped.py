# coding: utf-8

"""
    simcore-service-storage API

    API definition for simcore-service-storage service  # noqa: E501

    The version of the OpenAPI document: 0.2.1
    Contact: support@simcore.io
    Generated by: https://openapi-generator.tech
"""


from __future__ import absolute_import

import unittest
import datetime

import simcore_service_storage_sdk
from simcore_service_storage_sdk.models.file_meta_data_enveloped import FileMetaDataEnveloped  # noqa: E501
from simcore_service_storage_sdk.rest import ApiException

class TestFileMetaDataEnveloped(unittest.TestCase):
    """FileMetaDataEnveloped unit test stubs"""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def make_instance(self, include_optional):
        """Test FileMetaDataEnveloped
            include_option is a boolean, when False only required
            params are included, when True both required and
            optional params are included """
        # model = simcore_service_storage_sdk.models.file_meta_data_enveloped.FileMetaDataEnveloped()  # noqa: E501
        if include_optional :
            return FileMetaDataEnveloped(
                data = simcore_service_storage_sdk.models.file_meta_data.FileMetaData(
                    file_uuid = '', 
                    location_id = '', 
                    location = '', 
                    bucket_name = '', 
                    object_name = '', 
                    project_id = '', 
                    project_name = '', 
                    node_id = '', 
                    node_name = '', 
                    file_name = '', 
                    user_id = '', 
                    user_name = '', 
                    file_id = '', 
                    raw_file_path = '', 
                    display_file_path = '', 
                    created_at = '', 
                    last_modified = '', 
                    file_size = 56, 
                    parent_id = '', 
                    entity_tag = '', ), 
                error = None
            )
        else :
            return FileMetaDataEnveloped(
                data = simcore_service_storage_sdk.models.file_meta_data.FileMetaData(
                    file_uuid = '', 
                    location_id = '', 
                    location = '', 
                    bucket_name = '', 
                    object_name = '', 
                    project_id = '', 
                    project_name = '', 
                    node_id = '', 
                    node_name = '', 
                    file_name = '', 
                    user_id = '', 
                    user_name = '', 
                    file_id = '', 
                    raw_file_path = '', 
                    display_file_path = '', 
                    created_at = '', 
                    last_modified = '', 
                    file_size = 56, 
                    parent_id = '', 
                    entity_tag = '', ),
                error = None,
        )

    def testFileMetaDataEnveloped(self):
        """Test FileMetaDataEnveloped"""
        inst_req_only = self.make_instance(include_optional=False)
        inst_req_and_optional = self.make_instance(include_optional=True)

if __name__ == '__main__':
    unittest.main()
