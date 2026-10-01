import logging
import logging.handlers
import multiprocessing
from multiprocessing.queues import Queue


class _LogRecordTreeHandler(logging.Handler):
    """
    Replays log records created inside worker processes into the local logging tree,
    so that they are processed exactly like records created in this process (the
    configured handlers, the loggers' filters, pytest's capture, ...)
    """

    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


class _LogForwardingListener(logging.handlers.QueueListener):
    """listener forwarding the log records created inside worker processes"""

    queue: Queue[logging.LogRecord]

    def __init__(self, log_queue: Queue[logging.LogRecord]) -> None:
        super().__init__(log_queue, _LogRecordTreeHandler())


def create_log_listener() -> _LogForwardingListener:
    """creates the parent-side listener forwarding the worker's log records into this process"""
    return _LogForwardingListener(multiprocessing.Queue())


def setup_log_forwarding(log_queue: Queue[logging.LogRecord]) -> None:
    # NOTE: runs in the created process

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(logging.handlers.QueueHandler(log_queue))
