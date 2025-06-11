from pydantic import BaseModel, validator
from typing import List, Optional
from enum import Enum

class BillingPeriod(str, Enum):
    FREE = "free"
    MONTHLY = "monthly"
    YEARLY = "yearly"

class Plan(BaseModel):
    title: str
    description: str
    price: float
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    features: List[str]
    billing_period: BillingPeriod

    @validator('discount_percentage')
    def validate_discount(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Discount percentage must be between 0 and 100')
        return v

class UpdatePlan(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    features: Optional[List[str]] = None
    billing_period: Optional[BillingPeriod] = None
