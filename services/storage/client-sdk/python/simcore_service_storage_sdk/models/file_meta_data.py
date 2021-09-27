# coding: utf-8

"""
    simcore-service-storage API

    API definition for simcore-service-storage service  # noqa: E501

    The version of the OpenAPI document: 0.2.1
    Contact: support@simcore.io
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six
from simcore_service_storage_sdk.configuration import Configuration


class FileMetaData(object):
    """NOTE: This class is auto generated by OpenAPI Generator.
    Ref: https://openapi-generator.tech

    Do not edit the class manually.
    """

    """
    Attributes:
      openapi_types (dict): The key is attribute name
                            and the value is attribute type.
      attribute_map (dict): The key is attribute name
                            and the value is json key in definition.
    """
    openapi_types = {
        "file_uuid": "str",
        "location_id": "str",
        "location": "str",
        "bucket_name": "str",
        "object_name": "str",
        "project_id": "str",
        "project_name": "str",
        "node_id": "str",
        "node_name": "str",
        "file_name": "str",
        "user_id": "str",
        "user_name": "str",
        "file_id": "str",
        "raw_file_path": "str",
        "display_file_path": "str",
        "created_at": "str",
        "last_modified": "str",
        "file_size": "int",
        "parent_id": "str",
        "entity_tag": "str",
    }

    attribute_map = {
        "file_uuid": "file_uuid",
        "location_id": "location_id",
        "location": "location",
        "bucket_name": "bucket_name",
        "object_name": "object_name",
        "project_id": "project_id",
        "project_name": "project_name",
        "node_id": "node_id",
        "node_name": "node_name",
        "file_name": "file_name",
        "user_id": "user_id",
        "user_name": "user_name",
        "file_id": "file_id",
        "raw_file_path": "raw_file_path",
        "display_file_path": "display_file_path",
        "created_at": "created_at",
        "last_modified": "last_modified",
        "file_size": "file_size",
        "parent_id": "parent_id",
        "entity_tag": "entity_tag",
    }

    def __init__(
        self,
        file_uuid=None,
        location_id=None,
        location=None,
        bucket_name=None,
        object_name=None,
        project_id=None,
        project_name=None,
        node_id=None,
        node_name=None,
        file_name=None,
        user_id=None,
        user_name=None,
        file_id=None,
        raw_file_path=None,
        display_file_path=None,
        created_at=None,
        last_modified=None,
        file_size=None,
        parent_id=None,
        entity_tag=None,
        local_vars_configuration=None,
    ):  # noqa: E501
        """FileMetaData - a model defined in OpenAPI"""  # noqa: E501
        if local_vars_configuration is None:
            local_vars_configuration = Configuration()
        self.local_vars_configuration = local_vars_configuration

        self._file_uuid = None
        self._location_id = None
        self._location = None
        self._bucket_name = None
        self._object_name = None
        self._project_id = None
        self._project_name = None
        self._node_id = None
        self._node_name = None
        self._file_name = None
        self._user_id = None
        self._user_name = None
        self._file_id = None
        self._raw_file_path = None
        self._display_file_path = None
        self._created_at = None
        self._last_modified = None
        self._file_size = None
        self._parent_id = None
        self._entity_tag = None
        self.discriminator = None

        if file_uuid is not None:
            self.file_uuid = file_uuid
        if location_id is not None:
            self.location_id = location_id
        if location is not None:
            self.location = location
        if bucket_name is not None:
            self.bucket_name = bucket_name
        if object_name is not None:
            self.object_name = object_name
        if project_id is not None:
            self.project_id = project_id
        if project_name is not None:
            self.project_name = project_name
        if node_id is not None:
            self.node_id = node_id
        if node_name is not None:
            self.node_name = node_name
        if file_name is not None:
            self.file_name = file_name
        if user_id is not None:
            self.user_id = user_id
        if user_name is not None:
            self.user_name = user_name
        if file_id is not None:
            self.file_id = file_id
        if raw_file_path is not None:
            self.raw_file_path = raw_file_path
        if display_file_path is not None:
            self.display_file_path = display_file_path
        if created_at is not None:
            self.created_at = created_at
        if last_modified is not None:
            self.last_modified = last_modified
        if file_size is not None:
            self.file_size = file_size
        if parent_id is not None:
            self.parent_id = parent_id
        if entity_tag is not None:
            self.entity_tag = entity_tag

    @property
    def file_uuid(self):
        """Gets the file_uuid of this FileMetaData.  # noqa: E501


        :return: The file_uuid of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._file_uuid

    @file_uuid.setter
    def file_uuid(self, file_uuid):
        """Sets the file_uuid of this FileMetaData.


        :param file_uuid: The file_uuid of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._file_uuid = file_uuid

    @property
    def location_id(self):
        """Gets the location_id of this FileMetaData.  # noqa: E501


        :return: The location_id of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._location_id

    @location_id.setter
    def location_id(self, location_id):
        """Sets the location_id of this FileMetaData.


        :param location_id: The location_id of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._location_id = location_id

    @property
    def location(self):
        """Gets the location of this FileMetaData.  # noqa: E501


        :return: The location of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._location

    @location.setter
    def location(self, location):
        """Sets the location of this FileMetaData.


        :param location: The location of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._location = location

    @property
    def bucket_name(self):
        """Gets the bucket_name of this FileMetaData.  # noqa: E501


        :return: The bucket_name of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._bucket_name

    @bucket_name.setter
    def bucket_name(self, bucket_name):
        """Sets the bucket_name of this FileMetaData.


        :param bucket_name: The bucket_name of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._bucket_name = bucket_name

    @property
    def object_name(self):
        """Gets the object_name of this FileMetaData.  # noqa: E501


        :return: The object_name of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._object_name

    @object_name.setter
    def object_name(self, object_name):
        """Sets the object_name of this FileMetaData.


        :param object_name: The object_name of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._object_name = object_name

    @property
    def project_id(self):
        """Gets the project_id of this FileMetaData.  # noqa: E501


        :return: The project_id of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._project_id

    @project_id.setter
    def project_id(self, project_id):
        """Sets the project_id of this FileMetaData.


        :param project_id: The project_id of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._project_id = project_id

    @property
    def project_name(self):
        """Gets the project_name of this FileMetaData.  # noqa: E501


        :return: The project_name of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._project_name

    @project_name.setter
    def project_name(self, project_name):
        """Sets the project_name of this FileMetaData.


        :param project_name: The project_name of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._project_name = project_name

    @property
    def node_id(self):
        """Gets the node_id of this FileMetaData.  # noqa: E501


        :return: The node_id of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._node_id

    @node_id.setter
    def node_id(self, node_id):
        """Sets the node_id of this FileMetaData.


        :param node_id: The node_id of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._node_id = node_id

    @property
    def node_name(self):
        """Gets the node_name of this FileMetaData.  # noqa: E501


        :return: The node_name of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._node_name

    @node_name.setter
    def node_name(self, node_name):
        """Sets the node_name of this FileMetaData.


        :param node_name: The node_name of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._node_name = node_name

    @property
    def file_name(self):
        """Gets the file_name of this FileMetaData.  # noqa: E501


        :return: The file_name of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._file_name

    @file_name.setter
    def file_name(self, file_name):
        """Sets the file_name of this FileMetaData.


        :param file_name: The file_name of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._file_name = file_name

    @property
    def user_id(self):
        """Gets the user_id of this FileMetaData.  # noqa: E501


        :return: The user_id of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._user_id

    @user_id.setter
    def user_id(self, user_id):
        """Sets the user_id of this FileMetaData.


        :param user_id: The user_id of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._user_id = user_id

    @property
    def user_name(self):
        """Gets the user_name of this FileMetaData.  # noqa: E501


        :return: The user_name of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._user_name

    @user_name.setter
    def user_name(self, user_name):
        """Sets the user_name of this FileMetaData.


        :param user_name: The user_name of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._user_name = user_name

    @property
    def file_id(self):
        """Gets the file_id of this FileMetaData.  # noqa: E501


        :return: The file_id of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._file_id

    @file_id.setter
    def file_id(self, file_id):
        """Sets the file_id of this FileMetaData.


        :param file_id: The file_id of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._file_id = file_id

    @property
    def raw_file_path(self):
        """Gets the raw_file_path of this FileMetaData.  # noqa: E501


        :return: The raw_file_path of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._raw_file_path

    @raw_file_path.setter
    def raw_file_path(self, raw_file_path):
        """Sets the raw_file_path of this FileMetaData.


        :param raw_file_path: The raw_file_path of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._raw_file_path = raw_file_path

    @property
    def display_file_path(self):
        """Gets the display_file_path of this FileMetaData.  # noqa: E501


        :return: The display_file_path of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._display_file_path

    @display_file_path.setter
    def display_file_path(self, display_file_path):
        """Sets the display_file_path of this FileMetaData.


        :param display_file_path: The display_file_path of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._display_file_path = display_file_path

    @property
    def created_at(self):
        """Gets the created_at of this FileMetaData.  # noqa: E501


        :return: The created_at of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._created_at

    @created_at.setter
    def created_at(self, created_at):
        """Sets the created_at of this FileMetaData.


        :param created_at: The created_at of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._created_at = created_at

    @property
    def last_modified(self):
        """Gets the last_modified of this FileMetaData.  # noqa: E501


        :return: The last_modified of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._last_modified

    @last_modified.setter
    def last_modified(self, last_modified):
        """Sets the last_modified of this FileMetaData.


        :param last_modified: The last_modified of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._last_modified = last_modified

    @property
    def file_size(self):
        """Gets the file_size of this FileMetaData.  # noqa: E501


        :return: The file_size of this FileMetaData.  # noqa: E501
        :rtype: int
        """
        return self._file_size

    @file_size.setter
    def file_size(self, file_size):
        """Sets the file_size of this FileMetaData.


        :param file_size: The file_size of this FileMetaData.  # noqa: E501
        :type: int
        """

        self._file_size = file_size

    @property
    def parent_id(self):
        """Gets the parent_id of this FileMetaData.  # noqa: E501


        :return: The parent_id of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._parent_id

    @parent_id.setter
    def parent_id(self, parent_id):
        """Sets the parent_id of this FileMetaData.


        :param parent_id: The parent_id of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._parent_id = parent_id

    @property
    def entity_tag(self):
        """Gets the entity_tag of this FileMetaData.  # noqa: E501


        :return: The entity_tag of this FileMetaData.  # noqa: E501
        :rtype: str
        """
        return self._entity_tag

    @entity_tag.setter
    def entity_tag(self, entity_tag):
        """Sets the entity_tag of this FileMetaData.


        :param entity_tag: The entity_tag of this FileMetaData.  # noqa: E501
        :type: str
        """

        self._entity_tag = entity_tag

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.openapi_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(
                    map(lambda x: x.to_dict() if hasattr(x, "to_dict") else x, value)
                )
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(
                    map(
                        lambda item: (item[0], item[1].to_dict())
                        if hasattr(item[1], "to_dict")
                        else item,
                        value.items(),
                    )
                )
            else:
                result[attr] = value

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, FileMetaData):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, FileMetaData):
            return True

        return self.to_dict() != other.to_dict()
