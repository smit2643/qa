# Billing Module

Location: `backend/modules/billing/`

Stripe-based subscription billing. Usage-based metering on test runs + seat-based plans.

---

## Plans

| Plan | Runs/Month | Price |
|---|---|---|
| Free | 50 | $0 |
| Pro | 5,000 | $250/mo |
| Enterprise | Unlimited | $2,500/mo |

---

## Files

| File | Responsibility |
|---|---|
| `service.py` | Stripe API calls: checkout session, webhook handling |
| `router.py` | `POST /billing/checkout`, `POST /billing/webhook` |

---

## Checkout Flow

```
1. User clicks "Upgrade to Pro" in UI
2. Frontend: POST /billing/checkout { "plan": "pro" }
3. Backend: stripe.checkout.Session.create(...)
4. Returns: { "checkout_url": "https://checkout.stripe.com/..." }
5. Frontend redirects user to Stripe-hosted checkout
6. User completes payment on Stripe
7. Stripe redirects to /dashboard?billing=success
8. Stripe fires webhook → POST /billing/webhook
9. Backend handles "checkout.session.completed" event
10. Update org subscription status in DB
```

---

## Webhook Events Handled

| Event | Action |
|---|---|
| `checkout.session.completed` | Activate subscription for org |
| `customer.subscription.deleted` | Downgrade org to free plan |
| `invoice.payment_failed` | Mark subscription past due, notify owner |

---

## Stripe Configuration

Set these in `.env`:

```bash
STRIPE_SECRET_KEY=sk_live_...       # or sk_test_... for dev
STRIPE_WEBHOOK_SECRET=whsec_...     # from Stripe dashboard → Webhooks
```

For local webhook testing:
```bash
stripe listen --forward-to localhost:8000/api/v1/billing/webhook
```

---

## Adding Price IDs

Update `PLANS` in `billing/service.py` with real Stripe price IDs from your dashboard:

```python
PLANS = {
    "free": {"runs_per_month": 50, "price_id": None},
    "pro": {"runs_per_month": 5000, "price_id": "price_1ABC..."},
    "enterprise": {"runs_per_month": -1, "price_id": "price_1XYZ..."},
}
```
