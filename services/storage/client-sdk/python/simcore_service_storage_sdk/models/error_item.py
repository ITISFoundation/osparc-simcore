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


class ErrorItem(object):
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
    openapi_types = {"code": "str", "message": "str", "resource": "str", "field": "str"}

    attribute_map = {
        "code": "code",
        "message": "message",
        "resource": "resource",
        "field": "field",
    }

    def __init__(
        self,
        code=None,
        message=None,
        resource=None,
        field=None,
        local_vars_configuration=None,
    ):  # noqa: E501
        """ErrorItem - a model defined in OpenAPI"""  # noqa: E501
        if local_vars_configuration is None:
            local_vars_configuration = Configuration()
        self.local_vars_configuration = local_vars_configuration

        self._code = None
        self._message = None
        self._resource = None
        self._field = None
        self.discriminator = None

        self.code = code
        self.message = message
        if resource is not None:
            self.resource = resource
        if field is not None:
            self.field = field

    @property
    def code(self):
        """Gets the code of this ErrorItem.  # noqa: E501

        Typically the name of the exception that produced it otherwise some known error code  # noqa: E501

        :return: The code of this ErrorItem.  # noqa: E501
        :rtype: str
        """
        return self._code

    @code.setter
    def code(self, code):
        """Sets the code of this ErrorItem.

        Typically the name of the exception that produced it otherwise some known error code  # noqa: E501

        :param code: The code of this ErrorItem.  # noqa: E501
        :type: str
        """
        if (
            self.local_vars_configuration.client_side_validation and code is None
        ):  # noqa: E501
            raise ValueError(
                "Invalid value for `code`, must not be `None`"
            )  # noqa: E501

        self._code = code

    @property
    def message(self):
        """Gets the message of this ErrorItem.  # noqa: E501

        Error message specific to this item  # noqa: E501

        :return: The message of this ErrorItem.  # noqa: E501
        :rtype: str
        """
        return self._message

    @message.setter
    def message(self, message):
        """Sets the message of this ErrorItem.

        Error message specific to this item  # noqa: E501

        :param message: The message of this ErrorItem.  # noqa: E501
        :type: str
        """
        if (
            self.local_vars_configuration.client_side_validation and message is None
        ):  # noqa: E501
            raise ValueError(
                "Invalid value for `message`, must not be `None`"
            )  # noqa: E501

        self._message = message

    @property
    def resource(self):
        """Gets the resource of this ErrorItem.  # noqa: E501

        API resource affected by this error  # noqa: E501

        :return: The resource of this ErrorItem.  # noqa: E501
        :rtype: str
        """
        return self._resource

    @resource.setter
    def resource(self, resource):
        """Sets the resource of this ErrorItem.

        API resource affected by this error  # noqa: E501

        :param resource: The resource of this ErrorItem.  # noqa: E501
        :type: str
        """

        self._resource = resource

    @property
    def field(self):
        """Gets the field of this ErrorItem.  # noqa: E501

        Specific field within the resource  # noqa: E501

        :return: The field of this ErrorItem.  # noqa: E501
        :rtype: str
        """
        return self._field

    @field.setter
    def field(self, field):
        """Sets the field of this ErrorItem.

        Specific field within the resource  # noqa: E501

        :param field: The field of this ErrorItem.  # noqa: E501
        :type: str
        """

        self._field = field

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
        if not isinstance(other, ErrorItem):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, ErrorItem):
            return True

        return self.to_dict() != other.to_dict()
