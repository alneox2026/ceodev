"""Lazy Firestore client access for Billing API operations."""

from __future__ import annotations

import threading
from typing import Any

from services.billing_api.app.core.config import get_settings


_firestore_client: Any | None = None
_firestore_client_lock = threading.Lock()


def get_firestore_client() -> Any:
    global _firestore_client
    if _firestore_client is None:
        with _firestore_client_lock:
            if _firestore_client is None:
                from google.cloud import firestore

                _firestore_client = firestore.Client(project=get_settings().project_id)
    return _firestore_client
