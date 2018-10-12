# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from .base_model_ import Model
from .error import Error  # noqa: F401,E501
from .. import util


class ErrorEnveloped(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, error: Error=None, status: int=None):  # noqa: E501
        """ErrorEnveloped - a model defined in OpenAPI

        :param error: The error of this ErrorEnveloped.  # noqa: E501
        :type error: Error
        :param status: The status of this ErrorEnveloped.  # noqa: E501
        :type status: int
        """
        self.openapi_types = {
            'error': Error,
            'status': int
        }

        self.attribute_map = {
            'error': 'error',
            'status': 'status'
        }

        self._error = error
        self._status = status

    @classmethod
    def from_dict(cls, dikt) -> 'ErrorEnveloped':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The ErrorEnveloped of this ErrorEnveloped.  # noqa: E501
        :rtype: ErrorEnveloped
        """
        return util.deserialize_model(dikt, cls)

    @property
    def error(self) -> Error:
        """Gets the error of this ErrorEnveloped.


        :return: The error of this ErrorEnveloped.
        :rtype: Error
        """
        return self._error

    @error.setter
    def error(self, error: Error):
        """Sets the error of this ErrorEnveloped.


        :param error: The error of this ErrorEnveloped.
        :type error: Error
        """
        if error is None:
            raise ValueError("Invalid value for `error`, must not be `None`")  # noqa: E501

        self._error = error

    @property
    def status(self) -> int:
        """Gets the status of this ErrorEnveloped.

        Error code  # noqa: E501

        :return: The status of this ErrorEnveloped.
        :rtype: int
        """
        return self._status

    @status.setter
    def status(self, status: int):
        """Sets the status of this ErrorEnveloped.

        Error code  # noqa: E501

        :param status: The status of this ErrorEnveloped.
        :type status: int
        """

        self._status = status
