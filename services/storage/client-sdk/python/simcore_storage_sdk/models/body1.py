# coding: utf-8

"""
    simcore-service-storage API

    API definition for simcore-service-storage service  # noqa: E501

    OpenAPI spec version: 0.1.0
    Contact: support@simcore.io
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six


class Body1(object):
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
        'bucket_name': 'str',
        'file_id': 'str',
        'file_name': 'str',
        'file_uuid': 'str',
        'location': 'str',
        'location_id': 'str',
        'node_id': 'str',
        'node_name': 'str',
        'object_name': 'str',
        'project_id': 'str',
        'project_name': 'str',
        'user_id': 'str',
        'user_name': 'str'
    }

    attribute_map = {
        'bucket_name': 'bucket_name',
        'file_id': 'file_id',
        'file_name': 'file_name',
        'file_uuid': 'file_uuid',
        'location': 'location',
        'location_id': 'location_id',
        'node_id': 'node_id',
        'node_name': 'node_name',
        'object_name': 'object_name',
        'project_id': 'project_id',
        'project_name': 'project_name',
        'user_id': 'user_id',
        'user_name': 'user_name'
    }

    def __init__(self, bucket_name=None, file_id=None, file_name=None, file_uuid=None, location=None, location_id=None, node_id=None, node_name=None, object_name=None, project_id=None, project_name=None, user_id=None, user_name=None):  # noqa: E501
        """Body1 - a model defined in OpenAPI"""  # noqa: E501

        self._bucket_name = None
        self._file_id = None
        self._file_name = None
        self._file_uuid = None
        self._location = None
        self._location_id = None
        self._node_id = None
        self._node_name = None
        self._object_name = None
        self._project_id = None
        self._project_name = None
        self._user_id = None
        self._user_name = None
        self.discriminator = None

        if bucket_name is not None:
            self.bucket_name = bucket_name
        if file_id is not None:
            self.file_id = file_id
        if file_name is not None:
            self.file_name = file_name
        if file_uuid is not None:
            self.file_uuid = file_uuid
        if location is not None:
            self.location = location
        if location_id is not None:
            self.location_id = location_id
        if node_id is not None:
            self.node_id = node_id
        if node_name is not None:
            self.node_name = node_name
        if object_name is not None:
            self.object_name = object_name
        if project_id is not None:
            self.project_id = project_id
        if project_name is not None:
            self.project_name = project_name
        if user_id is not None:
            self.user_id = user_id
        if user_name is not None:
            self.user_name = user_name

    @property
    def bucket_name(self):
        """Gets the bucket_name of this Body1.  # noqa: E501


        :return: The bucket_name of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._bucket_name

    @bucket_name.setter
    def bucket_name(self, bucket_name):
        """Sets the bucket_name of this Body1.


        :param bucket_name: The bucket_name of this Body1.  # noqa: E501
        :type: str
        """

        self._bucket_name = bucket_name

    @property
    def file_id(self):
        """Gets the file_id of this Body1.  # noqa: E501


        :return: The file_id of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._file_id

    @file_id.setter
    def file_id(self, file_id):
        """Sets the file_id of this Body1.


        :param file_id: The file_id of this Body1.  # noqa: E501
        :type: str
        """

        self._file_id = file_id

    @property
    def file_name(self):
        """Gets the file_name of this Body1.  # noqa: E501


        :return: The file_name of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._file_name

    @file_name.setter
    def file_name(self, file_name):
        """Sets the file_name of this Body1.


        :param file_name: The file_name of this Body1.  # noqa: E501
        :type: str
        """

        self._file_name = file_name

    @property
    def file_uuid(self):
        """Gets the file_uuid of this Body1.  # noqa: E501


        :return: The file_uuid of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._file_uuid

    @file_uuid.setter
    def file_uuid(self, file_uuid):
        """Sets the file_uuid of this Body1.


        :param file_uuid: The file_uuid of this Body1.  # noqa: E501
        :type: str
        """

        self._file_uuid = file_uuid

    @property
    def location(self):
        """Gets the location of this Body1.  # noqa: E501


        :return: The location of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._location

    @location.setter
    def location(self, location):
        """Sets the location of this Body1.


        :param location: The location of this Body1.  # noqa: E501
        :type: str
        """

        self._location = location

    @property
    def location_id(self):
        """Gets the location_id of this Body1.  # noqa: E501


        :return: The location_id of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._location_id

    @location_id.setter
    def location_id(self, location_id):
        """Sets the location_id of this Body1.


        :param location_id: The location_id of this Body1.  # noqa: E501
        :type: str
        """

        self._location_id = location_id

    @property
    def node_id(self):
        """Gets the node_id of this Body1.  # noqa: E501


        :return: The node_id of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._node_id

    @node_id.setter
    def node_id(self, node_id):
        """Sets the node_id of this Body1.


        :param node_id: The node_id of this Body1.  # noqa: E501
        :type: str
        """

        self._node_id = node_id

    @property
    def node_name(self):
        """Gets the node_name of this Body1.  # noqa: E501


        :return: The node_name of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._node_name

    @node_name.setter
    def node_name(self, node_name):
        """Sets the node_name of this Body1.


        :param node_name: The node_name of this Body1.  # noqa: E501
        :type: str
        """

        self._node_name = node_name

    @property
    def object_name(self):
        """Gets the object_name of this Body1.  # noqa: E501


        :return: The object_name of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._object_name

    @object_name.setter
    def object_name(self, object_name):
        """Sets the object_name of this Body1.


        :param object_name: The object_name of this Body1.  # noqa: E501
        :type: str
        """

        self._object_name = object_name

    @property
    def project_id(self):
        """Gets the project_id of this Body1.  # noqa: E501


        :return: The project_id of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._project_id

    @project_id.setter
    def project_id(self, project_id):
        """Sets the project_id of this Body1.


        :param project_id: The project_id of this Body1.  # noqa: E501
        :type: str
        """

        self._project_id = project_id

    @property
    def project_name(self):
        """Gets the project_name of this Body1.  # noqa: E501


        :return: The project_name of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._project_name

    @project_name.setter
    def project_name(self, project_name):
        """Sets the project_name of this Body1.


        :param project_name: The project_name of this Body1.  # noqa: E501
        :type: str
        """

        self._project_name = project_name

    @property
    def user_id(self):
        """Gets the user_id of this Body1.  # noqa: E501


        :return: The user_id of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._user_id

    @user_id.setter
    def user_id(self, user_id):
        """Sets the user_id of this Body1.


        :param user_id: The user_id of this Body1.  # noqa: E501
        :type: str
        """

        self._user_id = user_id

    @property
    def user_name(self):
        """Gets the user_name of this Body1.  # noqa: E501


        :return: The user_name of this Body1.  # noqa: E501
        :rtype: str
        """
        return self._user_name

    @user_name.setter
    def user_name(self, user_name):
        """Sets the user_name of this Body1.


        :param user_name: The user_name of this Body1.  # noqa: E501
        :type: str
        """

        self._user_name = user_name

    def to_dict(self):
        """Returns the model properties as a dict"""
        result = {}

        for attr, _ in six.iteritems(self.openapi_types):
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: x.to_dict() if hasattr(x, "to_dict") else x,
                    value
                ))
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], item[1].to_dict())
                    if hasattr(item[1], "to_dict") else item,
                    value.items()
                ))
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
        if not isinstance(other, Body1):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
