from datetime import datetime, timezone

import pytest

from common.billing import customer_wallet_document_id
from services.agent_persistence_worker.app.core.config import get_settings
from services.agent_persistence_worker.app.services import billing_reconciliation
from services.agent_persistence_worker.app.services.billing_reconciliation import (
    BillingReconciliationService,
)
from tests.unit.test_wallet_reservations import FakeClient


@pytest.fixture(autouse=True)
def _reset_worker_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _run_transaction(client, operation):
    return operation(client.transaction())


def test_expired_reservation_releases_held_credit_when_no_ledger_exists(monkeypatch):
    client = FakeClient()
    user_id = "user-1"
    wallet_id = customer_wallet_document_id(user_id)
    client.documents[("customer_wallets", wallet_id)] = {
        "billing_subject_id": user_id,
        "owner_uid": user_id,
        "currency": "USD",
        "status": "active",
        "available_credit_nanos": 500_000_000,
        "reserved_credit_nanos": 500_000_000,
        "settled_usage_nanos": 0,
    }
    client.documents[("billing_reservations", "turn-1")] = {
        "reservation_id": "turn-1",
        "turn_id": "turn-1",
        "request_id": "req-1",
        "billing_subject_id": user_id,
        "owner_uid": user_id,
        "agent_id": "maxima",
        "currency": "USD",
        "reserved_amount_nanos": 500_000_000,
        "status": "reserved",
    }
    monkeypatch.setattr(
        billing_reconciliation,
        "_run_firestore_transaction",
        _run_transaction,
    )
    service = BillingReconciliationService(
        firestore_client_factory=lambda: client,
    )

    released = service._release_expired_reservation_sync(
        client,
        client.documents[("billing_reservations", "turn-1")],
        datetime(2026, 8, 11, 11, 0, tzinfo=timezone.utc),
    )

    assert released is True
    wallet = client.documents[("customer_wallets", wallet_id)]
    assert wallet["available_credit_nanos"] == 1_000_000_000
    assert wallet["reserved_credit_nanos"] == 0
    reservation = client.documents[("billing_reservations", "turn-1")]
    assert reservation["status"] == "expired_released"
    transaction = client.documents[("wallet_transactions", "reservation_expired_turn-1")]
    assert transaction["transaction_type"] == "reservation_expiry_release"
    assert transaction["released_amount_nanos"] == 500_000_000
