import smtplib
import logging
import ssl
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from functools import partial
import asyncio

# Setup optional dependencies
try:
    import aiosmtplib
    from aiosmtplib.errors import SMTPException
    ASYNC_SMTP = True
except ImportError:
    ASYNC_SMTP = False
    SMTPException = Exception  # Fallback for retry decorator
    logging.warning("aiosmtplib not installed. Using synchronous SMTP.")

try:
    from jinja2 import Environment, PackageLoader, select_autoescape
    env = Environment(
        loader=PackageLoader('templates/email', 'mail'),
        autoescape=select_autoescape(['html', 'xml'])
    )
    TEMPLATES_ENABLED = True
except ImportError:
    logging.warning("jinja2 not installed. Using simple email templates.")
    TEMPLATES_ENABLED = False

# Import settings after checking dependencies
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

class EmailTemplate:
    """Email template constants"""
    VERIFY_EMAIL = "verify_email.html"
    WELCOME = "welcome.html" 
    PASSWORD_RESET = "password_reset.html"
    PASSWORD_RESET_SUCCESS = "password_reset_success.html"
    VERIFICATION_SUCCESS = "verification_success.html"
    SUBSCRIPTION_UPDATE = "subscription_update.html"
    PAYMENT_SUCCESS = "payment_success.html"
    PAYMENT_FAILED = "payment_failed.html"
    PAYMENT_CONFIRMATION = "payment_confirmation.html"

def get_template(template_name: str, **kwargs) -> str:
    """
    Get rendered template or fallback to basic HTML
    
    Args:
        template_name: Name of the template to render
        **kwargs: Template variables
        
    Returns:
        str: Rendered HTML template
    """
    try:
        if TEMPLATES_ENABLED:
            template = env.get_template(template_name)
            return template.render(**kwargs)
    except Exception as e:
        logger.error(f"Error loading template {template_name}: {str(e)}")
        
    # Fallback templates for common emails
    if template_name == "verify_email.html":
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Email Verification</h2>
            <p>Hello {kwargs.get('user_name', '')},</p>
            <p>Please verify your email by clicking: <a href="{kwargs.get('verification_url', '')}">Verify Email</a></p>
            <p>Thank you for joining us!</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                {kwargs.get('company_name', '')}<br>
                {kwargs.get('company_address', '')}
            </p>
        </body>
        </html>
        """
    elif template_name == "verification_success.html":
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Email Verification Successful!</h2>
            <p>Hello {kwargs.get('user_name', '')},</p>
            <p>Your email has been successfully verified. You can now access all features of your account.</p>
            <p>Click here to <a href="{kwargs.get('login_url', '')}">login to your account</a>.</p>
            <p>Thank you for joining us!</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                {kwargs.get('company_name', '')}<br>
                {kwargs.get('company_address', '')}
            </p>
        </body>
        </html>
        """
    elif template_name == "password_reset.html":
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Password Reset</h2>
            <p>Hello {kwargs.get('user_name', '')},</p>
            <p>Click here to reset your password: <a href="{kwargs.get('reset_url', '')}">Reset Password</a></p>
            <p>If you did not request this password reset, please ignore this email.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                {kwargs.get('company_name', '')}<br>
                {kwargs.get('company_address', '')}
            </p>
        </body>
        </html>
        """
    elif template_name == "password_reset_success.html":
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Password Reset Successful</h2>
            <p>Hello {kwargs.get('user_name', '')},</p>
            <p>Your password has been successfully reset.</p>
            <div style="margin: 20px 0;">
                <a href="{kwargs.get('login_url', '')}" 
                   style="background-color: #007bff; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 4px;">
                    Login to Your Account
                </a>
            </div>
            <p>If you did not request this change, please contact our support team immediately.</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                {kwargs.get('company_name', '')}<br>
                {kwargs.get('company_address', '')}
            </p>
        </body>
        </html>
        """
    elif template_name == "subscription_update.html":
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Subscription Update</h2>
            <p>Hello {kwargs.get('user_name', '')},</p>
            <p>Your subscription to {kwargs.get('plan_name', '')} has been updated.</p>
            <p>Your subscription will end on: {kwargs.get('end_date', '')}</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                {kwargs.get('company_name', '')}<br>
                {kwargs.get('company_address', '')}
            </p>
        </body>
        </html>
        """
    elif template_name == "payment_confirmation.html":
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>Payment Confirmation</h2>
            <p>Hello {kwargs.get('user_name', '')},</p>
            <p>Your payment of ${kwargs.get('amount', '0.00')} for {kwargs.get('plan_name', '')} has been processed successfully.</p>
            <p>Thank you for your business!</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                {kwargs.get('company_name', '')}<br>
                {kwargs.get('company_address', '')}
            </p>
        </body>
        </html>
        """
    else:
        # Generic fallback
        return kwargs.get('body', '')

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def send_email(to_email: str, subject: str, body: str, is_html: bool = True) -> bool:
    """
    Sends an email using either async or sync SMTP based on availability
    Includes retry mechanism and detailed logging
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        is_html: Whether the body is HTML (default True)
        
    Returns:
        bool: Success or failure
    """
    message = MIMEMultipart()
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "html" if is_html else "plain"))

    try:
        logger.info(f"Attempting to send email to {to_email} with subject: {subject}")
        
        if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            logger.error("SMTP credentials not configured!")
            return False
            
        if ASYNC_SMTP:
            success = await _send_async_email(message)
        else:
            success = await _send_sync_email(message)
            
        if success:
            logger.info(f"Successfully sent email to {to_email}")
        else:
            logger.error(f"Failed to send email to {to_email}")
        return success
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}", exc_info=True)
        raise  # Let retry mechanism handle it

