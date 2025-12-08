"""
Stripe Prices API Routes
Endpoints for managing and fetching Stripe price IDs.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from app.services.stripe_price_manager import stripe_price_manager
from app.core.logger import get_logger

logger = get_logger('api.stripe_prices')

router = APIRouter(prefix="/stripe/prices", tags=["stripe-prices"])


@router.get("/all")
async def get_all_price_ids():
    """
    Get or create all Stripe price IDs for all plans.
    Returns the price IDs that should be used in the frontend.
    """
    if not stripe_price_manager.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Please contact support."
        )
    
    try:
        # Ensure Pro and Enterprise have proper sections
        stripe_price_manager.ensure_plan_sections()
        
        # Get or create all price IDs
        price_ids = stripe_price_manager.get_all_price_ids()
        
        logger.info(f"Retrieved price IDs: {price_ids}")
        
        return {
            "success": True,
            "price_ids": price_ids,
            "plans": {
                "Starter": {
                    "price_id": price_ids.get("Starter"),
                    "name": "Starter Plan",
                    "amount": 0,
                    "currency": "usd"
                },
                "Pro": {
                    "price_id": price_ids.get("Pro"),
                    "name": "Pro Plan",
                    "amount": 2900,
                    "currency": "usd",
                    "section": "premium",
                    "metadata": {
                        "plan_type": "pro",
                        "tier": "professional"
                    }
                },
                "Enterprise": {
                    "price_id": price_ids.get("Enterprise"),
                    "name": "Enterprise Plan",
                    "amount": 9900,
                    "currency": "usd",
                    "section": "premium",
                    "metadata": {
                        "plan_type": "enterprise",
                        "tier": "enterprise"
                    }
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting price IDs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get price IDs: {str(e)}"
        )


@router.post("/ensure-sections")
async def ensure_plan_sections():
    """
    Ensure Pro and Enterprise plans have proper section/metadata configuration.
    This endpoint can be called to verify/update plan configurations.
    """
    if not stripe_price_manager.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Please contact support."
        )
    
    try:
        success = stripe_price_manager.ensure_plan_sections()
        
        if success:
            return {
                "success": True,
                "message": "All plan sections configured successfully"
            }
        else:
            return {
                "success": False,
                "message": "Some plan sections could not be configured"
            }
        
    except Exception as e:
        logger.error(f"Error ensuring plan sections: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to ensure plan sections: {str(e)}"
        )

