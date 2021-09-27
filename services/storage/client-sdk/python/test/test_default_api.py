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

import simcore_service_storage_sdk
from simcore_service_storage_sdk.api.default_api import DefaultApi  # noqa: E501
from simcore_service_storage_sdk.rest import ApiException


class TestDefaultApi(unittest.TestCase):
    """DefaultApi unit test stubs"""

    def setUp(self):
        self.api = simcore_service_storage_sdk.api.default_api.DefaultApi()  # noqa: E501

    def tearDown(self):
        pass

    def test_check_action_post(self):
        """Test case for check_action_post

        Test checkpoint to ask server to fail or echo back the transmitted data  # noqa: E501
        """
        pass

    def test_copy_as_soft_link(self):
        """Test case for copy_as_soft_link

        Copy as soft link  # noqa: E501
        """
        pass

    def test_copy_folders_from_project(self):
        """Test case for copy_folders_from_project

        Deep copies of all data from source to destination project in s3  # noqa: E501
        """
        pass

    def test_delete_file(self):
        """Test case for delete_file

        Deletes file  # noqa: E501
        """
        pass

    def test_delete_folders_of_project(self):
        """Test case for delete_folders_of_project

        Deletes all objects within a node_id or within a project_id if node_id is omitted  # noqa: E501
        """
        pass

    def test_download_file(self):
        """Test case for download_file

        Gets download link for file at location  # noqa: E501
        """
        pass

    def test_get_datasets_metadata(self):
        """Test case for get_datasets_metadata

        Lists all dataset's metadata  # noqa: E501
        """
        pass

    def test_get_file_metadata(self):
        """Test case for get_file_metadata

        Get file metadata  # noqa: E501
        """
        pass

    def test_get_files_metadata(self):
        """Test case for get_files_metadata

        Lists all file's metadata  # noqa: E501
        """
        pass

    def test_get_files_metadata_dataset(self):
        """Test case for get_files_metadata_dataset

        Get dataset metadata  # noqa: E501
        """
        pass

    def test_get_status(self):
        """Test case for get_status

        checks status of self and connected services  # noqa: E501
        """
        pass

    def test_get_storage_locations(self):
        """Test case for get_storage_locations

        Lists available storage locations  # noqa: E501
        """
        pass

    def test_health_check(self):
        """Test case for health_check

        Service health-check endpoint  # noqa: E501
        """
        pass

    def test_search_files_starting_with(self):
        """Test case for search_files_starting_with

        Returns metadata for all files matching a pattern  # noqa: E501
        """
        pass

    def test_synchronise_meta_data_table(self):
        """Test case for synchronise_meta_data_table

        Manually triggers the synchronisation of the file meta data table in the database  # noqa: E501
        """
        pass

    def test_update_file_meta_data(self):
        """Test case for update_file_meta_data

        Update file metadata  # noqa: E501
        """
        pass

    def test_upload_file(self):
        """Test case for upload_file

        Returns upload link or performs copy operation to datcore  # noqa: E501
        """
        pass


if __name__ == '__main__':
    unittest.main()
