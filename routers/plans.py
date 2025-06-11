from fastapi import APIRouter, HTTPException, Query
from models.plan import Plan, UpdatePlan, BillingPeriod
from models.database import db
from bson import ObjectId

router = APIRouter()

DEFAULT_PLAN_TITLES = [
    "Free Starter",
    "Pro Monthly",
    "Business Monthly",
    "Pro Yearly",
    "Business Yearly",
    "Enterprise Yearly"
]

def enrich_plan_data(plan: dict) -> dict:
    """Add computed fields to plan data"""
    if plan.get("original_price") and plan.get("price"):
        plan["savings"] = round(plan["original_price"] - plan["price"], 2)
        if plan["billing_period"] == "yearly":
            plan["monthly_price"] = round(plan["price"] / 12, 2)
    return plan

# Fetch all plans with optional billing period filter
@router.get("")
async def get_plans(billing_period: BillingPeriod | None = Query(None)):
    filter_query = {}
    if billing_period:
        filter_query["billing_period"] = billing_period

    cursor = db.plans.find(filter_query)
    plans = await cursor.to_list(length=None)
    for plan in plans:
        plan["_id"] = str(plan["_id"])
        plan["features"] = [str(f) for f in plan["features"]]
        plan = enrich_plan_data(plan)
    return plans

# Get single plan
@router.get("/{plan_id}")
async def get_plan(plan_id: str):
    plan = await db.plans.find_one({"_id": ObjectId(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan["_id"] = str(plan["_id"])
    plan["features"] = [str(f) for f in plan["features"]]
    plan = enrich_plan_data(plan)
    return plan

# Update Plan - only allow editing default plans
@router.patch("/{plan_id}/edit")
async def update_plan(plan_id: str, updated_data: UpdatePlan):
    plan = await db.plans.find_one({"_id": ObjectId(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check if this is a default plan
    if plan["title"] not in DEFAULT_PLAN_TITLES:
        raise HTTPException(
            status_code=403, 
            detail="Only default plans can be modified"
        )

    # Prevent changing the title or billing period
    if updated_data.title is not None or updated_data.billing_period is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot change plan title or billing period"
        )

    update_data = {k: v for k, v in updated_data.dict().items() 
                  if v is not None and k not in ['title', 'billing_period']}

    if "features" in update_data:
        feature_cursor = db.features.find({"_id": {"$in": [ObjectId(f) for f in update_data["features"]]}})
        valid_features = await feature_cursor.to_list(length=None)
        if len(valid_features) != len(update_data["features"]):
            raise HTTPException(status_code=400, detail="Invalid feature IDs")
        update_data["features"] = [ObjectId(f) for f in update_data["features"]]

    await db.plans.update_one({"_id": ObjectId(plan_id)}, {"$set": update_data})
    return {"message": "Plan updated successfully"}
