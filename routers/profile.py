from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile
from typing import Dict, Any, Optional
import logging
import jwt
from jwt import PyJWTError
from bson.objectid import ObjectId
import base64

from middleware.auth import get_current_user, require_verified_email, oauth2_scheme
from services.profile_service import (
    get_user_profile,
    update_profile,
    delete_profile_image,
    deactivate_account
)
from models.database import users, blacklisted_tokens
from datetime import datetime
from config import settings  # Changed from core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/me")
async def get_profile(token: str = Depends(oauth2_scheme)):
    """Get user profile with verification status"""
    try:
        # Decode token
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
        except PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )

        # Convert string ID to ObjectId
        try:
            user_id = ObjectId(user_id)
        except:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )

        # Get user from database
        user = await users.find_one({"_id": user_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Always return basic profile with verification status
        profile_data = {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "username": user.get("username", ""),
            "is_verified": user.get("is_verified", False),
            "profile_image": user.get("profile_image"),
            "name_avatar": user.get("name_avatar"),
            "verification_pending": not user.get("is_verified", False),
            "phone": user.get("phone"),
            "created_at": user.get("created_at", datetime.utcnow()),
            "updated_at": user.get("updated_at", datetime.utcnow())
        }

        return profile_data

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error fetching profile: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile"
        )

@router.put("/me", dependencies=[Depends(require_verified_email)])
async def update_user_profile(
    profile_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user profile with fresh data return"""
    try:
        # Extract fields from the request body
        name = profile_data.get("name")
        username = profile_data.get("username")
        profile_image = profile_data.get("profile_image")
        
        # Update profile
        success, updated_user, error = await update_profile(
            current_user["_id"],
            name,
            username,
            profile_image
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=error)
            
        # Fetch the latest user data to ensure we return the most up-to-date info
        fresh_user = await users.find_one({"_id": current_user["_id"]})
        if not fresh_user:
            raise HTTPException(status_code=404, detail="User not found after update")
            
        return {
            "id": fresh_user["_id"],
            "name": fresh_user["name"],
            "email": fresh_user["email"],
            "username": fresh_user["username"],
            "profile_image": fresh_user.get("profile_image"),
            "name_avatar": fresh_user.get("name_avatar"),
            "is_verified": fresh_user.get("is_verified", False),
            "updated_at": datetime.utcnow()
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.put("/me/profile-image")
async def update_profile_image(
    image_data: Dict[str, str],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user profile image"""
    try:
        if not image_data.get("image"):
            raise HTTPException(
                status_code=400,
                detail="Image data is required"
            )

        # Add request debouncing
        request_key = f"profile_image_upload_{current_user['_id']}"
        if hasattr(update_profile_image, 'last_request'):
            last_time = getattr(update_profile_image, 'last_request').get(request_key)
            if last_time and (datetime.utcnow() - last_time).total_seconds() < 2:
                raise HTTPException(
                    status_code=429,
                    detail="Please wait before uploading another image"
                )
        else:
            setattr(update_profile_image, 'last_request', {})

        update_profile_image.last_request[request_key] = datetime.utcnow()

        # Validate base64 data and image type
        try:
            base64_data = image_data["image"]
            if ',' not in base64_data:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid image format"
                )
            
            # Updated image type validation to include SVG
            image_type = base64_data.split(',')[0].lower()
            valid_types = ['jpeg', 'jpg', 'png', 'gif', 'webp', 'bmp', 'svg+xml', 'image/']
            if not any(type_str in image_type for type_str in valid_types):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid image format. Please upload a valid image file"
                )

        except HTTPException as he:
            raise he
        except Exception as e:
            logger.error(f"Image validation error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail="Invalid image data"
            )

        # Upload image and get URL
        success, updated_user, error = await update_profile(
            current_user["_id"],
            profile_image=image_data["image"]
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail=error
            )

        return {
            "success": True,
            "profile_image": updated_user.get("profile_image"),
            "name_avatar": updated_user.get("name_avatar")
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error updating profile image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile image"
        )

@router.delete("/me/profile-image")
async def remove_profile_image(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Remove user profile image"""
    try:
        success, error = await delete_profile_image(current_user["_id"])
        if not success:
            raise HTTPException(status_code=400, detail=error)
            
        # Fetch fresh user data after update
        fresh_user = await users.find_one({"_id": current_user["_id"]})
        
        return {
            "message": "Profile image removed successfully",
            "profile_image": fresh_user.get("profile_image"),
            "name_avatar": fresh_user.get("name_avatar")
        }
    except Exception as e:
        logger.error(f"Error removing profile image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove profile image"
        )

@router.post("/me/deactivate")
async def deactivate_user_account(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Deactivate user account"""
    try:
        success, error = await deactivate_account(current_user["_id"])
        if not success:
            raise HTTPException(status_code=400, detail=error)
        return {"message": "Account deactivated successfully"}
    except Exception as e:
        logger.error(f"Error deactivating account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate account"
        )

@router.post("/me/change-password")
async def change_password(
    request: Request,
    data: Dict[str, str],
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Change user password"""
    try:
        # Validate request data
        if not data.get("old_password") or not data.get("new_password"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both old and new passwords are required"
            )

        # Get user from database to verify password
        user = await users.find_one({"_id": ObjectId(current_user["_id"])})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Verify old password
        if not verify_password(data["old_password"], user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

        # Update password
        hashed_password = get_password_hash(data["new_password"])
        result = await users.find_one_and_update(
            {"_id": ObjectId(current_user["_id"])},
            {
                "$set": {
                    "password_hash": hashed_password,
                    "updated_at": datetime.utcnow()
                }
            },
            return_document=True
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )

        return {"success": True, "message": "Password updated successfully"}

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error changing password: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )