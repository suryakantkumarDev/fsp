from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from typing import Dict, Any, List
import logging

from models.subscription import SubscriptionCreate, SubscriptionResponse, SubscriptionUpdate, Plan, DEFAULT_PLANS
from services import subscription_service, email_service
from models.subscription import subscriptions  # Add this line to import subscriptions
from middleware.auth import get_current_user, require_verified_email
router = APIRouter()
logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/plans", response_model=List[Plan])
async def get_all_plans():
    """Get all available subscription plans"""
    plans = await subscription_service.get_all_plans()
    return plans

@router.get("/current")
async def get_current_subscription(current_user = Depends(get_current_user)):
    """Get current subscription"""
    try:
        logger.info(f"Processing subscription request for user ID: {current_user.get('_id')}")
        
        if not current_user or not current_user.get("_id"):
            logger.error("Invalid user data in token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication"
            )

        user_id = str(current_user["_id"])
        
        # Log the actual MongoDB query
        logger.info(f"Querying subscription for user_id: {user_id}")
        
        # Get subscription
        subscription = await subscriptions.find_one({"user_id": user_id})
        logger.info(f"Found subscription: {subscription is not None}")

        return {
            "success": True,
            "subscription": subscription,
            "message": "Subscription fetched successfully"
        }

    except Exception as e:
        logger.error(f"Error in get_current_subscription: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/subscribe", response_model=SubscriptionResponse)
async def subscribe(
    subscription_data: SubscriptionCreate,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Subscribe to a plan"""
    success, subscription, error = await subscription_service.update_subscription(
        user_id=current_user["_id"],
        plan_id=subscription_data.plan_id,
        payment_id=subscription_data.payment_id,
        auto_renew=subscription_data.auto_renew
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Get plan details for email
    plan = await subscription_service.get_plan_by_id(subscription_data.plan_id)
    
    # Send subscription update email in background
    background_tasks.add_task(
        email_service.send_subscription_update_email,
        current_user["email"],
        current_user["name"],
        plan["name"],
        subscription["end_date"].strftime("%Y-%m-%d")
    )
    
    return subscription

@router.post("/cancel", response_model=Dict[str, str])
async def cancel_subscription(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Cancel current subscription"""
    success, error = await subscription_service.cancel_subscription(current_user["_id"])
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return {"message": "Subscription cancelled successfully"}

@router.get("/status")
async def get_subscription_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user's subscription status - auth required but not verification"""
    try:
        return {
            "subscription": current_user.get("subscription", {}),
            "is_verified": current_user.get("is_verified", False)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch subscription status"
        )

@router.get("/plans")
async def get_plans():
    """Get available subscription plans - no auth required"""
    return DEFAULT_PLANS

@router.get("/history")
async def get_subscription_history(current_user: Dict[str, Any] = Depends(get_current_user)):
    # Add your subscription history logic here
    return []

@router.post("/create-checkout", dependencies=[Depends(require_verified_email)])
async def create_checkout_session(
    plan_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create checkout session - requires verification"""
    # Add your checkout session creation logic here
    return {"sessionId": "mock-session-id"}

@router.get("/verify/{session_id}")
async def verify_payment(session_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    # Add your payment verification logic here
    return {"status": "success"}