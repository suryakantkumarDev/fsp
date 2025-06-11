import asyncio
import sys
sys.path.append("..")

from config import settings
from utils.email import send_email
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_email_configuration():
    """Test email configuration by sending a test email"""
    logger.info("Testing email configuration...")
    
    if not settings.verify_email_settings():
        logger.error("Email settings are not properly configured!")
        logger.error("Please check your .env file for the following settings:")
        logger.error("SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM")
        return False
    
    test_email = settings.EMAIL_FROM  # Send to self for testing
    subject = "Test Email Configuration"
    body = """
    <html>
    <body>
        <h2>Email Configuration Test</h2>
        <p>This is a test email to verify your email configuration is working correctly.</p>
    </body>
    </html>
    """
    
    try:
        success = await send_email(test_email, subject, body)
        if success:
            logger.info("Test email sent successfully!")
            logger.info(f"Please check {test_email} for the test message.")
        else:
            logger.error("Failed to send test email!")
        return success
    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    asyncio.run(test_email_configuration())
