import aiohttp
from typing import Optional, Dict, Any, Tuple
from config import settings
import logging
import json

logger = logging.getLogger(__name__)

# Add a simple in-memory cache for recently used codes
_used_codes = set()

async def exchange_code_for_token(code: str) -> Optional[Dict[str, str]]:
    """Exchange authorization code for tokens"""
    try:
        # Check if code was already used
        if code in _used_codes:
            logger.warning(f"Code already used: {code[:10]}...")
            return None
            
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI
        }
        
        logger.info(f"Attempting token exchange with payload: {json.dumps(payload, indent=2)}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                token_url,
                data=payload,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
                },
                ssl=True,
                timeout=30
            ) as response:
                try:
                    response_data = await response.json()
                except Exception as e:
                    response_text = await response.text()
                    logger.error(f"Failed to parse response as JSON: {response_text}")
                    raise e

                if response.status != 200:
                    logger.error(f"Token exchange failed with status {response.status}")
                    logger.error(f"Response data: {json.dumps(response_data, indent=2)}")
                    return None

                # Mark code as used only on successful exchange
                _used_codes.add(code)
                logger.info("Token exchange successful")
                return response_data

    except Exception as e:
        logger.error(f"Token exchange error: {str(e)}", exc_info=True)
        return None

async def get_google_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user profile from Google"""
    try:
        url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to get user info: {await response.text()}")
                    return None
                return await response.json()

    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        return None

async def handle_google_auth(code: str) -> Tuple[bool, Dict[str, Any], str]:
    """Complete Google OAuth flow"""
    try:
        if not code:
            return False, {}, "Authorization code is required"

        # Exchange code for tokens
        tokens = await exchange_code_for_token(code)
        if not tokens:
            return False, {}, "Failed to exchange code for tokens"

        # Get user info using the access token
        user_info = await get_google_user_info(tokens["access_token"])
        if not user_info:
            return False, {}, "Failed to get user information"

        if "email" not in user_info:
            return False, {}, "Email not found in user info"

        # Return cleaned user data
        return True, {
            "email": user_info["email"],
            "name": user_info.get("name", user_info["email"].split("@")[0]),
            "picture": user_info.get("picture"),
            "verified_email": user_info.get("verified_email", False)
        }, ""

    except Exception as e:
        logger.error(f"Google auth error: {str(e)}", exc_info=True)
        return False, {}, f"Authentication failed: {str(e)}"
