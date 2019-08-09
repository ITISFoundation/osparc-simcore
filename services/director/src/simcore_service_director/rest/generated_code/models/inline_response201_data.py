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

    def __init__(self, entry_point=None, published_port=None, service_basepath=None, service_host=None, service_key=None, service_message=None, service_port=None, service_state=None, service_uuid=None, service_version=None):  # noqa: E501
        """InlineResponse201Data - a model defined in OpenAPI

        :param entry_point: The entry_point of this InlineResponse201Data.  # noqa: E501
        :type entry_point: str
        :param published_port: The published_port of this InlineResponse201Data.  # noqa: E501
        :type published_port: int
        :param service_basepath: The service_basepath of this InlineResponse201Data.  # noqa: E501
        :type service_basepath: str
        :param service_host: The service_host of this InlineResponse201Data.  # noqa: E501
        :type service_host: str
        :param service_key: The service_key of this InlineResponse201Data.  # noqa: E501
        :type service_key: str
        :param service_message: The service_message of this InlineResponse201Data.  # noqa: E501
        :type service_message: str
        :param service_port: The service_port of this InlineResponse201Data.  # noqa: E501
        :type service_port: int
        :param service_state: The service_state of this InlineResponse201Data.  # noqa: E501
        :type service_state: str
        :param service_uuid: The service_uuid of this InlineResponse201Data.  # noqa: E501
        :type service_uuid: str
        :param service_version: The service_version of this InlineResponse201Data.  # noqa: E501
        :type service_version: str
        """
        self.openapi_types = {
            'entry_point': 'str',
            'published_port': 'int',
            'service_basepath': 'str',
            'service_host': 'str',
            'service_key': 'str',
            'service_message': 'str',
            'service_port': 'int',
            'service_state': 'str',
            'service_uuid': 'str',
            'service_version': 'str'
        }

        self.attribute_map = {
            'entry_point': 'entry_point',
            'published_port': 'published_port',
            'service_basepath': 'service_basepath',
            'service_host': 'service_host',
            'service_key': 'service_key',
            'service_message': 'service_message',
            'service_port': 'service_port',
            'service_state': 'service_state',
            'service_uuid': 'service_uuid',
            'service_version': 'service_version'
        }

        self._entry_point = entry_point
        self._published_port = published_port
        self._service_basepath = service_basepath
        self._service_host = service_host
        self._service_key = service_key
        self._service_message = service_message
        self._service_port = service_port
        self._service_state = service_state
        self._service_uuid = service_uuid
        self._service_version = service_version

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
    def service_basepath(self):
        """Gets the service_basepath of this InlineResponse201Data.

        different base path where current service is mounted otherwise defaults to root  # noqa: E501

        :return: The service_basepath of this InlineResponse201Data.
        :rtype: str
        """
        return self._service_basepath

    @service_basepath.setter
    def service_basepath(self, service_basepath):
        """Sets the service_basepath of this InlineResponse201Data.

        different base path where current service is mounted otherwise defaults to root  # noqa: E501

        :param service_basepath: The service_basepath of this InlineResponse201Data.
        :type service_basepath: str
        """

        self._service_basepath = service_basepath

    @property
    def service_host(self):
        """Gets the service_host of this InlineResponse201Data.

        service host name within the network  # noqa: E501

        :return: The service_host of this InlineResponse201Data.
        :rtype: str
        """
        return self._service_host

    @service_host.setter
    def service_host(self, service_host):
        """Sets the service_host of this InlineResponse201Data.

        service host name within the network  # noqa: E501

        :param service_host: The service_host of this InlineResponse201Data.
        :type service_host: str
        """
        if service_host is None:
            raise ValueError("Invalid value for `service_host`, must not be `None`")  # noqa: E501

        self._service_host = service_host

    @property
    def service_key(self):
        """Gets the service_key of this InlineResponse201Data.

        distinctive name for the node based on the docker registry path  # noqa: E501

        :return: The service_key of this InlineResponse201Data.
        :rtype: str
        """
        return self._service_key

    @service_key.setter
    def service_key(self, service_key):
        """Sets the service_key of this InlineResponse201Data.

        distinctive name for the node based on the docker registry path  # noqa: E501

        :param service_key: The service_key of this InlineResponse201Data.
        :type service_key: str
        """
        if service_key is None:
            raise ValueError("Invalid value for `service_key`, must not be `None`")  # noqa: E501
        if service_key is not None and not re.search(r'^(simcore)\/(services)\/(comp|dynamic)(\/[^\\s\/]+)+$', service_key):  # noqa: E501
            raise ValueError("Invalid value for `service_key`, must be a follow pattern or equal to `/^(simcore)\/(services)\/(comp|dynamic)(\/[^\\s\/]+)+$/`")  # noqa: E501

        self._service_key = service_key

    @property
    def service_message(self):
        """Gets the service_message of this InlineResponse201Data.

        the service message  # noqa: E501

        :return: The service_message of this InlineResponse201Data.
        :rtype: str
        """
        return self._service_message

    @service_message.setter
    def service_message(self, service_message):
        """Sets the service_message of this InlineResponse201Data.

        the service message  # noqa: E501

        :param service_message: The service_message of this InlineResponse201Data.
        :type service_message: str
        """

        self._service_message = service_message

    @property
    def service_port(self):
        """Gets the service_port of this InlineResponse201Data.

        port to access the service within the network  # noqa: E501

        :return: The service_port of this InlineResponse201Data.
        :rtype: int
        """
        return self._service_port

    @service_port.setter
    def service_port(self, service_port):
        """Sets the service_port of this InlineResponse201Data.

        port to access the service within the network  # noqa: E501

        :param service_port: The service_port of this InlineResponse201Data.
        :type service_port: int
        """
        if service_port is None:
            raise ValueError("Invalid value for `service_port`, must not be `None`")  # noqa: E501
        if service_port is not None and service_port < 1:  # noqa: E501
            raise ValueError("Invalid value for `service_port`, must be a value greater than or equal to `1`")  # noqa: E501

        self._service_port = service_port

    @property
    def service_state(self):
        """Gets the service_state of this InlineResponse201Data.

        the service state * 'pending' - The service is waiting for resources to start * 'pulling' - The service is being pulled from the registry * 'starting' - The service is starting * 'running' - The service is running * 'complete' - The service completed * 'failed' - The service failed to start   # noqa: E501

        :return: The service_state of this InlineResponse201Data.
        :rtype: str
        """
        return self._service_state

    @service_state.setter
    def service_state(self, service_state):
        """Sets the service_state of this InlineResponse201Data.

        the service state * 'pending' - The service is waiting for resources to start * 'pulling' - The service is being pulled from the registry * 'starting' - The service is starting * 'running' - The service is running * 'complete' - The service completed * 'failed' - The service failed to start   # noqa: E501

        :param service_state: The service_state of this InlineResponse201Data.
        :type service_state: str
        """
        allowed_values = ["pending", "pulling", "starting", "running", "complete", "failed"]  # noqa: E501
        if service_state not in allowed_values:
            raise ValueError(
                "Invalid value for `service_state` ({0}), must be one of {1}"
                .format(service_state, allowed_values)
            )

        self._service_state = service_state

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

    @property
    def service_version(self):
        """Gets the service_version of this InlineResponse201Data.

        semantic version number  # noqa: E501

        :return: The service_version of this InlineResponse201Data.
        :rtype: str
        """
        return self._service_version

    @service_version.setter
    def service_version(self, service_version):
        """Sets the service_version of this InlineResponse201Data.

        semantic version number  # noqa: E501

        :param service_version: The service_version of this InlineResponse201Data.
        :type service_version: str
        """
        if service_version is None:
            raise ValueError("Invalid value for `service_version`, must not be `None`")  # noqa: E501
        if service_version is not None and not re.search(r'^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$', service_version):  # noqa: E501
            raise ValueError("Invalid value for `service_version`, must be a follow pattern or equal to `/^(0|[1-9]\\d*)(\\.(0|[1-9]\\d*)){2}(-(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*)(\\.(0|[1-9]\\d*|\\d*[-a-zA-Z][-\\da-zA-Z]*))*)?(\\+[-\\da-zA-Z]+(\\.[-\\da-zA-Z-]+)*)?$/`")  # noqa: E501

        self._service_version = service_version
