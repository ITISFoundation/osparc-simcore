# coding: utf-8

"""
    Director API

    This is the oSparc's director API  # noqa: E501

    The version of the OpenAPI document: 0.1.0
    Contact: support@simcore.com
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six

from simcore_director_sdk.configuration import Configuration


class InlineResponse200(object):
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
        'data': 'InlineResponse200Data',
        'error': 'object'
    }

    attribute_map = {
        'data': 'data',
        'error': 'error'
    }

    def __init__(self, data=None, error=None, local_vars_configuration=None):  # noqa: E501
        """InlineResponse200 - a model defined in OpenAPI"""  # noqa: E501
        if local_vars_configuration is None:
            local_vars_configuration = Configuration()
        self.local_vars_configuration = local_vars_configuration

        self._data = None
        self._error = None
        self.discriminator = None

        self.data = data
        self.error = error

    @property
    def data(self):
        """Gets the data of this InlineResponse200.  # noqa: E501


        :return: The data of this InlineResponse200.  # noqa: E501
        :rtype: InlineResponse200Data
        """
        return self._data

    @data.setter
    def data(self, data):
        """Sets the data of this InlineResponse200.


        :param data: The data of this InlineResponse200.  # noqa: E501
        :type: InlineResponse200Data
        """
        if self.local_vars_configuration.client_side_validation and data is None:  # noqa: E501
            raise ValueError("Invalid value for `data`, must not be `None`")  # noqa: E501

        self._data = data

    @property
    def error(self):
        """Gets the error of this InlineResponse200.  # noqa: E501


        :return: The error of this InlineResponse200.  # noqa: E501
        :rtype: object
        """
        return self._error

    @error.setter
    def error(self, error):
        """Sets the error of this InlineResponse200.


        :param error: The error of this InlineResponse200.  # noqa: E501
        :type: object
        """

        self._error = error

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
        if not isinstance(other, InlineResponse200):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, InlineResponse200):
            return True

        return self.to_dict() != other.to_dict()
