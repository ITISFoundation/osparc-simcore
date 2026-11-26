"""Upload certification state for output port content."""

import logging

from models_library.services_types import ServicePortKey

from ._content_monitor import Fingerprint, PortContentMonitor

_logger = logging.getLogger(__name__)


class PortUploadTrust:
    """Tracks, for one port, the fingerprint a successful upload certified as stored."""

    def __init__(self, *, port_key: ServicePortKey, monitor: PortContentMonitor) -> None:
        self._port_key = port_key
        self._monitor = monitor
        self._upload_candidate: Fingerprint | None = None
        self._uploaded_fingerprint: Fingerprint | None = None
        self._stored_content = False

    def is_certified(self, fingerprint: Fingerprint | None) -> bool:
        """True when a completed upload certified exactly this content"""
        return fingerprint is not None and self._uploaded_fingerprint == fingerprint

    def note_upload_started(self, fingerprint: Fingerprint) -> None:
        """Records the fingerprint the upload is sending, verified after the PUT."""
        self._upload_candidate = fingerprint

    def note_upload_uncertified(self) -> None:
        """Clears the certification of an unidentified PUT: its content stays eligible."""
        self._upload_candidate = None
        self._uploaded_fingerprint = None

    def has_stored_content(self) -> bool:
        """True once any PUT for this port completed in this process; survives certification invalidation"""
        return self._stored_content

    async def verify_upload_completed(self) -> bool:
        """Rescans after a successful PUT; records the content as certified unless it changed"""
        self._stored_content = True  # called only for PUTs that completed without error
        fingerprint = await self._monitor.rescan()
        unchanged = fingerprint is not None and fingerprint == self._upload_candidate
        if unchanged:
            self._uploaded_fingerprint = fingerprint
        return unchanged
