# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from .base_model_ import Model
from .. import util


class Document(Model):
    """NOTE: This class is auto generated by OpenAPI Generator (https://openapi-generator.tech).

    Do not edit the class manually.
    """

    def __init__(self, doc_id: str=None, text: str=None):  # noqa: E501
        """Document - a model defined in OpenAPI

        :param doc_id: The doc_id of this Document.  # noqa: E501
        :type doc_id: str
        :param text: The text of this Document.  # noqa: E501
        :type text: str
        """
        self.openapi_types = {
            'doc_id': str,
            'text': str
        }

        self.attribute_map = {
            'doc_id': 'doc_id',
            'text': 'text'
        }

        self._doc_id = doc_id
        self._text = text

    @classmethod
    def from_dict(cls, dikt) -> 'Document':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The Document of this Document.  # noqa: E501
        :rtype: Document
        """
        return util.deserialize_model(dikt, cls)

    @property
    def doc_id(self) -> str:
        """Gets the doc_id of this Document.


        :return: The doc_id of this Document.
        :rtype: str
        """
        return self._doc_id

    @doc_id.setter
    def doc_id(self, doc_id: str):
        """Sets the doc_id of this Document.


        :param doc_id: The doc_id of this Document.
        :type doc_id: str
        """

        self._doc_id = doc_id

    @property
    def text(self) -> str:
        """Gets the text of this Document.


        :return: The text of this Document.
        :rtype: str
        """
        return self._text

    @text.setter
    def text(self, text: str):
        """Sets the text of this Document.


        :param text: The text of this Document.
        :type text: str
        """
        if text is None:
            raise ValueError("Invalid value for `text`, must not be `None`")  # noqa: E501

        self._text = text
