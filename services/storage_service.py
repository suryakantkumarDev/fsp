from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
import uuid
from typing import Optional
import base64
from io import BytesIO
from PIL import Image
from config import settings

blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
container_client = blob_service_client.get_container_client(settings.AZURE_STORAGE_CONTAINER)

async def upload_profile_image(base64_image: str, user_id: str) -> Optional[str]:
    try:
        # Extract image data
        image_data = base64_image.split(",")[1] if "," in base64_image else base64_image
        image_bytes = base64.b64decode(image_data)
        
        # Process image
        image = Image.open(BytesIO(image_bytes))
        
        # Resize image
        max_size = (500, 500)
        image.thumbnail(max_size, Image.LANCZOS)
        
        # Convert to bytes
        output = BytesIO()
        image.save(output, format="JPEG")
        image_bytes = output.getvalue()
        
        # Generate unique blob name
        blob_name = f"profile-images/{user_id}/{uuid.uuid4()}.jpg"
        
        # Upload to Azure
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(image_bytes, overwrite=True)
        
        # Return the URL
        return f"{settings.AZURE_STORAGE_URL}/{settings.AZURE_STORAGE_CONTAINER}/{blob_name}"
        
    except Exception as e:
        print(f"Error uploading image: {str(e)}")
        return None

async def delete_profile_image(image_url: str) -> bool:
    try:
        # Extract blob name from URL
        blob_name = image_url.split(f"{settings.AZURE_STORAGE_CONTAINER}/")[-1]
        
        # Delete blob
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.delete_blob()
        
        return True
    except Exception:
        return False
