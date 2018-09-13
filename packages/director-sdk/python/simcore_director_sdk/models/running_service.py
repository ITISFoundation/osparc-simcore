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


class RunningService(object):
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
        'published_port': 'int',
        'entry_point': 'str',
        'service_uuid': 'str'
    }

    attribute_map = {
        'published_port': 'published_port',
        'entry_point': 'entry_point',
        'service_uuid': 'service_uuid'
    }

    def __init__(self, published_port=None, entry_point=None, service_uuid=None):  # noqa: E501
        """RunningService - a model defined in OpenAPI"""  # noqa: E501

        self._published_port = None
        self._entry_point = None
        self._service_uuid = None
        self.discriminator = None

        self.published_port = published_port
        if entry_point is not None:
            self.entry_point = entry_point
        self.service_uuid = service_uuid

    @property
    def published_port(self):
        """Gets the published_port of this RunningService.  # noqa: E501

        The ports where the service provides its interface  # noqa: E501

        :return: The published_port of this RunningService.  # noqa: E501
        :rtype: int
        """
        return self._published_port

    @published_port.setter
    def published_port(self, published_port):
        """Sets the published_port of this RunningService.

        The ports where the service provides its interface  # noqa: E501

        :param published_port: The published_port of this RunningService.  # noqa: E501
        :type: int
        """
        if published_port is None:
            raise ValueError("Invalid value for `published_port`, must not be `None`")  # noqa: E501
        if published_port is not None and published_port < 1:  # noqa: E501
            raise ValueError("Invalid value for `published_port`, must be a value greater than or equal to `1`")  # noqa: E501

        self._published_port = published_port

    @property
    def entry_point(self):
        """Gets the entry_point of this RunningService.  # noqa: E501

        The entry point where the service provides its interface if specified  # noqa: E501

        :return: The entry_point of this RunningService.  # noqa: E501
        :rtype: str
        """
        return self._entry_point

    @entry_point.setter
    def entry_point(self, entry_point):
        """Sets the entry_point of this RunningService.

        The entry point where the service provides its interface if specified  # noqa: E501

        :param entry_point: The entry_point of this RunningService.  # noqa: E501
        :type: str
        """

        self._entry_point = entry_point

    @property
    def service_uuid(self):
        """Gets the service_uuid of this RunningService.  # noqa: E501

        The UUID attached to this service  # noqa: E501

        :return: The service_uuid of this RunningService.  # noqa: E501
        :rtype: str
        """
        return self._service_uuid

    @service_uuid.setter
    def service_uuid(self, service_uuid):
        """Sets the service_uuid of this RunningService.

        The UUID attached to this service  # noqa: E501

        :param service_uuid: The service_uuid of this RunningService.  # noqa: E501
        :type: str
        """
        if service_uuid is None:
            raise ValueError("Invalid value for `service_uuid`, must not be `None`")  # noqa: E501

        self._service_uuid = service_uuid

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
        if not isinstance(other, RunningService):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
