import aiohttp
from typing import Optional, Dict, Any, Tuple
from config import settings
import logging
import json

logger = logging.getLogger(__name__)

_used_codes = set()

async def exchange_code_for_token(code: str) -> Optional[Dict[str, str]]:
    """Exchange authorization code for LinkedIn access token"""
    try:
        if code in _used_codes:
            logger.warning(f"Code already used: {code[:10]}...")
            return None
            
        token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        payload = {
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.LINKEDIN_REDIRECT_URI
        }
        
        logger.info(f"Attempting LinkedIn token exchange")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            ) as response:
                response_data = await response.json()
                
                if response.status != 200:
                    logger.error(f"LinkedIn token exchange failed: {response_data}")
                    return None

                _used_codes.add(code)
                return response_data

    except Exception as e:
        logger.error(f"LinkedIn token exchange error: {str(e)}")
        return None

async def get_linkedin_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user profile from LinkedIn"""
    try:
        # Get basic profile
        profile_url = "https://api.linkedin.com/v2/me"
        email_url = "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        async with aiohttp.ClientSession() as session:
            # Get profile data
            async with session.get(profile_url, headers=headers) as profile_response:
                if profile_response.status != 200:
                    logger.error("Failed to get LinkedIn profile")
                    return None
                profile = await profile_response.json()

            # Get email data
            async with session.get(email_url, headers=headers) as email_response:
                if email_response.status != 200:
                    logger.error("Failed to get LinkedIn email")
                    return None
                email_data = await email_response.json()

        # Extract email from response
        email = email_data.get("elements", [{}])[0].get("handle~", {}).get("emailAddress")

        return {
            "email": email,
            "name": f"{profile.get('localizedFirstName', '')} {profile.get('localizedLastName', '')}".strip(),
            "linkedin_id": profile.get("id"),
            "profile_url": f"https://www.linkedin.com/in/{profile.get('vanityName', '')}"
        }

    except Exception as e:
        logger.error(f"Error getting LinkedIn user info: {str(e)}")
        return None

async def handle_linkedin_auth(code: str) -> Tuple[bool, Dict[str, Any], str]:
    """Complete LinkedIn OAuth flow"""
    try:
        if not code:
            return False, {}, "Authorization code is required"

        tokens = await exchange_code_for_token(code)
        if not tokens:
            return False, {}, "Failed to exchange code for tokens"

        user_info = await get_linkedin_user_info(tokens["access_token"])
        if not user_info:
            return False, {}, "Failed to get user information"

        if "email" not in user_info:
            return False, {}, "Email not found in user info"

        return True, user_info, ""

    except Exception as e:
        logger.error(f"LinkedIn auth error: {str(e)}")
        return False, {}, f"Authentication failed: {str(e)}"
