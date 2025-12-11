"""
Payments API Routes
Webhook endpoint for Stripe payment processing.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Request
from starlette.responses import Response

from app.services.stripe_service import stripe_service
from app.core.logger import get_logger

logger = get_logger('api.payments')

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature")
):
    """
    Handle Stripe webhook events.
    
    This endpoint processes webhook events from Stripe for:
    - Subscription creation/updates/cancellations
    - Payment success/failure
    - Checkout completion
    
    Webhook URL: https://your-backend-url.com/payments/webhook
    """
    if not stripe_signature:
        logger.warning("Webhook request missing stripe-signature header")
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")
    
    try:
        # Get raw request body
        body = await request.body()
        
        # Construct and verify webhook event
        event = stripe_service.construct_webhook_event(body, stripe_signature)
        
        if not event:
            raise HTTPException(status_code=400, detail="Invalid webhook signature")
        
        # Handle the event
        success = stripe_service.handle_webhook_event(event)
        
        if not success:
            logger.warning(f"Webhook event {event.type} was not handled successfully")
            # Still return 200 to acknowledge receipt
        
        return Response(status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        # Return 400 to indicate we didn't process the event
        raise HTTPException(status_code=400, detail=f"Webhook processing failed: {str(e)}")




