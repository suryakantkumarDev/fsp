from typing import Dict, Any, Tuple, List, Optional
import motor.motor_asyncio
from datetime import datetime, timedelta
from config import settings
from models.subscription import DEFAULT_PLANS, SubscriptionStatus
from services.payment_service import (
    create_stripe_payment,
    create_razorpay_order,
    verify_stripe_payment,
    verify_razorpay_payment
)
from services.email_service import send_payment_confirmation_email
import logging
from models.database import subscriptions, users
from bson import ObjectId

logger = logging.getLogger(__name__)

# MongoDB connection
client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL)
db = client[settings.DB_NAME]
users_collection = db["users"]
plans_collection = db["plans"]

async def setup_default_plans():
    """Initialize default subscription plans if they don't exist"""
    for plan in DEFAULT_PLANS:
        await plans_collection.update_one(
            {"id": plan["id"]},
            {"$set": plan},
            upsert=True
        )

async def get_all_plans() -> List[Dict[str, Any]]:
    """Get all available subscription plans"""
    return DEFAULT_PLANS

async def get_plan_by_id(plan_id: str) -> Optional[Dict[str, Any]]:
    """Get plan by ID"""
    return await plans_collection.find_one({"id": plan_id, "is_active": True})

async def get_user_subscription(user_id: str) -> Dict[str, Any]:
    """Get user's current subscription"""
    try:
        # Find active subscription
        subscription = await subscriptions.find_one({
            "user_id": str(user_id),
            "status": "active",
            "end_date": {"$gt": datetime.utcnow()}
        })
        
        if subscription:
            # Get plan details
            plan = next(
                (plan for plan in DEFAULT_PLANS if plan["id"] == subscription["plan_id"]),
                None
            )
            if plan:
                subscription["plan_details"] = plan

        return {
            "success": True,
            "subscription": subscription,
            "available_plans": DEFAULT_PLANS
        }
    except Exception as e:
        logger.error(f"Error fetching subscription: {str(e)}")
        return {
            "success": False,
            "error": "Failed to fetch subscription"
        }

async def create_subscription(
    user_id: str,
    plan_id: str,
    payment_id: str = None,
    auto_renew: bool = False
) -> Tuple[bool, Dict[str, Any], str]:
    """Create or update user subscription"""
    try:
        # Get plan details
        plan = next((p for p in DEFAULT_PLANS if p["id"] == plan_id), None)
        if not plan:
            return False, None, "Invalid plan selected"

        # Calculate dates
        start_date = datetime.utcnow()
        end_date = start_date + timedelta(days=30)  # 30 days subscription

        subscription = {
            "user_id": str(user_id),
            "plan_id": plan_id,
            "status": "active",
            "payment_id": payment_id,
            "auto_renew": auto_renew,
            "start_date": start_date,
            "end_date": end_date,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        # Insert new subscription
        result = await subscriptions.insert_one(subscription)
        
        if result.inserted_id:
            # Update user's subscription status
            await users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": {
                    "subscription": {
                        "plan_id": plan_id,
                        "status": "active",
                        "end_date": end_date
                    }
                }}
            )
            
            subscription["_id"] = str(result.inserted_id)
            subscription["plan_details"] = plan
            return True, subscription, ""
            
        return False, None, "Failed to create subscription"

    except Exception as e:
        logger.error(f"Error creating subscription: {str(e)}")
        return False, None, str(e)

