from utils.email import (
    send_email,
    send_email_async,
    send_verification_email,
    send_password_reset_email,
    send_password_reset_notification,
    send_verification_success_email,
    send_welcome_email,
    send_subscription_update_email,
    send_payment_confirmation_email,
    get_template
)
import logging

logger = logging.getLogger(__name__)

# Re-export all email functions
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