# coding: utf-8

"""
    Director API

    This is the oSparc's director API  # noqa: E501

    OpenAPI spec version: 0.1.0
    Contact: support@simcore.com
    Generated by: https://openapi-generator.tech
"""


import pprint
import re  # noqa: F401

import six


class InlineResponse201Data(object):
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
        'entry_point': 'str',
        'published_port': 'int',
        'service_basepath': 'str',
        'service_host': 'str',
        'service_key': 'str',
        'service_port': 'int',
        'service_uuid': 'str',
        'service_version': 'str'
    }

    attribute_map = {
        'entry_point': 'entry_point',
        'published_port': 'published_port',
        'service_basepath': 'service_basepath',
        'service_host': 'service_host',
        'service_key': 'service_key',
        'service_port': 'service_port',
        'service_uuid': 'service_uuid',
        'service_version': 'service_version'
    }

    def __init__(self, entry_point=None, published_port=None, service_basepath=None, service_host=None, service_key=None, service_port=None, service_uuid=None, service_version=None):  # noqa: E501
        """InlineResponse201Data - a model defined in OpenAPI"""  # noqa: E501

        self._entry_point = None
        self._published_port = None
        self._service_basepath = None
        self._service_host = None
        self._service_key = None
        self._service_port = None
        self._service_uuid = None
        self._service_version = None
        self.discriminator = None

        if entry_point is not None:
            self.entry_point = entry_point
        self.published_port = published_port
        if service_basepath is not None:
            self.service_basepath = service_basepath
        self.service_host = service_host
        self.service_key = service_key
        self.service_port = service_port
        self.service_uuid = service_uuid
        self.service_version = service_version

    @property
    def entry_point(self):
        """Gets the entry_point of this InlineResponse201Data.  # noqa: E501

        The entry point where the service provides its interface if specified  # noqa: E501

        :return: The entry_point of this InlineResponse201Data.  # noqa: E501
        :rtype: str
        """
        return self._entry_point

    @entry_point.setter
    def entry_point(self, entry_point):
        """Sets the entry_point of this InlineResponse201Data.

        The entry point where the service provides its interface if specified  # noqa: E501

        :param entry_point: The entry_point of this InlineResponse201Data.  # noqa: E501
        :type: str
        """

        self._entry_point = entry_point

    @property
    def published_port(self):
        """Gets the published_port of this InlineResponse201Data.  # noqa: E501

        The ports where the service provides its interface  # noqa: E501

        :return: The published_port of this InlineResponse201Data.  # noqa: E501
        :rtype: int
        """
        return self._published_port

    @published_port.setter
    def published_port(self, published_port):
        """Sets the published_port of this InlineResponse201Data.

        The ports where the service provides its interface  # noqa: E501

        :param published_port: The published_port of this InlineResponse201Data.  # noqa: E501
        :type: int
        """
        if published_port is None:
            raise ValueError("Invalid value for `published_port`, must not be `None`")  # noqa: E501
        if published_port is not None and published_port < 1:  # noqa: E501
            raise ValueError("Invalid value for `published_port`, must be a value greater than or equal to `1`")  # noqa: E501

        self._published_port = published_port

    @property
    def service_basepath(self):
        """Gets the service_basepath of this InlineResponse201Data.  # noqa: E501

        different base path where current service is mounted otherwise defaults to root  # noqa: E501

        :return: The service_basepath of this InlineResponse201Data.  # noqa: E501
        :rtype: str
        """
        return self._service_basepath

    @service_basepath.setter
    def service_basepath(self, service_basepath):
        """Sets the service_basepath of this InlineResponse201Data.

        different base path where current service is mounted otherwise defaults to root  # noqa: E501

        :param service_basepath: The service_basepath of this InlineResponse201Data.  # noqa: E501
        :type: str
        """

        self._service_basepath = service_basepath

    @property
    def service_host(self):
        """Gets the service_host of this InlineResponse201Data.  # noqa: E501

        service host name within the network  # noqa: E501

        :return: The service_host of this InlineResponse201Data.  # noqa: E501
        :rtype: str
        """
        return self._service_host

    @service_host.setter
    def service_host(self, service_host):
        """Sets the service_host of this InlineResponse201Data.

        service host name within the network  # noqa: E501

        :param service_host: The service_host of this InlineResponse201Data.  # noqa: E501
        :type: str
        """
        if service_host is None:
            raise ValueError("Invalid value for `service_host`, must not be `None`")  # noqa: E501

        self._service_host = service_host

    @property
    def service_key(self):
        """Gets the service_key of this InlineResponse201Data.  # noqa: E501

        distinctive name for the node based on the docker registry path  # noqa: E501

        :return: The service_key of this InlineResponse201Data.  # noqa: E501
        :rtype: str
        """
        return self._service_key

    @service_key.setter
    def service_key(self, service_key):
        """Sets the service_key of this InlineResponse201Data.

        distinctive name for the node based on the docker registry path  # noqa: E501

        :param service_key: The service_key of this InlineResponse201Data.  # noqa: E501
        :type: str
        """
        if service_key is None:
            raise ValueError("Invalid value for `service_key`, must not be `None`")  # noqa: E501
        if service_key is not None and not re.search('^(simcore)\/(services)\/(comp|dynamic)(\/[^\\s\/]+)+$', service_key):  # noqa: E501
            raise ValueError(r"Invalid value for `service_key`, must be a follow pattern or equal to `/^(simcore)\/(services)\/(comp|dynamic)(\/[^\\s\/]+)+$/`")  # noqa: E501

        self._service_key = service_key

    @property
    def service_port(self):
        """Gets the service_port of this InlineResponse201Data.  # noqa: E501

        port to access the service within the network  # noqa: E501

        :return: The service_port of this InlineResponse201Data.  # noqa: E501
        :rtype: int
        """
        return self._service_port

    @service_port.setter
    def service_port(self, service_port):
        """Sets the service_port of this InlineResponse201Data.

        port to access the service within the network  # noqa: E501

        :param service_port: The service_port of this InlineResponse201Data.  # noqa: E501
        :type: int
        """
        if service_port is None:
            raise ValueError("Invalid value for `service_port`, must not be `None`")  # noqa: E501
        if service_port is not None and service_port < 1:  # noqa: E501
            raise ValueError("Invalid value for `service_port`, must be a value greater than or equal to `1`")  # noqa: E501

        self._service_port = service_port

    @property
    def service_uuid(self):
        """Gets the service_uuid of this InlineResponse201Data.  # noqa: E501

        The UUID attached to this service  # noqa: E501

        :return: The service_uuid of this InlineResponse201Data.  # noqa: E501
        :rtype: str
        """
        return self._service_uuid

    @service_uuid.setter
    def service_uuid(self, service_uuid):
        """Sets the service_uuid of this InlineResponse201Data.

        The UUID attached to this service  # noqa: E501

        :param service_uuid: The service_uuid of this InlineResponse201Data.  # noqa: E501
        :type: str
        """
        if service_uuid is None:
            raise ValueError("Invalid value for `service_uuid`, must not be `None`")  # noqa: E501

        self._service_uuid = service_uuid

    @property
    def service_version(self):
        """Gets the service_version of this InlineResponse201Data.  # noqa: E501

        semantic version number  # noqa: E501

        :return: The service_version of this InlineResponse201Data.  # noqa: E501
        :rtype: str
        """
        return self._service_version

    @service_version.setter
    def service_version(self, service_version):
        """Sets the service_version of this InlineResponse201Data.

        semantic version number  # noqa: E501

        :param service_version: The service_version of this InlineResponse201Data.  # noqa: E501
        :type: str
        """
        if service_version is None:
            raise ValueError("Invalid value for `service_version`, must not be `None`")  # noqa: E501
        if service_version is not None and not re.search('^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$', service_version):  # noqa: E501
            raise ValueError(r"Invalid value for `service_version`, must be a follow pattern or equal to `/^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$/`")  # noqa: E501

        self._service_version = service_version

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
        if not isinstance(other, InlineResponse201Data):
            return False

        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        return not self == other
