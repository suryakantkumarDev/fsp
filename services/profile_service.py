from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from bson import ObjectId
import logging
import motor.motor_asyncio  # Add this import

from config import settings
from utils.helpers import generate_name_avatar
from utils.storage import azure_storage

logger = logging.getLogger(__name__)

# MongoDB connection
client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL)
db = client[settings.DB_NAME]
users_collection = db["users"]

async def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    return await users_collection.find_one({"_id": user_id})

async def update_profile(
    user_id: str, 
    name: Optional[str] = None, 
    username: Optional[str] = None, 
    profile_image: Optional[str] = None
) -> Tuple[bool, Dict[str, Any], str]:
    """Update user profile"""
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return False, None, "User not found"
        
        update_data = {"updated_at": datetime.utcnow()}
        
        if name:
            update_data["name"] = name
            update_data["name_avatar"] = generate_name_avatar(name)
        
        if username and username != user.get("username"):
            existing = await users_collection.find_one({"username": username})
            if existing and str(existing.get("_id")) != str(user_id):
                return False, None, "Username already taken"
            update_data["username"] = username
        
        if profile_image:
            try:
                # Delete old image if exists
                old_image_url = user.get("profile_image")
                if old_image_url:
                    await azure_storage.delete_image(old_image_url)
                
                # Upload new image directly to Azure
                new_image_url = await azure_storage.upload_image(profile_image, str(user["_id"]))
                if not new_image_url:
                    return False, None, "Failed to upload profile image"
                
                update_data["profile_image"] = new_image_url
                
                # Update name avatar if needed
                if not user.get("name_avatar"):
                    update_data["name_avatar"] = generate_name_avatar(user.get("name", ""))
                
            except Exception as e:
                logger.error(f"Error processing image: {str(e)}", exc_info=True)
                return False, None, "Failed to process profile image"

        # Update user document
        result = await users_collection.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=True
        )
        
        if not result:
            return False, None, "Failed to update profile"
        
        result["_id"] = str(result["_id"])
        return True, result, ""
        
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}", exc_info=True)
        return False, None, str(e)

async def delete_profile_image(user_id: str) -> Tuple[bool, str]:
    """
    Delete user's profile image
    Returns (success, error_message)
    """
    # Get current user data
    user = await users_collection.find_one({"_id": user_id})
    if not user:
        return False, "User not found"
    
    # Remove profile image if exists
    if user.get("profile_image"):
        # Delete file
        image_path = os.path.join(settings.UPLOAD_DIR, user["profile_image"])
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                return False, f"Error deleting image: {str(e)}"
        
        # Update user in database
        await users_collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "profile_image": None,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    return True, ""

async def deactivate_account(user_id: str) -> Tuple[bool, str]:
    """
    Deactivate user account
    Returns (success, error_message)
    """
    # Update user in database
    result = await users_collection.update_one(
        {"_id": user_id},
        {
            "$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count == 0:
        return False, "User not found or already deactivated"
    
    return True, ""