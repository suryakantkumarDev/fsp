from fastapi import APIRouter, HTTPException
from models.feature import Feature
from models.database import db
from bson import ObjectId

router = APIRouter()

# Get all features
@router.get("")
async def get_features():
    cursor = db.features.find({})
    features = await cursor.to_list(length=None)
    for feature in features:
        feature["_id"] = str(feature["_id"])
    return features

# Add a new feature
@router.post("")
async def add_feature(feature: Feature):
    result = await db.features.insert_one(feature.dict())
    return {"feature_id": str(result.inserted_id), "message": "Feature added successfully"}

# Delete a feature
@router.delete("/{feature_id}")
async def delete_feature(feature_id: str):
    # Check if feature is used in any plans
    plan = await db.plans.find_one({"features": ObjectId(feature_id)})
    if plan:
        raise HTTPException(status_code=400, detail="Feature is in use by one or more plans")
    
    result = await db.features.delete_one({"_id": ObjectId(feature_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feature not found")
    return {"message": "Feature deleted successfully"}
