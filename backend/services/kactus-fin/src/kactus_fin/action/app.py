"""Action-link feature registration."""

from __future__ import annotations

from kactus_common.app_registry import KactusApp
from kactus_fin.action.api import router

action_app = KactusApp(
    name="action",
    # Session required on both verbs — the token pre-authorises an action, it
    # does not authenticate whoever is holding the link.
    session_routes=[router],
)
