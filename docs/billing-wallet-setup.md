# Prepaid agent-token billing setup

This is the first billing layer for the gateway. It charges the recorded Gemini
token estimate only; it does not yet allocate Cloud Run, Agent Runtime,
Firestore, Storage, tax, or payment-provider costs.

The $5 monthly service fee is recorded as a separate pending line item in each
active customer billing period. It is not automatically collected until the
Billing API's verified Stripe payment/webhook flow is deployed.

## Do not create or write wallets from FlutterFlow

Firestore creates collections automatically on their first backend write. Do
not create the following collections in FlutterFlow, and do not let a client
create, update, delete, or top up any document in them:

- `customer_wallets`
- `billing_reservations`
- `wallet_transactions`
- `customer_billing_periods`
- `agent_billing_ledger`
- `customer_billing_accounts`
- `stripe_webhook_events`

The public FlutterFlow app may read its own wallet balance only. Query
`customer_wallets` with `owner_uid == currentUserUid`, limit the result to one,
and display `available_credit_nanos / 1,000,000,000` as USD. Do not use a
client-side balance as authorization; the gateway checks the wallet again in a
server-side Firestore transaction.

Wallet document IDs are opaque SHA-256-derived values. Do not calculate or
store them in FlutterFlow. The `owner_uid` query is the intended read path.

## Firestore documents

All money values use integer USD nanos: `1 USD = 1,000,000,000 nanos`. Never
store currency amounts as Firestore doubles.

### `customer_wallets/{opaque_wallet_id}`

Provision this document only after a verified payment in production. For a
development-only smoke test, use the helper below, which creates the wallet and
an immutable test-credit transaction together.

| Field | Firestore type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Starts at `1`. |
| `billing_subject_id` | string | Currently the Firebase UID; later may be an organization account ID. |
| `owner_uid` | string | Firebase UID permitted to read the balance. |
| `currency` | string | Always `USD`. |
| `status` | string | `active`, `suspended`, or `closed`. |
| `available_credit_nanos` | integer | Spendable prepaid credit. |
| `reserved_credit_nanos` | integer | Credit held by active agent turns. |
| `settled_usage_nanos` | integer | Lifetime token usage debited from this wallet. |
| `lifetime_credited_nanos` | integer | Total credited value; set by payment/provisioning code. |
| `created_at`, `updated_at` | timestamp | Backend timestamps. |
| `last_reservation_at`, `last_settlement_at` | timestamp | Optional operational timestamps. |

### `billing_reservations/{turn_id}`

Created by the gateway before invoking an agent. It holds the configured
maximum per-turn credit, currently `$0.50` (`500000000` nanos), for one hour.
The worker changes it to `settled`, `settled_shortfall`, `unpriced_released`, or
`expired_released`.

Important fields: `turn_id`, `request_id`, `billing_subject_id`, `owner_uid`,
`agent_id`, `currency`, `reserved_amount_nanos`, `status`, `created_at`,
`expires_at`, `settled_at`, `released_at`, `settled_amount_nanos`,
`released_amount_nanos`, `estimated_cost_nanos`, and `shortfall_nanos`.

### `wallet_transactions/{transaction_id}`

This is immutable financial history. A completed turn creates
`usage_{turn_id}` with `transaction_type = agent_usage_debit`. Expired holds
create `reservation_expired_{turn_id}` with
`transaction_type = reservation_expiry_release`. Required fields include
`billing_subject_id`, `owner_uid`, `currency`, `turn_id`, `reservation_id`,
`ledger_document_id`, `amount_nanos`, `released_amount_nanos`,
`estimated_cost_nanos`, `shortfall_nanos`, `status`, and `created_at`.

### `customer_billing_periods/{opaque_period_id}`

Created on the first settled or unpriced turn of a calendar month. Its core
fields are `billing_subject_id`, `owner_uid`, `currency`, `period_key`
(`YYYY-MM`), `period_start`, `period_end`, `status`,
`usage_estimated_nanos`, `collected_usage_nanos`, `uncollected_usage_nanos`,
`usage_turn_count`, `unpriced_turn_count`, `monthly_service_fee_nanos`,
`monthly_service_fee_status`, `created_at`, and `updated_at`.

