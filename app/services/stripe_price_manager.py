"""
Stripe Price Manager
Dynamically creates and manages Stripe products and prices.
Ensures Pro and Enterprise plans are properly configured.
"""
from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any
import stripe
from stripe.error import StripeError

from app.core.logger import get_logger

logger = get_logger('services.stripe_price_manager')

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

if not stripe.api_key:
    logger.warning("STRIPE_SECRET_KEY not configured. Stripe price manager will not work.")


class StripePriceManager:
    """
    Manages Stripe products and prices dynamically.
    Creates products/prices if they don't exist, or fetches existing ones.
    """
    
    # Plan configurations
    PLAN_CONFIGS = {
        "Starter": {
            "name": "Starter Plan",
            "description": "Perfect for trying out Turbo Alan Refiner",
            "amount": 0,  # Free tier
            "currency": "usd",
            "interval": "month",
            "features": ["5 documents per month", "Basic refinement settings", "Standard processing speed", "Email support"]
        },
        "Pro": {
            "name": "Pro Plan",
            "description": "Ideal for content creators and professionals",
            "amount": 2900,  # $29.00 in cents
            "currency": "usd",
            "interval": "month",
            "features": [
                "Unlimited documents",
                "Advanced refinement controls",
                "Priority processing",
                "Google Drive integration",
                "Batch processing",
                "Analytics dashboard",
                "Priority support"
            ],
            "metadata": {
                "plan_type": "pro",
                "tier": "professional",
                "max_jobs": "unlimited",
                "max_passes": "6",
                "max_tokens": "100000"
            }
        },
        "Enterprise": {
            "name": "Enterprise Plan",
            "description": "For teams and organizations",
            "amount": 9900,  # $99.00 in cents (custom pricing can be set)
            "currency": "usd",
            "interval": "month",
            "features": [
                "Everything in Professional",
                "Team collaboration",
                "Custom integrations",
                "Advanced analytics",
                "Dedicated support",
                "SLA guarantee"
            ],
            "metadata": {
                "plan_type": "enterprise",
                "tier": "enterprise",
                "max_jobs": "unlimited",
                "max_passes": "unlimited",
                "max_tokens": "unlimited",
                "custom_deployment": "true"
            }
        }
    }
    
    @staticmethod
    def is_configured() -> bool:
        """Check if Stripe is properly configured."""
        return bool(stripe.api_key)
    
    @staticmethod
    def get_or_create_product(plan_name: str) -> Optional[Dict[str, Any]]:
        """
        Get existing product or create a new one for the plan.
        
        Args:
            plan_name: Plan name (Starter, Pro, Enterprise)
            
        Returns:
            Product object or None if failed
        """
        if not StripePriceManager.is_configured():
            logger.error("Stripe not configured")
            return None
        
        try:
            config = StripePriceManager.PLAN_CONFIGS.get(plan_name)
            if not config:
                logger.error(f"Unknown plan: {plan_name}")
                return None
            
            # Search for existing product by name
            try:
                products = stripe.Product.search(
                    query=f"name:'{config['name']}' AND active:'true'",
                    limit=1
                )
                
                if products.data and len(products.data) > 0:
                    product = products.data[0]
                    logger.info(f"Found existing product for {plan_name}: {product.id}")
                    return {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description
                    }
            except Exception as e:
                logger.warning(f"Product search failed, will create new product: {e}")
            
            # Create new product
            product = stripe.Product.create(
                name=config["name"],
                description=config["description"],
                metadata={
                    "plan_name": plan_name,
                    "plan_type": config.get("metadata", {}).get("plan_type", plan_name.lower())
                }
            )
            
            logger.info(f"Created new product for {plan_name}: {product.id}")
            
            return {
                "id": product.id,
                "name": product.name,
                "description": product.description
            }
            
        except StripeError as e:
            logger.error(f"Stripe error getting/creating product for {plan_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting/creating product for {plan_name}: {e}")
            return None
    
    @staticmethod
    def get_or_create_price(plan_name: str) -> Optional[str]:
        """
        Get existing price or create a new one for the plan.
        Returns the price ID.
        
        Args:
            plan_name: Plan name (Starter, Pro, Enterprise)
            
        Returns:
            Price ID or None if failed
        """
        if not StripePriceManager.is_configured():
            logger.error("Stripe not configured")
            return None
        
        try:
            config = StripePriceManager.PLAN_CONFIGS.get(plan_name)
            if not config:
                logger.error(f"Unknown plan: {plan_name}")
                return None
            
            # Get or create product first
            product = StripePriceManager.get_or_create_product(plan_name)
            if not product:
                return None
            
            product_id = product["id"]
            
            # Search for existing price for this product
            prices = stripe.Price.list(
                product=product_id,
                active=True,
                limit=10
            )
            
            # Find matching price
            for price in prices.data:
                if (price.unit_amount == config["amount"] and 
                    price.currency == config["currency"] and
                    price.recurring and 
                    price.recurring.interval == config["interval"]):
                    logger.info(f"Found existing price for {plan_name}: {price.id}")
                    return price.id
            
            # Create new price
            price_data = {
                "product": product_id,
                "unit_amount": config["amount"],
                "currency": config["currency"],
                "recurring": {
                    "interval": config["interval"]
                },
                "metadata": config.get("metadata", {})
            }
            
            price = stripe.Price.create(**price_data)
            
            logger.info(f"Created new price for {plan_name}: {price.id}")
            
            return price.id
            
        except StripeError as e:
            logger.error(f"Stripe error getting/creating price for {plan_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting/creating price for {plan_name}: {e}")
            return None
    
    @staticmethod
    def get_all_price_ids() -> Dict[str, Optional[str]]:
        """
        Get or create all price IDs for all plans.
        
        Returns:
            Dictionary mapping plan names to price IDs
        """
        return {
            "Starter": StripePriceManager.get_or_create_price("Starter"),
            "Pro": StripePriceManager.get_or_create_price("Pro"),
            "Enterprise": StripePriceManager.get_or_create_price("Enterprise")
        }
    
    @staticmethod
    def ensure_plan_sections() -> bool:
        """
        Ensure Pro and Enterprise plans have proper section/metadata configuration.
        This ensures they belong to their respective sections.
        
        Returns:
            True if all plans are properly configured
        """
        if not StripePriceManager.is_configured():
            return False
        
        try:
            all_configured = True
            
            for plan_name in ["Pro", "Enterprise"]:
                config = StripePriceManager.PLAN_CONFIGS.get(plan_name)
                if not config:
                    continue
                
                # Get or create product
                product = StripePriceManager.get_or_create_product(plan_name)
                if not product:
                    all_configured = False
                    continue
                
                # Update product metadata to ensure proper section
                try:
                    stripe.Product.modify(
                        product["id"],
                        metadata={
                            "plan_name": plan_name,
                            "plan_type": config.get("metadata", {}).get("plan_type", plan_name.lower()),
                            "tier": config.get("metadata", {}).get("tier", plan_name.lower()),
                            "section": "premium" if plan_name in ["Pro", "Enterprise"] else "basic"
                        }
                    )
                    logger.info(f"Updated metadata for {plan_name} product")
                except Exception as e:
                    logger.warning(f"Could not update product metadata for {plan_name}: {e}")
                
                # Get or create price and update its metadata
                price_id = StripePriceManager.get_or_create_price(plan_name)
                if price_id:
                    try:
                        stripe.Price.modify(
                            price_id,
                            metadata=config.get("metadata", {})
                        )
                        logger.info(f"Updated metadata for {plan_name} price")
                    except Exception as e:
                        logger.warning(f"Could not update price metadata for {plan_name}: {e}")
                else:
                    all_configured = False
            
            return all_configured
            
        except Exception as e:
            logger.error(f"Error ensuring plan sections: {e}")
            return False


# Global instance
stripe_price_manager = StripePriceManager()

