from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from models.database import subscriptions  # Import directly from database

class PlanFeature(BaseModel):
    name: str
    description: str
    value: str

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"

class Plan(BaseModel):
    id: str
    name: str
    description: str
    price: float
    billing_cycle: str  # monthly, yearly
    features: List[PlanFeature]
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SubscriptionCreate(BaseModel):
    user_id: str
    plan_id: str
    payment_id: Optional[str] = None
    auto_renew: bool = False

class SubscriptionUpdate(BaseModel):
    plan_id: Optional[str] = None
    status: Optional[SubscriptionStatus] = None
    end_date: Optional[datetime] = None
    auto_renew: Optional[bool] = None
    payment_id: Optional[str] = None

class SubscriptionResponse(BaseModel):
    user_id: str
    plan_id: str
    status: SubscriptionStatus
    start_date: datetime
    end_date: datetime
    auto_renew: bool
    payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# Pre-defined plans
FREE_PLAN = {
    "id": "free",
    "name": "Free Plan",
    "description": "Basic features for individual users",
    "price": 0.0,
    "billing_cycle": "monthly",
    "features": [
        {"name": "Feature 1", "description": "Basic feature", "value": "Limited"},
        {"name": "Feature 2", "description": "Another basic feature", "value": "5 per month"}
    ]
}

STANDARD_PLAN = {
    "id": "standard",
    "name": "Standard Plan",
    "description": "Enhanced features for professionals",
    "price": 9.99,
    "billing_cycle": "monthly",
    "features": [
        {"name": "Feature 1", "description": "Enhanced feature", "value": "Unlimited"},
        {"name": "Feature 2", "description": "Another enhanced feature", "value": "20 per month"},
        {"name": "Feature 3", "description": "Premium feature", "value": "Basic"}
    ]
}

PREMIUM_PLAN = {
    "id": "premium",
    "name": "Premium Plan",
    "description": "Complete features for businesses",
    "price": 19.99,
    "billing_cycle": "monthly",
    "features": [
        {"name": "Feature 1", "description": "Premium feature", "value": "Unlimited"},
        {"name": "Feature 2", "description": "Another premium feature", "value": "Unlimited"},
        {"name": "Feature 3", "description": "Business feature", "value": "Advanced"},
        {"name": "Feature 4", "description": "Enterprise feature", "value": "Included"}
    ]
}

DEFAULT_PLANS = [FREE_PLAN, STANDARD_PLAN, PREMIUM_PLAN]