`monthly_service_fee_nanos` starts at `5000000000` ($5.00) and
`monthly_service_fee_status` starts as `pending_collection`. This makes the
service fee explicit and separate from provider-token usage; it is not a wallet
debit yet.

### `agent_billing_ledger/{turn_id}`

This existing immutable source of truth gains `billing_subject_id`,
`billing_reservation_id`, `billing_reservation_nanos`, and `pricing_version`.
It remains the only source used to determine the actual per-turn debit.

### `customer_billing_accounts/{opaque_billing_account_id}`

This is a private Billing API record, created by the backend before the first
Stripe Customer is created. Its document ID is an opaque SHA-256-derived value
from `billing_subject_id`; the server never accepts the document ID, Stripe
customer ID, or owner UID from FlutterFlow.

| Field | Firestore type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Starts at `1`. |
| `billing_account_id` | string | Must equal the opaque document ID. Used as the Stripe Customer creation idempotency key. |
| `billing_subject_id` | string | Current Firebase UID; can later be an organization billing account. |
| `owner_uid` | string | Current Firebase UID. Private—never readable by the client through this collection. |
| `currency` | string | Always `USD`. |
| `catalog_environment` | string | `test` or `production`; prevents test and live payment state being mixed. |
| `stripe_customer_id` | string or null | Populated only after the server creates/retrieves the Stripe Customer. |
| `stripe_customer_status` | string | `pending`, `ready`, or `failed`. |
| `stripe_subscription_id` | string or null | The separate $5/month Stripe Subscription, if started. |
| `stripe_subscription_status` | string | Starts as `not_started`; later reflects verified Stripe subscription state. |
| `stripe_subscription_current_period_start`, `stripe_subscription_current_period_end` | timestamp or null | Verified Stripe subscription period boundaries. |
| `active_checkout_request_id`, `active_checkout_session_id`, `active_checkout_url` | string or null | One short-lived, server-created Checkout Session lock per billing account. Never treat the URL as a payment receipt. |
| `active_checkout_mode`, `active_checkout_topup_package_id`, `active_checkout_created_at`, `active_checkout_expires_at` | string/timestamp or null | Server-only Checkout correlation and expiry state. |
| `created_at`, `updated_at` | timestamp | Backend timestamps. |

This record is mutable backend state, not a financial ledger. Stripe event
receipts and wallet transactions provide the immutable audit history.

### `stripe_webhook_events/{opaque_stripe_event_id}`

This is the immutable, backend-only webhook receipt and event-level
idempotency record. The document ID is a SHA-256-derived value from Stripe's
`evt_...` event ID. The Billing API creates it in the same Firestore
transaction as the resulting wallet or subscription accounting records. If it
already exists, the duplicate webhook is acknowledged without applying a
second credit or fee record.

| Field | Firestore type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Starts at `1`. |
| `stripe_event_id`, `stripe_event_type` | string | Stripe event identity and event type. |
| `stripe_event_created_at`, `processed_at` | timestamp | Stripe creation time and backend processing time. |
| `stripe_livemode` | boolean | Must match the catalog environment (`false` for test, `true` for production). |
| `catalog_environment` | string | `test` or `production`. |
| `payload_sha256` | string | SHA-256 of the verified raw event body; avoids storing the full payload. |
| `outcome` | string | `topup_credited`, `service_fee_collected`, `subscription_state_updated`, or `ignored`. |
| `billing_account_id`, `billing_subject_id`, `owner_uid` | string or null | Server-derived ownership references. |
| `stripe_customer_id`, `stripe_checkout_session_id`, `stripe_payment_intent_id`, `stripe_invoice_id`, `stripe_subscription_id` | string or null | Minimal Stripe correlation IDs. |
| `wallet_transaction_id` | string or null | Immutable financial record created for a funded top-up or paid service fee. |

Never store the `Stripe-Signature` header, webhook signing secret, payment
method/card data, or complete raw webhook body in Firestore.

## Billing API Cloud Run infrastructure

The Billing API is a separate public Cloud Run service named
`ceoagent-billing-api`. It is public only because Stripe needs to deliver an
unauthenticated HTTP webhook. This does **not** authorize wallet funding:

- the future FlutterFlow-facing Checkout endpoints verify a Firebase ID token;
- the webhook endpoint verifies the raw Stripe signature with its
  distinct `whsec_...` secret;
- the Billing API service account has Firestore data access, but no Vertex AI,
  Pub/Sub, or broad Secret Manager role;
