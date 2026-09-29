"""Centralized observer event labels (signals)

Labels used with the observer pattern (``servicelib.aiohttp.observer``) to
``emit()`` events and ``register_observer()`` handlers across domains
(e.g. login emits, wallets/socketio observe).

Keeping them here centralizes the names and, since this module is a pure leaf
(it must never import from the service graph), importing it cannot create
cross-domain dependencies or cycles.
"""

from typing import Annotated, Final

from annotated_types import doc

SIGNAL_ON_USER_CONFIRMATION: Final[
    Annotated[
        str,
        doc(
            "Emitted when a user is confirmed into a product for the first time."
            " Payload (keyword arguments): user_id, product_name, extra_credits_in_usd."
        ),
    ]
] = "SIGNAL_ON_USER_CONFIRMATION"

SIGNAL_USER_CONNECTED: Final[
    Annotated[
        str,
        doc(
            "Emitted when a user's socketio client connects."
            " Payload (positional arguments): user_id, app, product_name, client_session_id."
        ),
    ]
] = "SIGNAL_USER_CONNECTED"

SIGNAL_USER_DISCONNECTED: Final[
    Annotated[
        str,
        doc(
            "Emitted when a user's socketio client disconnects."
            " Payload (positional arguments): user_id, client_session_id, app, product_name."
        ),
    ]
] = "SIGNAL_USER_DISCONNECTED"

SIGNAL_USER_LOGOUT: Final[
    Annotated[
        str,
        doc("Emitted when a user logs out. Payload (positional arguments): user_id, client_session_id, app."),
    ]
] = "SIGNAL_USER_LOGOUT"

__all__: tuple[str, ...] = (
    "SIGNAL_ON_USER_CONFIRMATION",
    "SIGNAL_USER_CONNECTED",
    "SIGNAL_USER_DISCONNECTED",
    "SIGNAL_USER_LOGOUT",
)
