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


class InlineObject1(object):
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
    openapi_types = {"link_id": "str"}

    attribute_map = {"link_id": "link_id"}

    def __init__(self, link_id=None, local_vars_configuration=None):  # noqa: E501
        """InlineObject1 - a model defined in OpenAPI"""  # noqa: E501
        if local_vars_configuration is None:
            local_vars_configuration = Configuration()
        self.local_vars_configuration = local_vars_configuration

        self._link_id = None
        self.discriminator = None

        self.link_id = link_id

    @property
    def link_id(self):
        """Gets the link_id of this InlineObject1.  # noqa: E501


        :return: The link_id of this InlineObject1.  # noqa: E501
        :rtype: str
        """
        return self._link_id

    @link_id.setter
    def link_id(self, link_id):
        """Sets the link_id of this InlineObject1.


        :param link_id: The link_id of this InlineObject1.  # noqa: E501
        :type: str
        """
        if (
            self.local_vars_configuration.client_side_validation and link_id is None
        ):  # noqa: E501
            raise ValueError(
                "Invalid value for `link_id`, must not be `None`"
            )  # noqa: E501

        self._link_id = link_id

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
        if not isinstance(other, InlineObject1):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, InlineObject1):
            return True

        return self.to_dict() != other.to_dict()
