# Paystack visibility payments (test mode)

Fair Measure uses **Paystack** for two one-time ZAR unlocks when payment keys are set:

| Product | Default test price | Effect |
| --- | --- | --- |
| Private competition | R99 | Sets `is_private=True`, clears landing |
| Landing page placement | R149 | Sets `show_on_landing=True` (public only) |

Creating and running competitions stays free in year one. Turning **off** private or landing stays free.

## Environment

Set these on the web service (Render Dashboard or `render.yaml` secrets):

- `PAYSTACK_SECRET_KEY` — Paystack **test** secret (`sk_test_…`)
- `PAYSTACK_PUBLIC_KEY` — Paystack **test** public (`pk_test_…`)
- `PAYSTACK_WEBHOOK_SECRET` — optional; defaults to the secret key for HMAC verification
- `BILLING_PRIVATE_CENTS` — optional override (default `9900`)
- `BILLING_LANDING_CENTS` — optional override (default `14900`)

If `PAYSTACK_SECRET_KEY` is empty:

- **Local/dev** (`BILLING_STUB=true`, the default in `config.settings.dev`): Setup still opens a **test payment popup**. Confirming calls `POST /billing/checkouts/:ref/complete-stub` and unlocks the flag without a card.
- **Production** (`BILLING_STUB` false): visibility toggles stay free until Paystack keys are set.

## Webhook

In the Paystack dashboard (Test mode):

1. Settings → API Keys & Webhooks
2. Add webhook URL: `https://fairmeasure-v2.onrender.com/api/v1/billing/paystack/webhook`
3. Subscribe to `charge.success`

Local return URL after redirect checkout:

`{PUBLIC_APP_ORIGIN}/tabs/billing/return?reference=…&competition=…`

## Test cards

Use Paystack’s published test cards (for example the success card `4084084084084081`). OTP and PIN flows follow Paystack’s test docs.

## API

- `GET /api/v1/billing/config` — `{ enabled, public_key, private_cents, landing_cents, … }`
- `POST /api/v1/billing/checkouts` — `{ competition_id, kind: "private"|"landing" }` (admin/owner)
- `GET /api/v1/billing/checkouts/:reference` — status (also verifies with Paystack if still pending)
- `POST /api/v1/billing/paystack/webhook` — Paystack server events
