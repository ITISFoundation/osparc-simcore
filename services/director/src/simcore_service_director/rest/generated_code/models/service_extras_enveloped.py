# coding: utf-8

from datetime import date, datetime

from typing import List, Dict, Type

from .base_model_ import Model
from .inline_response2002_data import InlineResponse2002Data
from .. import util


class ServiceExtrasEnveloped(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, data: InlineResponse2002Data=None, error: object=None):
        """ServiceExtrasEnveloped - a model defined in OpenAPI

        :param data: The data of this ServiceExtrasEnveloped.
        :param error: The error of this ServiceExtrasEnveloped.
        """
        self.openapi_types = {
            'data': InlineResponse2002Data,
            'error': object
        }

        self.attribute_map = {
            'data': 'data',
            'error': 'error'
        }

        self._data = data
        self._error = error

    @classmethod
    def from_dict(cls, dikt: dict) -> 'ServiceExtrasEnveloped':
        """Returns the dict as a model

        :param dikt: A dict.
        :return: The ServiceExtrasEnveloped of this ServiceExtrasEnveloped.
        """
        return util.deserialize_model(dikt, cls)

    @property
    def data(self):
        """Gets the data of this ServiceExtrasEnveloped.


        :return: The data of this ServiceExtrasEnveloped.
        :rtype: InlineResponse2002Data
        """
        return self._data

    @data.setter
    def data(self, data):
        """Sets the data of this ServiceExtrasEnveloped.


        :param data: The data of this ServiceExtrasEnveloped.
        :type data: InlineResponse2002Data
        """
        if data is None:
            raise ValueError("Invalid value for `data`, must not be `None`")

        self._data = data

    @property
    def error(self):
        """Gets the error of this ServiceExtrasEnveloped.


        :return: The error of this ServiceExtrasEnveloped.
        :rtype: object
        """
        return self._error

    @error.setter
    def error(self, error):
        """Sets the error of this ServiceExtrasEnveloped.


        :param error: The error of this ServiceExtrasEnveloped.
        :type error: object
        """

        self._error = error
