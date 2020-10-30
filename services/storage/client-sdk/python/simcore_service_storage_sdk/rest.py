# coding: utf-8

"""
    simcore-service-storage API

    API definition for simcore-service-storage service  # noqa: E501

    OpenAPI spec version: 0.1.0
    Contact: support@simcore.io
    Generated by: https://openapi-generator.tech
"""


import io
import json
import logging
import re
import ssl

import aiohttp
import certifi
import asyncio

# python 2 and python 3 compatibility library
from six.moves.urllib.parse import urlencode

logger = logging.getLogger(__name__)


class RESTResponse(io.IOBase):
    def __init__(self, resp, data):
        self.aiohttp_response = resp
        self.status = resp.status
        self.reason = resp.reason
        self.data = data

    def getheaders(self):
        """Returns a CIMultiDictProxy of the response headers."""
        return self.aiohttp_response.headers

    def getheader(self, name, default=None):
        """Returns a given response header."""
        return self.aiohttp_response.headers.get(name, default)


class RESTClientObject(object):
    def __init__(self, configuration, pools_size=4, maxsize=4):
        # maxsize is number of requests to host that are allowed in parallel

        # ca_certs
        if configuration.ssl_ca_cert:
            ca_certs = configuration.ssl_ca_cert
        else:
            # if not set certificate file, use Mozilla's root certificates.
            ca_certs = certifi.where()

        ssl_context = ssl.create_default_context(cafile=ca_certs)
        if configuration.cert_file:
            ssl_context.load_cert_chain(
                configuration.cert_file, keyfile=configuration.key_file
            )

        if not configuration.verify_ssl:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(limit=maxsize, ssl_context=ssl_context)

        # https pool manager
        timeout_settings = aiohttp.ClientTimeout(total=1, connect=1, sock_connect=1)
        if configuration.proxy:
            self.pool_manager = aiohttp.ClientSession(
                connector=connector, proxy=configuration.proxy, timeout=timeout_settings
            )
        else:
            self.pool_manager = aiohttp.ClientSession(
                connector=connector, timeout=timeout_settings
            )

    def __del__(self):
        asyncio.ensure_future(self.pool_manager.close())

    async def request(
        self,
        method,
        url,
        query_params=None,
        headers=None,
        body=None,
        post_params=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        """Execute request

        :param method: http request method
        :param url: http request url
        :param query_params: query parameters in the url
        :param headers: http request headers
        :param body: request json body, for `application/json`
        :param post_params: request post parameters,
                            `application/x-www-form-urlencoded`
                            and `multipart/form-data`
        :param _preload_content: this is a non-applicable field for
                                 the AiohttpClient.
        :param _request_timeout: timeout setting for this request. If one
                                 number provided, it will be total request
                                 timeout. It can also be a pair (tuple) of
                                 (connection, read) timeouts.
        """
        method = method.upper()
        assert method in ["GET", "HEAD", "DELETE", "POST", "PUT", "PATCH", "OPTIONS"]

        if post_params and body:
            raise ValueError(
                "body parameter cannot be used with post_params parameter."
            )

        post_params = post_params or {}
        headers = headers or {}
        timeout = _request_timeout or 5 * 60

        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        args = {"method": method, "url": url, "timeout": timeout, "headers": headers}

        if query_params:
            args["url"] += "?" + urlencode(query_params)

        # For `POST`, `PUT`, `PATCH`, `OPTIONS`, `DELETE`
        if method in ["POST", "PUT", "PATCH", "OPTIONS", "DELETE"]:
            if re.search("json", headers["Content-Type"], re.IGNORECASE):
                if body is not None:
                    body = json.dumps(body)
                args["data"] = body
            elif (
                headers["Content-Type"] == "application/x-www-form-urlencoded"
            ):  # noqa: E501
                args["data"] = aiohttp.FormData(post_params)
            elif headers["Content-Type"] == "multipart/form-data":
                # must del headers['Content-Type'], or the correct
                # Content-Type which generated by aiohttp
                del headers["Content-Type"]
                data = aiohttp.FormData()
                for param in post_params:
                    k, v = param
                    if isinstance(v, tuple) and len(v) == 3:
                        data.add_field(k, value=v[1], filename=v[0], content_type=v[2])
                    else:
                        data.add_field(k, v)
                args["data"] = data

            # Pass a `bytes` parameter directly in the body to support
            # other content types than Json when `body` argument is provided
            # in serialized form
            elif isinstance(body, bytes):
                args["data"] = body
            else:
                # Cannot generate the request from given parameters
                msg = """Cannot prepare a request message for provided
                         arguments. Please check that your arguments match
                         declared content type."""
                raise ApiException(status=0, reason=msg)

        r = await self.pool_manager.request(**args)
        if _preload_content:

            data = await r.text()
            r = RESTResponse(r, data)

            # log response body
            logger.debug("response body: %s", r.data)

            if not 200 <= r.status <= 299:
                raise ApiException(http_resp=r)

        return r

    async def GET(
        self,
        url,
        headers=None,
        query_params=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        return await self.request(
            "GET",
            url,
            headers=headers,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
            query_params=query_params,
        )

    async def HEAD(
        self,
        url,
        headers=None,
        query_params=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        return await self.request(
            "HEAD",
            url,
            headers=headers,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
            query_params=query_params,
        )

    async def OPTIONS(
        self,
        url,
        headers=None,
        query_params=None,
        post_params=None,
        body=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        return await self.request(
            "OPTIONS",
            url,
            headers=headers,
            query_params=query_params,
            post_params=post_params,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
            body=body,
        )

    async def DELETE(
        self,
        url,
        headers=None,
        query_params=None,
        body=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        return await self.request(
            "DELETE",
            url,
            headers=headers,
            query_params=query_params,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
            body=body,
        )

    async def POST(
        self,
        url,
        headers=None,
        query_params=None,
        post_params=None,
        body=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        return await self.request(
            "POST",
            url,
            headers=headers,
            query_params=query_params,
            post_params=post_params,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
            body=body,
        )

    async def PUT(
        self,
        url,
        headers=None,
        query_params=None,
        post_params=None,
        body=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        return await self.request(
            "PUT",
            url,
            headers=headers,
            query_params=query_params,
            post_params=post_params,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
            body=body,
        )

    async def PATCH(
        self,
        url,
        headers=None,
        query_params=None,
        post_params=None,
        body=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        return await self.request(
            "PATCH",
            url,
            headers=headers,
            query_params=query_params,
            post_params=post_params,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
            body=body,
        )


class ApiException(Exception):
    def __init__(self, status=None, reason=None, http_resp=None):
        if http_resp:
            self.status = http_resp.status
            self.reason = http_resp.reason
            self.body = http_resp.data
            self.headers = http_resp.getheaders()
        else:
            self.status = status
            self.reason = reason
            self.body = None
            self.headers = None

    def __str__(self):
        """Custom error messages for exception"""
        error_message = "({0})\nReason: {1}\n".format(self.status, self.reason)
        if self.headers:
            error_message += "HTTP response headers: {0}\n".format(self.headers)

        if self.body:
            error_message += "HTTP response body: {0}\n".format(self.body)

        return error_message
