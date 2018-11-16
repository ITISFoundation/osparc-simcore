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


class InlineResponseDefaultError(object):
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
        'errors': 'list[object]',
        'message': 'str',
        'status': 'int'
    }

    attribute_map = {
        'errors': 'errors',
        'message': 'message',
        'status': 'status'
    }

    def __init__(self, errors=None, message=None, status=None):  # noqa: E501
        """InlineResponseDefaultError - a model defined in OpenAPI"""  # noqa: E501

        self._errors = None
        self._message = None
        self._status = None
        self.discriminator = None

        if errors is not None:
            self.errors = errors
        self.message = message
        self.status = status

    @property
    def errors(self):
        """Gets the errors of this InlineResponseDefaultError.  # noqa: E501


        :return: The errors of this InlineResponseDefaultError.  # noqa: E501
        :rtype: list[object]
        """
        return self._errors

    @errors.setter
    def errors(self, errors):
        """Sets the errors of this InlineResponseDefaultError.


        :param errors: The errors of this InlineResponseDefaultError.  # noqa: E501
        :type: list[object]
        """

        self._errors = errors

    @property
    def message(self):
        """Gets the message of this InlineResponseDefaultError.  # noqa: E501

        Error message  # noqa: E501

        :return: The message of this InlineResponseDefaultError.  # noqa: E501
        :rtype: str
        """
        return self._message

    @message.setter
    def message(self, message):
        """Sets the message of this InlineResponseDefaultError.

        Error message  # noqa: E501

        :param message: The message of this InlineResponseDefaultError.  # noqa: E501
        :type: str
        """
        if message is None:
            raise ValueError("Invalid value for `message`, must not be `None`")  # noqa: E501

        self._message = message

    @property
    def status(self):
        """Gets the status of this InlineResponseDefaultError.  # noqa: E501

        Error code  # noqa: E501

        :return: The status of this InlineResponseDefaultError.  # noqa: E501
        :rtype: int
        """
        return self._status

    @status.setter
    def status(self, status):
        """Sets the status of this InlineResponseDefaultError.

        Error code  # noqa: E501

        :param status: The status of this InlineResponseDefaultError.  # noqa: E501
        :type: int
        """
        if status is None:
            raise ValueError("Invalid value for `status`, must not be `None`")  # noqa: E501

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
        if not isinstance(other, InlineResponseDefaultError):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
