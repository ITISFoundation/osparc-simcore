# coding: utf-8

"""
    simcore-service-storage API

    API definition for simcore-service-storage service  # noqa: E501

    The version of the OpenAPI document: 0.2.1
    Contact: support@simcore.io
    Generated by: https://openapi-generator.tech
"""


try:
    from inspect import getfullargspec
except ImportError:
    from inspect import getargspec as getfullargspec
import pprint
import re  # noqa: F401
import six

from simcore_service_storage_sdk.configuration import Configuration


class HealthCheckEnveloped(object):
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
        'data': 'HealthCheck',
        'error': 'object'
    }

    attribute_map = {
        'data': 'data',
        'error': 'error'
    }

    def __init__(self, data=None, error=None, local_vars_configuration=None):  # noqa: E501
        """HealthCheckEnveloped - a model defined in OpenAPI"""  # noqa: E501
        if local_vars_configuration is None:
            local_vars_configuration = Configuration.get_default_copy()
        self.local_vars_configuration = local_vars_configuration

        self._data = None
        self._error = None
        self.discriminator = None

        self.data = data
        self.error = error

    @property
    def data(self):
        """Gets the data of this HealthCheckEnveloped.  # noqa: E501


        :return: The data of this HealthCheckEnveloped.  # noqa: E501
        :rtype: HealthCheck
        """
        return self._data

    @data.setter
    def data(self, data):
        """Sets the data of this HealthCheckEnveloped.


        :param data: The data of this HealthCheckEnveloped.  # noqa: E501
        :type data: HealthCheck
        """
        if self.local_vars_configuration.client_side_validation and data is None:  # noqa: E501
            raise ValueError("Invalid value for `data`, must not be `None`")  # noqa: E501

        self._data = data

    @property
    def error(self):
        """Gets the error of this HealthCheckEnveloped.  # noqa: E501


        :return: The error of this HealthCheckEnveloped.  # noqa: E501
        :rtype: object
        """
        return self._error

    @error.setter
    def error(self, error):
        """Sets the error of this HealthCheckEnveloped.


        :param error: The error of this HealthCheckEnveloped.  # noqa: E501
        :type error: object
        """

        self._error = error

    def to_dict(self, serialize=False):
        """Returns the model properties as a dict"""
        result = {}

        def convert(x):
            if hasattr(x, "to_dict"):
                args = getfullargspec(x.to_dict).args
                if len(args) == 1:
                    return x.to_dict()
                else:
                    return x.to_dict(serialize)
            else:
                return x

        for attr, _ in six.iteritems(self.openapi_types):
            value = getattr(self, attr)
            attr = self.attribute_map.get(attr, attr) if serialize else attr
            if isinstance(value, list):
                result[attr] = list(map(
                    lambda x: convert(x),
                    value
                ))
            elif isinstance(value, dict):
                result[attr] = dict(map(
                    lambda item: (item[0], convert(item[1])),
                    value.items()
                ))
            else:
                result[attr] = convert(value)

        return result

    def to_str(self):
        """Returns the string representation of the model"""
        return pprint.pformat(self.to_dict())

    def __repr__(self):
        """For `print` and `pprint`"""
        return self.to_str()

    def __eq__(self, other):
        """Returns true if both objects are equal"""
        if not isinstance(other, HealthCheckEnveloped):
            return False

        return self.to_dict() == other.to_dict()

    def __ne__(self, other):
        """Returns true if both objects are not equal"""
        if not isinstance(other, HealthCheckEnveloped):
            return True

        return self.to_dict() != other.to_dict()
