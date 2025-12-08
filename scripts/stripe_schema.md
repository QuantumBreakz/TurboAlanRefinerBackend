# Stripe Collections Schema Documentation

This document describes the MongoDB collections used for Stripe payment and subscription management.

## Collections

### 1. customers

Stores Stripe customer records linked to users.

```javascript
{
  _id: ObjectId,
  user_id: String (UUID), // Internal user ID
  stripe_customer_id: String, // Stripe customer ID (unique)
  email: String,
  name: String (optional),
  created_at: Date,
  updated_at: Date
}
```

**Indexes:**
- `user_id` (unique)
- `stripe_customer_id` (unique)
- `email`

### 2. subscriptions

Stores subscription records from Stripe.

```javascript
{
  _id: ObjectId,
  subscription_id: String, // Stripe subscription ID (unique)
  user_id: String (UUID),
  customer_id: String, // Stripe customer ID
  status: String, // 'active', 'trialing', 'past_due', 'canceled', 'unpaid', 'incomplete', 'incomplete_expired', 'cancelled'
  price_id: String, // Stripe price ID
  current_period_start: Date,
  current_period_end: Date,
  cancel_at_period_end: Boolean,
  metadata: Object (optional),
  created_at: Date,
  updated_at: Date
}
```

**Indexes:**
- `subscription_id` (unique)
- `user_id`
- `customer_id`
- `status`
- `created_at` (descending)

### 3. payments

Stores payment records from Stripe invoices.

```javascript
{
  _id: ObjectId,
  payment_intent_id: String, // Stripe payment intent ID (unique)
  user_id: String (UUID),
  customer_id: String, // Stripe customer ID
  subscription_id: String (optional), // Stripe subscription ID
  amount: Number, // Amount in cents
  currency: String, // e.g., 'usd'
  status: String, // 'succeeded', 'failed', 'pending', etc.
  metadata: Object (optional),
  created_at: Date
}
```

**Indexes:**
- `payment_intent_id` (unique)
- `user_id`
- `customer_id`
- `subscription_id`
- `status`
- `created_at` (descending)

## Webhook Events Handled

The Stripe service handles the following webhook events:

1. **checkout.session.completed** - When a checkout session is completed
2. **customer.subscription.created** - When a subscription is created
3. **customer.subscription.updated** - When a subscription is updated
4. **customer.subscription.deleted** - When a subscription is deleted
5. **invoice.payment_succeeded** - When an invoice payment succeeds
6. **invoice.payment_failed** - When an invoice payment fails

## Setup Instructions

1. **Create Stripe Account**: Sign up at https://stripe.com
2. **Get API Keys**: 
   - Go to https://dashboard.stripe.com/apikeys
   - Copy your Secret Key and Publishable Key
   - Add them to your environment variables
3. **Create Products and Prices**:
   - Go to https://dashboard.stripe.com/products
   - Create products for your subscription tiers
   - Create prices for each product (recurring subscriptions)
   - Note the Price IDs (e.g., `price_xxxxx`)
4. **Set up Webhook**:
   - Go to https://dashboard.stripe.com/webhooks
   - Add endpoint: `https://your-backend-url.com/stripe/webhook`
   - Select events to listen to:
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.payment_succeeded`
     - `invoice.payment_failed`
   - Copy the webhook signing secret
   - Add it to your environment variables as `STRIPE_WEBHOOK_SECRET`
5. **Configure Customer Portal** (optional):
   - Go to https://dashboard.stripe.com/settings/billing/portal
   - Configure the customer portal settings
   - Enable features like subscription cancellation, payment method updates, etc.

## Testing

Use Stripe test mode for development:
- Test card: `4242 4242 4242 4242`
- Any future expiry date
- Any 3-digit CVC
- Any ZIP code

For more test cards, see: https://stripe.com/docs/testing