- Secret Manager access is granted only to the exact named Stripe secrets.

Terraform injects the existing `stripe-secret-key` as `STRIPE_SECRET_KEY` from
a **pinned numeric secret version**. It does not create the secret or put its
value in Terraform state. A newly created Secret Manager secret normally has
version `1`; update `billing_api_stripe_secret_key_secret_version` whenever a
key is rotated. Do not use `latest` for an environment-variable secret.

Leave the webhook secret Terraform fields empty for now:

```hcl
billing_api_stripe_webhook_signing_secret_id      = ""
billing_api_stripe_webhook_signing_secret_version = ""
```

After the webhook route is deployed and configured in Stripe, create its
separate `whsec_...` Secret Manager secret, then set both values to the new
secret ID and its pinned numeric version. The Checkout/webhook implementation
will return `503` while this secret is intentionally absent; it will never
accept an unsigned webhook as a fallback.

The initial test-mode scaling defaults are one vCPU, 512 MiB memory,
concurrency 32, `max_instances = 50`, and `min_instances = 0`. This supports
horizontal scaling without idle test cost. Before production, run a staged
Checkout/webhook load test and choose whether to set `billing_api_min_instances = 1`
for a warm instance; also set `billing_api_deletion_protection = true`.

Build and publish the additional image with the existing helper:

```powershell
.\scripts\build_images.ps1
```

It now returns `billing_api_image` alongside the gateway and worker images.
When infrastructure deployment is approved, provide that image to
`scripts/deploy_infra.ps1` using its new `-BillingApiImage` parameter. The
example Terraform variables file includes the required image URI and Stripe
secret version fields.

## Stripe Checkout and verified webhook flow

The Billing API now exposes two public URLs on the Billing API Cloud Run
service:

| Route | Who can call it | Purpose |
| --- | --- | --- |
| `POST /v1/billing/topups/checkout-session` | FlutterFlow user with a valid Firebase ID token | Creates one server-owned Stripe Checkout Session for a catalog package. The request body is only `{"topup_package_id":"credit_5_usd"}` (or the `$10`/`$25` package ID). |
| `POST /v1/billing/stripe/webhook` | Stripe | Verifies the raw `Stripe-Signature`, retrieves Stripe objects server-side, and performs idempotent Firestore accounting. |

Do not call Stripe directly from FlutterFlow for either flow. In particular,
FlutterFlow must not send an amount, a Stripe Price ID, a UID, an account ID,
or a wallet-document ID. It sends the Firebase bearer token and one of the
server-catalog package identifiers only.

On the user's first paid top-up, the API creates a Stripe Checkout Session in
`subscription` mode with two separate line items:

1. the selected one-time token-credit Price; and
2. the recurring `$5/month` service-fee Price.

They remain separate Stripe line items and produce separate immutable records:
`stripe_topup_{checkout_session_id}` credits the wallet and
`stripe_service_fee_{invoice_id}` records the fee payment. Later top-ups use a
payment-only Checkout Session with the selected one-time Price, after the
monthly subscription is verified as active. A pending first subscription blocks
another top-up until its verified `invoice.paid` event arrives, preventing a
duplicate monthly subscription during webhook reordering.

### Configure the test-mode return URLs

Create two published FlutterFlow web routes (or equivalent HTTPS pages): a
success page and a cancellation page. The success route may show a neutral
"payment received; confirming your credit" state, but it must never add credit
itself. Set these Terraform values to the exact published routes:

```hcl
billing_api_checkout_success_url = "https://YOUR_APP_DOMAIN/billing-complete?session_id={CHECKOUT_SESSION_ID}"
billing_api_checkout_cancel_url  = "https://YOUR_APP_DOMAIN/billing-cancelled"
```

Keep the literal `{CHECKOUT_SESSION_ID}` placeholder in the success URL. The
backend rejects Checkout creation until both URLs are configured.

### Configure Stripe after the Billing API URL is available

1. Build and deploy the Billing API image through the approved Terraform
   rollout, then record the `billing_api_url` Terraform output. Do not enable
   customer charging yet.
2. In the Stripe **test-mode** Dashboard, add an endpoint at
   `https://YOUR_BILLING_API_HOST/v1/billing/stripe/webhook`.
