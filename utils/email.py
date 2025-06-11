import smtplib
import logging
import ssl
import os
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import EmailMessage
from typing import Dict, Any, Optional
from functools import partial
import asyncio
from pathlib import Path

# Import settings first
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Setup optional dependencies
try:
    import aiosmtplib
    from aiosmtplib.errors import SMTPException
    ASYNC_SMTP = True
except ImportError:
    ASYNC_SMTP = False
    SMTPException = Exception
    logger.warning("aiosmtplib not installed. Using synchronous SMTP.")

# Update the template directory setup
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    base_dir = Path(__file__).resolve().parent.parent
    template_dir = base_dir / 'templates'
    if not template_dir.exists():
        template_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(['html'])
    )
    TEMPLATES_ENABLED = True
    logger.info(f"Jinja2 templates initialized with directory: {template_dir}")
except Exception as e:
    logger.error(f"Failed to initialize Jinja2: {e}")
    TEMPLATES_ENABLED = False

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

class EmailService:
    """Email service for handling all email operations"""
    
    def __init__(self):
        """Initialize email service with logger and settings"""
        # Initialize logger first to ensure it's available for other methods
        self.logger = logging.getLogger(__name__)
        self.templates_enabled = False
        self.smtp_async = False
        
        try:
            self._setup_jinja()
            self._setup_smtp()
            self.logger.info("Email service initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing email service: {e}")

    def _setup_jinja(self):
        """Initialize Jinja2 template engine"""
        try:
            # Get the base directory (Backend folder)
            base_dir = Path(__file__).resolve().parent.parent
            # Point directly to the email templates directory
            template_dir = base_dir / 'templates'
            
            if not template_dir.exists():
                template_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created template directory: {template_dir}")

            self.env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(['html'])
            )
            self.templates_enabled = True
            self.logger.info(f"Jinja2 templates initialized with directory: {template_dir}")
            # Log all available templates for debugging
            templates = self.env.list_templates()
            self.logger.info(f"Available templates: {templates}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Jinja2: {e}")
            self.templates_enabled = False
            raise

    def _setup_smtp(self):
        """Initialize SMTP settings"""
        try:
            import aiosmtplib
            self.smtp_async = True
            self.logger.info("Async SMTP enabled")
        except ImportError:
            self.smtp_async = False
            self.logger.warning("aiosmtplib not installed. Using synchronous SMTP.")

    async def send_email_async(self, to_email: str, subject: str, template_name: str, template_data: Dict[str, Any]) -> bool:
        """Main email sending function that handles templates"""
        try:
            self.logger.info(f"Preparing to send email to {to_email} using template {template_name}")
            
            template_data.update({
                "company_name": settings.COMPANY_NAME,
                "company_address": settings.COMPANY_ADDRESS,
                "logo_url": settings.LOGO_URL,
                "frontend_url": settings.FRONTEND_URL
            })
            
            body = self._render_template(template_name, template_data)
            if not body:
                self.logger.error("Failed to render email template")
                return False
                
            self.logger.info("Template rendered successfully, attempting to send email")
            return await self._send(to_email, subject, body)
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}", exc_info=True)
            return False

    def _render_template(self, template_name: str, data: dict) -> str:
        """Render email template"""
        try:
            # Add email/ prefix to look in the correct subdirectory
            template_path = f"email/{template_name}"
            self.logger.info(f"Attempting to load template: {template_path}")
            template = self.env.get_template(template_path)
            return template.render(**data)
        except Exception as e:
            self.logger.error(f"Template rendering error for {template_name}: {e}")
            # Use fallback template
            return self._get_fallback_template(template_name, data)

    def get_template(self, template_name: str, **kwargs) -> str:
        """Render email template with fallback"""
        try:
            if self.templates_enabled:
                # Add email/ prefix to look in the correct subdirectory
                template_path = f"email/{template_name}"
                template = self.env.get_template(template_path)
                return template.render(**kwargs)
        except Exception as e:
            self.logger.error(f"Template rendering error: {e}")
            return self._get_fallback_template(template_name, kwargs)

    def _get_fallback_template(self, template_name: str, data: dict) -> str:
        """Get fallback template when Jinja2 fails"""
        # Basic fallback template with common structure
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>{data.get('subject', 'Notification')}</h2>
            <p>Hello {data.get('user_name', '')},</p>
            <p>{data.get('body', '')}</p>
            <hr>
            <p style="color: #666; font-size: 12px;">
                {data.get('company_name', '')}<br>
                {data.get('company_address', '')}
            </p>
        </body>
        </html>
        """

    @retry(stop=stop_after_attempt(3), wait=wait_exponential())
    async def _send(self, to_email: str, subject: str, body: str) -> bool:
        """Send email with retry logic"""
        message = self._create_message(to_email, subject, body)
        
        if self.smtp_async:
            return await self._send_async(message)
        return await self._send_sync(message)

    async def send_verification_email(self, to_email: str, user_name: str, token: str) -> bool:
        """Send email verification"""
        return await self.send_email_async(
            to_email=to_email,
            subject="Verify Your Email",
            template_name="verify_email.html",
            template_data={
                "user_name": user_name,
                "verification_url": f"{settings.FRONTEND_URL}/verify-email?token={token}"
            }
        )

    async def send_password_reset(self, to_email: str, user_name: str, token: str) -> bool:
        """Send password reset email"""
        return await self.send_email_async(
            to_email=to_email,
            subject="Password Reset Request",
            template_name="password_reset.html",
            template_data={
                "user_name": user_name,
                "reset_url": f"{settings.FRONTEND_URL}/reset-password?token={token}"
            }
        )

    async def send_password_reset_notification(self, to_email: str, user_name: str) -> bool:
        """Send notification for successful password reset"""
        return await self.send_email_async(
            to_email=to_email,
            subject="Password Reset Successful",
            template_name=EmailTemplate.PASSWORD_RESET_SUCCESS,
            template_data={
                "user_name": user_name,
                "login_url": f"{settings.FRONTEND_URL}/login"
            }
        )

    async def send_verification_success_email(self, to_email: str, user_name: str) -> bool:
        """Send email for successful verification"""
        return await self.send_email_async(
            to_email=to_email,
            subject="Email Verification Successful",
            template_name=EmailTemplate.VERIFICATION_SUCCESS,
            template_data={
                "user_name": user_name,
                "login_url": f"{settings.FRONTEND_URL}/login"
            }
        )

    async def send_welcome_email(self, to_email: str, user_name: str) -> bool:
        """Send welcome email to new users"""
        return await self.send_email_async(
            to_email=to_email,
            subject="Welcome to Profact",
            template_name=EmailTemplate.WELCOME,
            template_data={
                "user_name": user_name,
                "login_url": f"{settings.FRONTEND_URL}/login",
                "docs_url": f"{settings.FRONTEND_URL}/docs",
                "support_url": f"{settings.FRONTEND_URL}/support",
                "blog_url": f"{settings.FRONTEND_URL}/blog"
            }
        )

    async def send_subscription_update_email(self, to_email: str, user_name: str, plan_name: str, end_date: str) -> bool:
        """Send subscription update notification"""
        return await self.send_email_async(
            to_email=to_email,
            subject="Your Subscription Has Been Updated",
            template_name=EmailTemplate.SUBSCRIPTION_UPDATE,
            template_data={
                "user_name": user_name,
                "plan_name": plan_name,
                "end_date": end_date
            }
        )

    async def send_payment_confirmation_email(self, to_email: str, user_name: str, amount: float, plan_name: str) -> bool:
        """Send payment confirmation"""
        return await self.send_email_async(
            to_email=to_email,
            subject="Payment Confirmation",
            template_name=EmailTemplate.PAYMENT_CONFIRMATION,
            template_data={
                "user_name": user_name,
                "amount": f"{amount:.2f}",
                "plan_name": plan_name
            }
        )

    # Private helper methods
    def _create_message(self, to_email: str, subject: str, body: str) -> MIMEMultipart:
        """Create email message"""
        message = MIMEMultipart()
        message["From"] = settings.EMAIL_FROM
        message["To"] = to_email
        message["Subject"] = subject
        message.attach(MIMEText(body, "html"))
        return message

    async def _send_async(self, message: MIMEMultipart) -> bool:
        """Send email using aiosmtplib"""
        smtp = None
        try:
            self.logger.info(f"Connecting to SMTP server: {settings.SMTP_SERVER}:{settings.SMTP_PORT}")
            
            if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
                self.logger.error("SMTP credentials not configured!")
                return False

            smtp = aiosmtplib.SMTP(
                hostname=settings.SMTP_SERVER,
                port=settings.SMTP_PORT,
                timeout=30,
                use_tls=False
            )

            self.logger.info("Establishing connection...")
            await smtp.connect()
            await smtp.ehlo()

            if settings.EMAIL_USE_TLS:
                try:
                    self.logger.info("Starting TLS...")
                    await smtp.starttls()
                    await smtp.ehlo()
                except SMTPException as e:
                    if "Connection already using TLS" in str(e):
                        self.logger.info("Connection already in TLS mode, proceeding with login")
                    else:
                        raise
            
            self.logger.info("Logging in...")
            await smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            
            self.logger.info("Sending message...")
            await smtp.send_message(message)
            
            self.logger.info("Message sent successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send email via SMTP: {str(e)}", exc_info=True)
            return False
            
        finally:
            if smtp is not None:
                try:
                    self.logger.info("Closing SMTP connection...")
                    await smtp.quit()
                except Exception as e:
                    self.logger.error(f"Error closing SMTP connection: {str(e)}")

    async def _send_sync(self, message: MIMEMultipart) -> bool:
        """Send email using synchronous SMTP"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._sync_send, message)
        except Exception as e:
            logger.error(f"Sync SMTP error: {e}")
            return False

    def _sync_send(self, message: MIMEMultipart) -> bool:
        """Synchronous SMTP send"""
        server = None
        try:
            self.logger.info(f"Establishing sync SMTP connection to {settings.SMTP_SERVER}:{settings.SMTP_PORT}")
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT, timeout=30)
            
            if settings.DEBUG:
                server.set_debuglevel(1)

            try:
                self.logger.info("Starting TLS...")
                server.starttls()
                server.ehlo()
                
                self.logger.info("Logging in...")
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                
                self.logger.info("Sending message...")
                server.send_message(message)
                
                self.logger.info("Message sent successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"SMTP operation failed: {str(e)}")
                raise
                
        except Exception as e:
            self.logger.error(f"SMTP error: {e}")
            return False
            
        finally:
            if server is not None:
                try:
                    self.logger.info("Closing SMTP connection...")
                    server.quit()
                except Exception as e:
                    self.logger.error(f"Error closing SMTP connection: {str(e)}")

# Create singleton instance
email_service = EmailService()

# Fix exports by properly exposing send_email function
async def send_email(to_email: str, subject: str, body: str, is_html: bool = True) -> bool:
    """Wrapper for email_service._send to maintain backwards compatibility"""
    message = email_service._create_message(to_email, subject, body)
    return await email_service._send(to_email, subject, body)

# Update exports list
__all__ = [
    'send_email',
    'send_email_async',
    'send_verification_email', 
    'send_password_reset_email',
    'send_password_reset_notification',
    'send_verification_success_email',
    'send_welcome_email',
    'send_subscription_update_email',
    'send_payment_confirmation_email',
    'get_template'
]

# Export functions from the singleton instance
send_email_async = email_service.send_email_async
send_verification_email = email_service.send_verification_email
send_password_reset_email = email_service.send_password_reset
send_password_reset_notification = email_service.send_password_reset_notification
send_verification_success_email = email_service.send_verification_success_email
send_welcome_email = email_service.send_welcome_email
send_subscription_update_email = email_service.send_subscription_update_email
send_payment_confirmation_email = email_service.send_payment_confirmation_email
get_template = email_service.get_template