async def _send_async_email(message: MIMEMultipart) -> bool:
    """Send email using aiosmtplib with detailed logging"""
    try:
        logger.info(f"Connecting to SMTP server: {settings.SMTP_SERVER}:{settings.SMTP_PORT}")
        
        async with aiosmtplib.SMTP(
            hostname=settings.SMTP_SERVER,
            port=settings.SMTP_PORT,
            use_tls=settings.EMAIL_SSL,
            timeout=settings.EMAIL_TIMEOUT
        ) as smtp:
            if settings.EMAIL_USE_TLS and not settings.EMAIL_SSL:
                logger.info("SMTP connection established, starting TLS...")
                if not smtp.is_connected:
                    await smtp.connect()
                await smtp.ehlo()
                try:
                    await smtp.starttls()  # Upgrade to TLS
                    await smtp.ehlo()
                    logger.info("TLS established, attempting login...")
                except SMTPException as e:
                    if "Connection already using TLS" in str(e):
                        logger.info("Connection already using TLS, skipping starttls")
                    else:
                        raise
            logger.info("Attempting login...")
            await smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            logger.info("SMTP login successful, sending message...")
            await smtp.send_message(message)
            logger.info("Message sent successfully via async SMTP")
        return True
    except Exception as e:
        logger.error(f"Async SMTP error: {str(e)}", exc_info=True)
        raise

async def _send_sync_email(message: MIMEMultipart) -> bool:
    """Send email using standard smtplib in a thread pool"""
    try:
        loop = asyncio.get_event_loop()
        send_func = partial(_sync_send_mail, message)
        await loop.run_in_executor(None, send_func)
        return True
    except Exception as e:
        logger.error(f"Sync SMTP error: {str(e)}", exc_info=True)
        return False

def _sync_send_mail(message: MIMEMultipart):
    """Synchronous email sending function"""
    try:
        logger.info(f"Attempting sync SMTP connection to {settings.SMTP_SERVER}:{settings.SMTP_PORT}")
        server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
        server.set_debuglevel(1)
        server.ehlo()
        
        if settings.EMAIL_USE_TLS:
            logger.info("Establishing TLS connection...")
            server.starttls()
            server.ehlo()
            
        logger.info("Attempting login...")
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        logger.info("Sending message...")
        server.send_message(message)
        server.quit()
        logger.info("Message sent successfully via sync SMTP")
        return True
    except Exception as e:
        logger.error(f"Sync SMTP error: {str(e)}", exc_info=True)
        return False

async def send_email_async(to_email: str, subject: str, template_name: str, template_data: Dict[str, Any]) -> bool:
    """
    Main email sending function that handles templates
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        template_name: Name of the template to use
        template_data: Data to render in the template
        
    Returns:
        bool: Success or failure
    """
    try:
        # Ensure standard company data is available
        template_data.update({
            "company_name": settings.COMPANY_NAME,
            "company_address": settings.COMPANY_ADDRESS,
            "logo_url": settings.LOGO_URL
        })
        
        body = get_template(template_name, **template_data)
        return await send_email(to_email, subject, body)
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}", exc_info=True)
        return False

# Specialized email sending functions

async def send_verification_email(to_email: str, user_name: str, token: str) -> bool:
    """
    Send verification email with detailed logging
    
    Args:
        to_email: Recipient email address
        user_name: Name of the user
        token: Verification token
        
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"Preparing verification email for {to_email}")
        verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        
        template_data = {
            "user_name": user_name,
            "verification_url": verification_url
        }
        
        success = await send_email_async(
            to_email,
            "Verify Your Email - Profact",
            EmailTemplate.VERIFY_EMAIL,
            template_data
        )
        
        if success:
            logger.info(f"Successfully sent verification email to {to_email}")
        else:
            logger.error(f"Failed to send verification email to {to_email}")
        return success
    except Exception as e:
        logger.error(f"Error in send_verification_email: {str(e)}", exc_info=True)
        return False

@retry(
    retry=retry_if_exception_type(SMTPException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def send_password_reset_email(to_email: str, user_name: str, reset_token: str) -> bool:
    """
    Send password reset email with retry logic for SMTP exceptions
    
    Args:
        to_email: Recipient email address
        user_name: Name of the user
        reset_token: Password reset token
        
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"Preparing password reset email for {to_email}")
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        
        template_data = {
            "user_name": user_name,
            "reset_url": reset_url
        }
        
        success = await send_email_async(
            to_email,
            "Password Reset Request - Profact",
            EmailTemplate.PASSWORD_RESET,
            template_data
        )
        
        if success:
            logger.info(f"Successfully sent password reset email to {to_email}")
        else:
            logger.error(f"Failed to send password reset email to {to_email}")
        return success
    except Exception as e:
        logger.error(f"Error in send_password_reset_email: {str(e)}", exc_info=True)
        return False

