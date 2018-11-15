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


class LogMessageType(object):
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
        'level': 'str',
        'message': 'str',
        'logger': 'str'
    }

    attribute_map = {
        'level': 'level',
        'message': 'message',
        'logger': 'logger'
    }

    def __init__(self, level='INFO', message=None, logger=None):  # noqa: E501
        """LogMessageType - a model defined in OpenAPI"""  # noqa: E501

        self._level = None
        self._message = None
        self._logger = None
        self.discriminator = None

        if level is not None:
            self.level = level
        self.message = message
        if logger is not None:
            self.logger = logger

    @property
    def level(self):
        """Gets the level of this LogMessageType.  # noqa: E501

        log level  # noqa: E501

        :return: The level of this LogMessageType.  # noqa: E501
        :rtype: str
        """
        return self._level

    @level.setter
    def level(self, level):
        """Sets the level of this LogMessageType.

        log level  # noqa: E501

        :param level: The level of this LogMessageType.  # noqa: E501
        :type: str
        """
        allowed_values = ["DEBUG", "WARNING", "INFO", "ERROR"]  # noqa: E501
        if level not in allowed_values:
            raise ValueError(
                "Invalid value for `level` ({0}), must be one of {1}"  # noqa: E501
                .format(level, allowed_values)
            )

        self._level = level

    @property
    def message(self):
        """Gets the message of this LogMessageType.  # noqa: E501

        log message. If logger is USER, then it MUST be human readable  # noqa: E501

        :return: The message of this LogMessageType.  # noqa: E501
        :rtype: str
        """
        return self._message

    @message.setter
    def message(self, message):
        """Sets the message of this LogMessageType.

        log message. If logger is USER, then it MUST be human readable  # noqa: E501

        :param message: The message of this LogMessageType.  # noqa: E501
        :type: str
        """
        if message is None:
            raise ValueError("Invalid value for `message`, must not be `None`")  # noqa: E501

        self._message = message

    @property
    def logger(self):
        """Gets the logger of this LogMessageType.  # noqa: E501

        name of the logger receiving this message  # noqa: E501

        :return: The logger of this LogMessageType.  # noqa: E501
        :rtype: str
        """
        return self._logger

    @logger.setter
    def logger(self, logger):
        """Sets the logger of this LogMessageType.

        name of the logger receiving this message  # noqa: E501

        :param logger: The logger of this LogMessageType.  # noqa: E501
        :type: str
        """

        self._logger = logger

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
        if not isinstance(other, LogMessageType):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
