from typing import Optional, Dict, Any
import aiohttp
from config import settings
from models.database import users
from services.auth_service import generate_auth_tokens, create_user

async def get_google_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Fetch user info from Google"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://www.googleapis.com/oauth2/v1/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        ) as response:
            if response.status == 200:
                return await response.json()
    return None

async def get_linkedin_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Fetch user info from LinkedIn"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            'https://api.linkedin.com/v2/me',
            headers={'Authorization': f'Bearer {access_token}'}
        ) as response:
            if response.status == 200:
                profile = await response.json()
                # Get email address in a separate call
                async with session.get(
                    'https://api.linkedin.com/v2/emailAddress',
                    headers={'Authorization': f'Bearer {access_token}'}
                ) as email_response:
                    if email_response.status == 200:
                        email_data = await email_response.json()
                        profile['email'] = email_data.get('emailAddress')
                        return profile
    return None

async def handle_social_login(provider: str, access_token: str) -> Dict[str, Any]:
    """Handle social login flow"""
    user_info = None
    if provider == "google":
        user_info = await get_google_user_info(access_token)
    elif provider == "linkedin":
        user_info = await get_linkedin_user_info(access_token)
    
    if not user_info:
        return {"success": False, "error": "Failed to get user info"}

    # Check if user exists
    existing_user = await users.find_one({
        f"social_accounts.{provider}_id": user_info.get("id")
    })

    if existing_user:
        tokens = await generate_auth_tokens(existing_user)
        return {
            "success": True,
            "tokens": tokens,
            "user": existing_user
        }

    # Create new user
    new_user = await create_user(
        email=user_info.get("email"),
        name=user_info.get("name"),
        username=user_info.get("email").split("@")[0],
        social_provider=provider,
        social_id=user_info.get("id")
    )

    if new_user:
        tokens = await generate_auth_tokens(new_user)
        return {
            "success": True,
            "tokens": tokens,
            "user": new_user
        }

    return {"success": False, "error": "Failed to create user"}