async def send_password_reset_notification(to_email: str, user_name: str) -> bool:
    """
    Sends a notification that password was successfully reset
    
    Args:
        to_email: Recipient email address
        user_name: Name of the user
        
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"Sending password reset confirmation email to {to_email}")
        
        template_data = {
            "user_name": user_name,
            "login_url": f"{settings.FRONTEND_URL}/login"
        }
        
        success = await send_email_async(
            to_email,
            "Password Reset Successful - Profact",
            EmailTemplate.PASSWORD_RESET_SUCCESS,
            template_data
        )
        
        if success:
            logger.info(f"Successfully sent password reset confirmation to {to_email}")
        else:
            logger.error(f"Failed to send password reset confirmation to {to_email}")
        return success
    except Exception as e:
        logger.error(f"Error sending password reset confirmation: {str(e)}", exc_info=True)
        return False

async def send_verification_success_email(to_email: str, user_name: str) -> bool:
    """
    Send email notification after successful email verification
    
    Args:
        to_email: Recipient email address
        user_name: Name of the user
        
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"Sending verification success email to {to_email}")
        
        template_data = {
            "user_name": user_name,
            "login_url": f"{settings.FRONTEND_URL}/login"
        }
        
        success = await send_email_async(
            to_email,
            "Email Verification Successful - Profact",
            EmailTemplate.VERIFICATION_SUCCESS,
            template_data
        )
        
        if success:
            logger.info(f"Successfully sent verification success email to {to_email}")
        else:
            logger.error(f"Failed to send verification success email to {to_email}")
        return success
    except Exception as e:
        logger.error(f"Error sending verification success email: {str(e)}", exc_info=True)
        return False

async def send_welcome_email(to_email: str, user_name: str) -> bool:
    """
    Send welcome email to new users
    
    Args:
        to_email: Recipient email address
        user_name: Name of the user
        
    Returns:
        bool: Success or failure
    """
    return await send_email_async(
        to_email,
        "Welcome to Profact!",
        EmailTemplate.WELCOME,
        {
            "user_name": user_name
        }
    )

async def send_subscription_update_email(to_email: str, user_name: str, plan_name: str, end_date: str) -> bool:
    """
    Sends an email notification about subscription updates
    
    Args:
        to_email: Recipient email address
        user_name: Name of the user
        plan_name: Name of the subscription plan
        end_date: End date of the subscription
        
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"Sending subscription update email to {to_email}")
        
        template_data = {
            "user_name": user_name,
            "plan_name": plan_name,
            "end_date": end_date
        }
        
        success = await send_email_async(
            to_email,
            "Profact - Your Subscription Update",
            EmailTemplate.SUBSCRIPTION_UPDATE,
            template_data
        )
        
        if success:
            logger.info(f"Successfully sent subscription update email to {to_email}")
        else:
            logger.error(f"Failed to send subscription update email to {to_email}")
        return success
    except Exception as e:
        logger.error(f"Error sending subscription update email: {str(e)}", exc_info=True)
        return False

async def send_payment_confirmation_email(to_email: str, user_name: str, amount: float, plan_name: str) -> bool:
    """
    Send payment confirmation email
    
    Args:
        to_email: Recipient email address
        user_name: Name of the user
        amount: Payment amount
        plan_name: Name of the subscription plan
        
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"Sending payment confirmation email to {to_email}")
        
        template_data = {
            "user_name": user_name,
            "amount": f"{amount:.2f}",
            "plan_name": plan_name
        }
        
        success = await send_email_async(
            to_email,
            "Payment Confirmation - Profact",
            EmailTemplate.PAYMENT_CONFIRMATION,
            template_data
        )
        
        if success:
            logger.info(f"Successfully sent payment confirmation email to {to_email}")
        else:
            logger.error(f"Failed to send payment confirmation email to {to_email}")
        return success
    except Exception as e:
        logger.error(f"Error sending payment confirmation email: {str(e)}", exc_info=True)
        return False

from fastapi import APIRouter, Depends, HTTPException
from services.email_service import send_verification_email
from middleware.auth import get_current_user

router = APIRouter()

# Define API endpoints that need email functionality
# Use the email_service through the services layer