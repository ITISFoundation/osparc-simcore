# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from .base_model_ import Model
from .. import util


class ErrorEnveloped(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, data: object=None, status: int=None):  # noqa: E501
        """ErrorEnveloped - a model defined in OpenAPI

        :param data: The data of this ErrorEnveloped.  # noqa: E501
        :type data: object
        :param status: The status of this ErrorEnveloped.  # noqa: E501
        :type status: int
        """
        self.openapi_types = {
            'data': object,
            'status': int
        }

        self.attribute_map = {
            'data': 'data',
            'status': 'status'
        }

        self._data = data
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
    def data(self) -> object:
        """Gets the data of this ErrorEnveloped.


        :return: The data of this ErrorEnveloped.
        :rtype: object
        """
        return self._data

    @data.setter
    def data(self, data: object):
        """Sets the data of this ErrorEnveloped.


        :param data: The data of this ErrorEnveloped.
        :type data: object
        """

        self._data = data

    @property
    def status(self) -> int:
        """Gets the status of this ErrorEnveloped.


        :return: The status of this ErrorEnveloped.
        :rtype: int
        """
        return self._status

    @status.setter
    def status(self, status: int):
        """Sets the status of this ErrorEnveloped.


        :param status: The status of this ErrorEnveloped.
        :type status: int
        """

        self._status = status
