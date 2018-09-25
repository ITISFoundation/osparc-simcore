# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from .base_model_ import Model
from .. import util


class HealthCheck(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, name: str=None, status: str=None, version: str=None, api_version: str=None):  # noqa: E501
        """HealthCheck - a model defined in OpenAPI

        :param name: The name of this HealthCheck.  # noqa: E501
        :type name: str
        :param status: The status of this HealthCheck.  # noqa: E501
        :type status: str
        :param version: The version of this HealthCheck.  # noqa: E501
        :type version: str
        :param api_version: The api_version of this HealthCheck.  # noqa: E501
        :type api_version: str
        """
        self.openapi_types = {
            'name': str,
            'status': str,
            'version': str,
            'api_version': str
        }

        self.attribute_map = {
            'name': 'name',
            'status': 'status',
            'version': 'version',
            'api_version': 'api_version'
        }

        self._name = name
        self._status = status
        self._version = version
        self._api_version = api_version

    @classmethod
    def from_dict(cls, dikt) -> 'HealthCheck':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The HealthCheck of this HealthCheck.  # noqa: E501
        :rtype: HealthCheck
        """
        return util.deserialize_model(dikt, cls)

    @property
    def name(self) -> str:
        """Gets the name of this HealthCheck.


        :return: The name of this HealthCheck.
        :rtype: str
        """
        return self._name

    @name.setter
    def name(self, name: str):
        """Sets the name of this HealthCheck.


        :param name: The name of this HealthCheck.
        :type name: str
        """

        self._name = name

    @property
    def status(self) -> str:
        """Gets the status of this HealthCheck.


        :return: The status of this HealthCheck.
        :rtype: str
        """
        return self._status

    @status.setter
    def status(self, status: str):
        """Sets the status of this HealthCheck.


        :param status: The status of this HealthCheck.
        :type status: str
        """

        self._status = status

    @property
    def version(self) -> str:
        """Gets the version of this HealthCheck.


        :return: The version of this HealthCheck.
        :rtype: str
        """
        return self._version

    @version.setter
    def version(self, version: str):
        """Sets the version of this HealthCheck.


        :param version: The version of this HealthCheck.
        :type version: str
        """

        self._version = version

    @property
    def api_version(self) -> str:
        """Gets the api_version of this HealthCheck.


        :return: The api_version of this HealthCheck.
        :rtype: str
        """
        return self._api_version

    @api_version.setter
    def api_version(self, api_version: str):
        """Sets the api_version of this HealthCheck.


        :param api_version: The api_version of this HealthCheck.
        :type api_version: str
        """

        self._api_version = api_version
