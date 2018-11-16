# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from .base_model_ import Model
from .. import util


class InlineResponse201Data(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, entry_point=None, published_port=None, service_uuid=None):  # noqa: E501
        """InlineResponse201Data - a model defined in OpenAPI

        :param entry_point: The entry_point of this InlineResponse201Data.  # noqa: E501
        :type entry_point: str
        :param published_port: The published_port of this InlineResponse201Data.  # noqa: E501
        :type published_port: int
        :param service_uuid: The service_uuid of this InlineResponse201Data.  # noqa: E501
        :type service_uuid: str
        """
        self.openapi_types = {
            'entry_point': 'str',
            'published_port': 'int',
            'service_uuid': 'str'
        }

        self.attribute_map = {
            'entry_point': 'entry_point',
            'published_port': 'published_port',
            'service_uuid': 'service_uuid'
        }

        self._entry_point = entry_point
        self._published_port = published_port
        self._service_uuid = service_uuid

    @classmethod
    def from_dict(cls, dikt) -> 'InlineResponse201Data':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The inline_response_201_data of this InlineResponse201Data.  # noqa: E501
        :rtype: InlineResponse201Data
        """
        return util.deserialize_model(dikt, cls)

    @property
    def entry_point(self):
        """Gets the entry_point of this InlineResponse201Data.

        The entry point where the service provides its interface if specified  # noqa: E501

        :return: The entry_point of this InlineResponse201Data.
        :rtype: str
        """
        return self._entry_point

    @entry_point.setter
    def entry_point(self, entry_point):
        """Sets the entry_point of this InlineResponse201Data.

        The entry point where the service provides its interface if specified  # noqa: E501

        :param entry_point: The entry_point of this InlineResponse201Data.
        :type entry_point: str
        """

        self._entry_point = entry_point

    @property
    def published_port(self):
        """Gets the published_port of this InlineResponse201Data.

        The ports where the service provides its interface  # noqa: E501

        :return: The published_port of this InlineResponse201Data.
        :rtype: int
        """
        return self._published_port

    @published_port.setter
    def published_port(self, published_port):
        """Sets the published_port of this InlineResponse201Data.

        The ports where the service provides its interface  # noqa: E501

        :param published_port: The published_port of this InlineResponse201Data.
        :type published_port: int
        """
        if published_port is None:
            raise ValueError("Invalid value for `published_port`, must not be `None`")  # noqa: E501
        if published_port is not None and published_port < 1:  # noqa: E501
            raise ValueError("Invalid value for `published_port`, must be a value greater than or equal to `1`")  # noqa: E501

        self._published_port = published_port

    @property
    def service_uuid(self):
        """Gets the service_uuid of this InlineResponse201Data.

        The UUID attached to this service  # noqa: E501

        :return: The service_uuid of this InlineResponse201Data.
        :rtype: str
        """
        return self._service_uuid

    @service_uuid.setter
    def service_uuid(self, service_uuid):
        """Sets the service_uuid of this InlineResponse201Data.

        The UUID attached to this service  # noqa: E501

        :param service_uuid: The service_uuid of this InlineResponse201Data.
        :type service_uuid: str
        """
        if service_uuid is None:
            raise ValueError("Invalid value for `service_uuid`, must not be `None`")  # noqa: E501

        self._service_uuid = service_uuid
