# coding: utf-8

"""
    simcore-service-storage API

    API definition for simcore-service-storage service  # noqa: E501

    OpenAPI spec version: 0.2.1
    Contact: support@simcore.io
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six


class DatasetMetaDataArrayEnveloped(object):
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
    openapi_types = {"data": "DatasetMetaDataArray", "error": "object"}

    attribute_map = {"data": "data", "error": "error"}

    def __init__(self, data=None, error=None):  # noqa: E501
        """DatasetMetaDataArrayEnveloped - a model defined in OpenAPI"""  # noqa: E501

        self._data = None
        self._error = None
        self.discriminator = None

        self.data = data
        self.error = error

    @property
    def data(self):
        """Gets the data of this DatasetMetaDataArrayEnveloped.  # noqa: E501


        :return: The data of this DatasetMetaDataArrayEnveloped.  # noqa: E501
        :rtype: DatasetMetaDataArray
        """
        return self._data

    @data.setter
    def data(self, data):
        """Sets the data of this DatasetMetaDataArrayEnveloped.


        :param data: The data of this DatasetMetaDataArrayEnveloped.  # noqa: E501
        :type: DatasetMetaDataArray
        """
        if data is None:
            raise ValueError(
                "Invalid value for `data`, must not be `None`"
            )  # noqa: E501

        self._data = data

    @property
    def error(self):
        """Gets the error of this DatasetMetaDataArrayEnveloped.  # noqa: E501


        :return: The error of this DatasetMetaDataArrayEnveloped.  # noqa: E501
        :rtype: object
        """
        return self._error

    @error.setter
    def error(self, error):
        """Sets the error of this DatasetMetaDataArrayEnveloped.


        :param error: The error of this DatasetMetaDataArrayEnveloped.  # noqa: E501
        :type: object
        """

        self._error = error

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
        if not isinstance(other, DatasetMetaDataArrayEnveloped):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