async def update_subscription(
    user_id: str, 
    plan_id: str,
    payment_id: Optional[str] = None,
    auto_renew: bool = False,
    duration_days: int = 30
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Update user subscription
    Returns (success, updated_subscription, error_message)
    """
    # Get current user data
    user = await users_collection.find_one({"_id": user_id})
    if not user:
        return False, None, "User not found"
    
    # Get plan data
    plan = await get_plan_by_id(plan_id)
    if not plan:
        return False, None, "Plan not found"
    
    # Calculate subscription dates
    now = datetime.utcnow()
    end_date = now + timedelta(days=duration_days)
    
    # Create updated subscription data
    subscription = {
        "plan_id": plan_id,
        "status": SubscriptionStatus.ACTIVE,
        "start_date": now,
        "end_date": end_date,
        "auto_renew": auto_renew,
        "payment_id": payment_id
    }
    
    # Update user in database
    await users_collection.update_one(
        {"_id": user_id},
        {
            "$set": {
                "subscription": subscription,
                "updated_at": now
            }
        }
    )
    
    # Get updated user
    updated_user = await users_collection.find_one({"_id": user_id})
    return True, updated_user.get("subscription"), ""

async def cancel_subscription(user_id: str) -> Tuple[bool, str]:
    """
    Cancel user subscription (will remain active until end date)
    Returns (success, error_message)
    """
    # Get current user data
    user = await users_collection.find_one({"_id": user_id})
    if not user:
        return False, "User not found"
    
    subscription = user.get("subscription", {})
    
    # Update subscription status
    subscription["status"] = SubscriptionStatus.CANCELLED
    subscription["auto_renew"] = False
    
    # Update user in database
    await users_collection.update_one(
        {"_id": user_id},
        {
            "$set": {
                "subscription": subscription,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    return True, ""

async def check_expired_subscriptions():
    """
    Check and update expired subscriptions
    This should be run as a scheduled task
    """
    now = datetime.utcnow()
    
    # Find users with active subscriptions that have expired
    users = users_collection.find({
        "subscription.status": SubscriptionStatus.ACTIVE,
        "subscription.end_date": {"$lt": now}
    })
    
    async for user in users:
        subscription = user.get("subscription", {})
        
        if subscription.get("auto_renew"):
            # TODO: Implement automatic renewal logic here
            # This would involve payment processing, which is outside the scope
            pass
        else:
            # Mark as expired
            subscription["status"] = SubscriptionStatus.EXPIRED
            
            # If it's not free plan, downgrade to free plan
            if subscription.get("plan_id") != settings.FREE_PLAN_ID:
                subscription["plan_id"] = settings.FREE_PLAN_ID
                subscription["start_date"] = now
                subscription["end_date"] = now + timedelta(days=settings.DEFAULT_SUBSCRIPTION_DAYS)
                subscription["status"] = SubscriptionStatus.ACTIVE
            
            # Update user in database
            await users_collection.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "subscription": subscription,
                        "updated_at": now
                    }
                }
            )

async def create_subscription_payment(
    user_id: str,
    plan_id: str,
    payment_method: str,
    currency: str = "USD"
) -> Dict[str, Any]:
    try:
        plan = await get_plan_by_id(plan_id)
        if not plan:
            raise ValueError("Invalid plan")
            
        if payment_method == "stripe":
            return await create_stripe_payment(plan["price"], currency)
        elif payment_method == "razorpay":
            return await create_razorpay_order(plan["price"], currency)
        else:
            raise ValueError("Invalid payment method")
    except ImportError:
        raise ValueError(f"Payment method {payment_method} is not configured")
    except Exception as e:
        raise ValueError(str(e))

async def process_payment_webhook(
    payment_method: str,
    payment_data: Dict[str, Any]
) -> Tuple[bool, str]:
    try:
        if payment_method == "stripe":
            success, status = await verify_stripe_payment(payment_data["payment_intent_id"])
        elif payment_method == "razorpay":
            success = await verify_razorpay_payment(
                payment_data["order_id"],
                payment_data["payment_id"],
                payment_data["signature"]
            )
            status = "succeeded" if success else "failed"
        else:
            return False, "Invalid payment method"

        if success:
            # Update subscription and send confirmation
            user_id = payment_data["metadata"]["user_id"]
            plan_id = payment_data["metadata"]["plan_id"]
            
            await update_subscription(
                user_id=user_id,
                plan_id=plan_id,
                payment_id=payment_data["payment_id"]
            )

        return success, status
    except Exception as e:
        return False, str(e)