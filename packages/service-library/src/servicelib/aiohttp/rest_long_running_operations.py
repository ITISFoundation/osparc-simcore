""" Long running operations

An API may need to expose a method that takes a significant amount of time to complete.

Rather than blocking while the task runs, it is better to return some kind of promise to the user and allow the user to check back in later

Essentially, the user is given a token that can be used to track progress and retrieve the result.

- SEE Long-running operations https://google.aip.dev/151
- SEE Operations https://github.com/googleapis/googleapis/blob/master/google/longrunning/operations.proto
"""

from abc import ABC, abstractmethod
from typing import Generic, Optional, TypeVar, Union

from pydantic import BaseModel, PositiveInt
from pydantic.generics import GenericModel

MetaT = TypeVar("MetaT", bound=BaseModel)
ErrorT = TypeVar("ErrorT", bound=BaseModel)
ResponseT = TypeVar("ResponseT", bound=BaseModel)


class Operation(GenericModel, Generic[MetaT, ResponseT, ErrorT]):
    """This resource represents a long-running operation that is the result of a network API call"""

    # The server-assigned name, which is only unique within the same service that
    # originally returns it. If you use the default HTTP mapping, the
    # `name` should be a resource name ending with `operations/{unique_id}`.
    name: str

    # Service-specific metadata associated with the operation.  It typically
    # contains progress information and common metadata such as create time.
    # Some services might not provide such metadata.  Any method that returns a
    # long-running operation should document the metadata type, if any.
    metadata: MetaT

    # If the value is `false`, it means the operation is still in progress.
    # If `true`, the operation is completed, and either `error` or `response` is
    # available.
    done: bool = False

    # The operation result, which can be either an `error` or a valid `response`.
    # If `done` == `false`, neither `error` nor `response` is set.
    # If `done` == `true`, exactly one of `error` or `response` is set.
    result: Union[None, ErrorT, ResponseT] = None

    # The error result of the operation in case of failure or cancellation.

    # The normal response of the operation in case of success.  If the original
    # method returns no data on success, such as `Delete`, the response is
    # None .  If the original method is standard
    # `Get`/`Create`/`Update`, the response should be the resource.  For other
    # methods, the response should have the type `XxxResponse`, where `Xxx`
    # is the original method name.  For example, if the original method name
    # is `TakeSnapshot()`, the inferred response type is
    # `TakeSnapshotResponse`.


# The request message for [Operations.ListOperations][google.longrunning.Operations.ListOperations].
class ListOperationsRequest(BaseModel):
    # The name of the operation's parent resource.
    name: str

    # The standard list filter.
    filter: str

    # The standard list page size.
    page_size: PositiveInt

    # The standard list page token.
    page_token: str


# The response message for [Operations.ListOperations][google.longrunning.Operations.ListOperations].
class ListOperationsResponse(BaseModel):
    # list of operations that matches the specified filter in the request.
    operations: list[Operation]

    # The standard List next-page token.
    next_page_token: str


class GetOperationRequest(BaseModel):
    #  The name of the operation resource
    name: str


# SERVICES ---------------------------------


class OperationsService(ABC):
    """Manages long-running operations with an API service."""

    # When an API method normally takes long time to complete, it can be designed
    # to return [Operation][google.longrunning.Operation] to the client, and the client can use this
    # interface to receive the real response asynchronously by polling the
    # operation resource, or pass the operation resource to another API (such as
    # Google Cloud Pub/Sub API) to receive the response.  Any API service that
    # returns long-running operations should implement the `Operations` interface
    # so developers can have a consistent client experience.

    @abstractmethod
    def list_operations(self, request: ListOperationsRequest) -> ListOperationsResponse:
        """
        Lists operations that match the specified filter in the request. If the
        server doesn't support this method, it returns `UNIMPLEMENTED`.

        NOTE: the `name` binding allows API services to override the binding
        to use different resource name schemes, such as `users/*/operations`. To
        override the binding, API services can add a binding such as
        `"/v1/{name=users/*}/operations"` to their service configuration.
        For backwards compatibility, the default name includes the operations
        collection id, however overriding users must ensure the name binding
        is the parent resource, without the operations collection id.
        """
        ...

    @abstractmethod
    def get_operation(self, name: str) -> Operation:
        """
        Gets the latest state of a long-running operation.  Clients can use this
        method to poll the operation result at intervals as recommended by the API
        service.
        """
        ...

    @abstractmethod
    def delete_operation(self, name: str) -> None:
        """
        Deletes a long-running operation. This method indicates that the client is
        no longer interested in the operation result. It does not cancel the
        operation. If the server doesn't support this method, it returns
        `google.rpc.Code.UNIMPLEMENTED`.
        """
        # name:  The name of the operation resource to be deleted.
        ...

    @abstractmethod
    def cancel_operation(self, name: str) -> None:
        """
        Starts asynchronous cancellation on a long-running operation.  The server
        makes a best effort to cancel the operation, but success is not
        guaranteed.  If the server doesn't support this method, it returns
        `google.rpc.Code.UNIMPLEMENTED`.  Clients can use
        [Operations.GetOperation][google.longrunning.Operations.GetOperation] or
        other methods to check whether the cancellation succeeded or whether the
        operation completed despite cancellation. On successful cancellation,
        the operation is not deleted; instead, it becomes an operation with
        an [Operation.error][google.longrunning.Operation.error] value with a [google.rpc.Status.code][google.rpc.Status.code] of 1,
        corresponding to `Code.CANCELLED`.

        """
        # name:  The name of the operation resource to be cancelled.
        ...

    def wait_operation(
        self, name: str, timeout: Optional[PositiveInt] = None
    ) -> Operation:
        """
        Waits until the specified long-running operation is done or reaches at most
        a specified timeout, returning the latest state.  If the operation is
        already done, the latest state is immediately returned.  If the timeout
        specified is greater than the default HTTP/RPC timeout, the HTTP/RPC
        timeout is used.  If the server does not support this method, it returns
        `google.rpc.Code.UNIMPLEMENTED`.
        Note that this method is on a best-effort basis.  It may return the latest
        state before the specified timeout (including immediately), meaning even an
        immediate response is no guarantee that the operation is done.
        """
        # timeout: The maximum duration to wait before timing out. If left blank, the wait
        # will be at most the time permitted by the underlying HTTP/RPC protocol.
        # If RPC context deadline is also specified, the shorter one will be used.
        ...
