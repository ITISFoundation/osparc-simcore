# coding: utf-8

"""
    Director API

    This is the oSparc's director API  # noqa: E501

    OpenAPI spec version: 1.0.0
    Contact: support@simcore.com
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six


class ServicesEnveloped(object):
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
        'data': 'list[NodeMetaV0]',
        'status': 'int'
    }

    attribute_map = {
        'data': 'data',
        'status': 'status'
    }

    def __init__(self, data=None, status=None):  # noqa: E501
        """ServicesEnveloped - a model defined in OpenAPI"""  # noqa: E501

        self._data = None
        self._status = None
        self.discriminator = None

        if data is not None:
            self.data = data
        if status is not None:
            self.status = status

    @property
    def data(self):
        """Gets the data of this ServicesEnveloped.  # noqa: E501


        :return: The data of this ServicesEnveloped.  # noqa: E501
        :rtype: list[NodeMetaV0]
        """
        return self._data

    @data.setter
    def data(self, data):
        """Sets the data of this ServicesEnveloped.


        :param data: The data of this ServicesEnveloped.  # noqa: E501
        :type: list[NodeMetaV0]
        """

        self._data = data

    @property
    def status(self):
        """Gets the status of this ServicesEnveloped.  # noqa: E501


        :return: The status of this ServicesEnveloped.  # noqa: E501
        :rtype: int
        """
        return self._status

    @status.setter
    def status(self, status):
        """Sets the status of this ServicesEnveloped.


        :param status: The status of this ServicesEnveloped.  # noqa: E501
        :type: int
        """

        self._status = status

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
        if not isinstance(other, ServicesEnveloped):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
