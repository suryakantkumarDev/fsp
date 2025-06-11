from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.core.exceptions import ResourceNotFoundError
import base64
from io import BytesIO
from PIL import Image
from config import settings
from typing import Optional
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class AzureStorage:
    def __init__(self):
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        self.container_name = settings.AZURE_STORAGE_CONTAINER
        if not self.connection_string:
            logger.warning("Azure Storage connection string not configured")
            self.client = None
            self.container_client = None
        else:
            try:
                self.client = BlobServiceClient.from_connection_string(self.connection_string)
                # Create container if it doesn't exist
                try:
                    self.container_client = self.client.get_container_client(self.container_name)
                    if not self.container_client.exists():
                        logger.info(f"Creating container: {self.container_name}")
                        self.container_client = self.client.create_container(
                            self.container_name,
                            public_access='blob'  # Makes blobs publicly accessible
                        )
                    logger.info(f"Successfully connected to container: {self.container_name}")
                except Exception as e:
                    logger.error(f"Error with container: {str(e)}")
                    self.container_client = None
            except Exception as e:
                logger.error(f"Error initializing Azure Storage: {str(e)}")
                self.client = None
                self.container_client = None

    def ensure_container_exists(self) -> bool:
        """Remove async since BlobServiceClient methods are synchronous"""
        try:
            if not self.client:
                logger.error("Azure Storage client not initialized")
                return False

            if not self.container_client or not self.container_client.exists():
                logger.info(f"Creating container: {self.container_name}")
                self.container_client = self.client.create_container(
                    self.container_name,
                    public_access='blob'
                )
            return True
        except Exception as e:
            logger.error(f"Error ensuring container exists: {str(e)}")
            return False

    async def upload_image(self, base64_image: str, user_id: str) -> Optional[str]:
        """Upload image to Azure Blob Storage"""
        try:
            if not self.container_client:
                logger.error("Azure Storage not configured")
                return None

            if not base64_image:
                logger.error("Empty image data")
                return None

            try:
                # Extract image data and type
                if ',' in base64_image:
                    header, base64_data = base64_image.split(',', 1)
                    is_svg = 'svg+xml' in header.lower()
                else:
                    base64_data = base64_image
                    is_svg = False

                # Handle SVG files differently
                if is_svg:
                    try:
                        image_bytes = base64.b64decode(base64_data)
                        # Generate unique blob name for SVG
                        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        unique_id = str(uuid.uuid4())[:8]
                        blob_name = f"profile-images/{user_id}/{timestamp}_{unique_id}.svg"
                        
                        blob_client = self.container_client.get_blob_client(blob_name)
                        content_settings = ContentSettings(
                            content_type='image/svg+xml',
                            cache_control='public, max-age=31536000'
                        )
                        
                        # Upload SVG directly
                        blob_client.upload_blob(
                            image_bytes,
                            overwrite=True,
                            content_settings=content_settings
                        )
                        
                        image_url = f"{settings.AZURE_STORAGE_URL}/{self.container_name}/{blob_name}"
                        logger.info(f"Successfully uploaded SVG image: {blob_name}")
                        return image_url
                    except Exception as e:
                        logger.error(f"Error processing SVG: {str(e)}")
                        return None

                # For non-SVG images, continue with existing processing
                try:
                    image_data = base64.b64decode(base64_data)
                except Exception as e:
                    logger.error(f"Invalid base64 data: {str(e)}")
                    return None

                # Open and validate image
                try:
                    image = Image.open(BytesIO(image_data))
                    
                    # Convert all images to RGB if needed
                    if image.mode in ['RGBA', 'P']:
                        background = Image.new('RGB', image.size, (255, 255, 255))
                        if image.mode == 'RGBA':
                            background.paste(image, mask=image.split()[3])
                        else:
                            background.paste(image)
                        image = background
                    elif image.mode != 'RGB':
                        image = image.convert('RGB')

                except Exception as e:
                    logger.error(f"Invalid image data: {str(e)}")
                    return None

                # Resize image maintaining aspect ratio
                max_size = (800, 800)
                image.thumbnail(max_size, Image.LANCZOS)

                # Optimize and save image
                output = BytesIO()
                image.save(output, format='JPEG', quality=85, optimize=True)
                image_bytes = output.getvalue()

                # Generate unique blob name
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                unique_id = str(uuid.uuid4())[:8]
                blob_name = f"profile-images/{user_id}/{timestamp}_{unique_id}.jpg"
                
                blob_client = self.container_client.get_blob_client(blob_name)

                # Set content settings
                content_settings = ContentSettings(
                    content_type='image/jpeg',
                    cache_control='public, max-age=31536000'
                )

                # Upload to Azure
                blob_client.upload_blob(
                    image_bytes,
                    overwrite=True,
                    content_settings=content_settings
                )

                image_url = f"{settings.AZURE_STORAGE_URL}/{self.container_name}/{blob_name}"
                logger.info(f"Successfully uploaded image: {blob_name}")
                return image_url

            except Exception as e:
                logger.error(f"Error processing image: {str(e)}", exc_info=True)
                return None

        except Exception as e:
            logger.error(f"Error uploading to Azure: {str(e)}", exc_info=True)
            return None

    async def delete_image(self, image_url: str) -> bool:
        """Delete image from Azure Blob Storage"""
        try:
            if not self.container_client:
                return False
                
            # Extract blob name from URL
            blob_name = image_url.split(f"{self.container_name}/")[-1]
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Check if blob exists and delete (removed await)
            if blob_client.exists():
                blob_client.delete_blob()
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error deleting image: {str(e)}")
            return False

# Create singleton instance
azure_storage = AzureStorage()
