import os
import uuid
import base64
from typing import Optional
from datetime import datetime
from PIL import Image
from io import BytesIO
import re
from config import settings

def generate_unique_id() -> str:
    """Generate a unique ID using UUID4"""
    return str(uuid.uuid4())

def is_valid_email(email: str) -> bool:
    """Validate email format"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

def is_strong_password(password: str) -> bool:
    """
    Check if password meets minimum requirements:
    - At least 8 characters
    - Contains uppercase letter
    - Contains lowercase letter
    - Contains a digit
    - Contains a special character
    """
    if len(password) < 8:
        return False
    
    # Check for uppercase, lowercase, digit, and special char
    has_upper = any(char.isupper() for char in password)
    has_lower = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_special = any(not char.isalnum() for char in password)
    
    return has_upper and has_lower and has_digit and has_special

def process_profile_image(base64_image: str, user_id: str) -> Optional[str]:
    """
    Process base64 image, validate, resize, and save to disk
    Returns the filename if successful, None otherwise
    """
    if not base64_image:
        return None
    
    try:
        # Extract image data from base64 string
        if "," in base64_image:
            image_data = base64_image.split(",")[1]
        else:
            image_data = base64_image
        
        # Decode base64
        image_bytes = base64.b64decode(image_data)
        
        # Check file size
        if len(image_bytes) > settings.MAX_PROFILE_IMAGE_SIZE:
            return None
        
        # Open and validate image
        image = Image.open(BytesIO(image_bytes))
        
        # Resize image (optional)
        max_size = (500, 500)
        image.thumbnail(max_size, Image.LANCZOS)
        
        # Create upload directory if it doesn't exist
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        # Save image
        filename = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        
        image.save(file_path, format="JPEG")
        
        return filename
    except Exception as e:
        print(f"Error processing image: {str(e)}")
        return None

def generate_name_avatar(name: str) -> str:
    """Generate initials for avatar from name"""
    if not name:
        return "?"
        
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    elif len(parts) == 1 and parts[0]:
        return parts[0][:2].upper()
    return "?"