3. Select exactly these event types for this implementation:
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
   `invoice.paid`, `invoice.payment_failed`,
   `customer.subscription.updated`, and `customer.subscription.deleted`.
4. Copy the endpoint's distinct `whsec_...` signing secret directly into a new
   GCP Secret Manager secret named `stripe-webhook-signing-secret`; do not put
   it in FlutterFlow, source code, a Terraform variable, or a chat message.
5. Pin its numeric version in Terraform and apply the configuration:

   ```hcl
   billing_api_stripe_webhook_signing_secret_id      = "stripe-webhook-signing-secret"
   billing_api_stripe_webhook_signing_secret_version = "1"
   ```

6. Perform a real test-mode top-up using Stripe's test card. Only after the
   signed webhook returns `2xx` should the user see the credited wallet
   balance. The success page is not proof of fulfillment.

For each test, verify one `stripe_webhook_events` receipt and, respectively,
one `wallet_transactions/stripe_topup_{session_id}` record or one
`wallet_transactions/stripe_service_fee_{invoice_id}` record. Re-deliver the
same event from Stripe: the receipt/transaction IDs must prevent a second
wallet credit or a second fee entry.

The checked-in catalog is explicitly **test-mode** and contains only your
three test Prices plus the test recurring fee Price. Before live payments,
create separate live-mode Prices, add a production catalog with
`environment: production`, and deploy it only with live Stripe secrets. Never
mix a test `price_...` catalog with live Stripe keys or vice versa.

## FlutterFlow/Firebase rules

Merge the following matches into your existing Firestore rules; do not replace
the rest of the application's rules with this fragment. Backend service
accounts bypass Firestore Security Rules, so application code and IAM remain
the controls for all writes.

If you already merged the original five billing collection matches, add only
the two new private-Stripe matches below. Do not create a second `match` block
for a path that already exists in your rules; consolidate its permissions in
the existing block.

```text
match /customer_wallets/{walletId} {
  allow read: if request.auth != null
              && resource.data.owner_uid == request.auth.uid;
  allow create, update, delete: if false;
}

match /wallet_transactions/{transactionId} {
  allow read: if request.auth != null
              && resource.data.owner_uid == request.auth.uid;
  allow create, update, delete: if false;
}

match /customer_billing_periods/{periodId} {
  allow read: if request.auth != null
              && resource.data.owner_uid == request.auth.uid;
  allow create, update, delete: if false;
}

match /billing_reservations/{reservationId} {
  allow read, create, update, delete: if false;
}

match /agent_billing_ledger/{turnId} {
  allow read, create, update, delete: if false;
}

match /customer_billing_accounts/{accountId} {
  allow read, create, update, delete: if false;
}

match /stripe_webhook_events/{stripeEventId} {
  allow read, create, update, delete: if false;
}
```

## Development-only wallet provisioning

Authenticate locally as an operator for the development project, then run:

```powershell
python -m pip install -r services/agent_persistence_worker/requirements.txt
python scripts/provision_test_wallet.py `
  --project-id ceo-dev123 `
  --uid FIREBASE_UID `
  --credit-usd 10.00 `
  --non-production
```

This is intentionally not a production credit mechanism. The verified Stripe
webhook now provides the production-shaped credit path: it uses the Stripe
event ID plus a source-specific transaction ID and creates the wallet credit
and `wallet_transactions` record atomically.

## Enabling the feature safely

1. Deploy the code with `billing_enforcement_enabled = false` (the default).
2. Apply the Firestore rule changes and provision a test wallet in the
   development project.
3. Set `billing_enforcement_enabled = true` and
   `billing_reconciliation_enabled = true` in the development Terraform
   variables, then deploy the gateway and worker.
4. Run buffered and streaming smoke tests with a funded UID. Confirm one
   `billing_reservations/{turn_id}`, one `agent_billing_ledger/{turn_id}`, one
   `wallet_transactions/usage_{turn_id}`, and one monthly period record.
5. Confirm that a wallet with less than the reservation amount receives a 402
   before the gateway calls an agent.
6. Let a reserved request expire in development and confirm the scheduled
   reconciliation job releases it. Review its Cloud Scheduler execution and
   worker logs.

Do not enable this for customers until each deployed agent reliably returns
usage metadata, the price catalog is reviewed, and Stripe/payment, refund,
tax, and suspension policies are implemented.
