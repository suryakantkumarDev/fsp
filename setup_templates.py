import os
from pathlib import Path
import logging
import shutil

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_template_directories():
    """Ensure all required template directories exist"""
    base_dir = Path(__file__).resolve().parent
    directories = [
        'templates/email',
        'templates/email/partials'
    ]
    
    for directory in directories:
        dir_path = base_dir / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {dir_path}")

def ensure_email_templates():
    """Ensure all required email templates exist"""
    base_dir = Path(__file__).resolve().parent
    template_dir = base_dir / 'templates' / 'email'
    
    verify_email_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Email Verification</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Email Verification</h2>
      <p>Hello {{ user_name }},</p>
      <p>Please verify your email by clicking the button below:</p>
      <div class="button-container">
        <a href="{{ verification_url }}" class="button">Verify Email</a>
      </div>
      <p>If the button doesn't work, copy and paste this link:</p>
      <p class="link">{{ verification_url }}</p>
      <p>Thank you for joining us!</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    welcome_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Welcome to Our Service</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Welcome to Our Service!</h2>
      <p>Hello {{ user_name }},</p>
      <p>Thank you for creating an account with us. We're excited to have you on board!</p>
      <p>With your new account, you can:</p>
      <ul>
        <li>Access all our premium features</li>
        <li>Manage your subscriptions</li>
        <li>Update your profile information</li>
      </ul>
      <div class="button-container">
        <a href="{{ dashboard_url }}" class="button">Go to Dashboard</a>
      </div>
      <p>If you have any questions or need assistance, please don't hesitate to contact our support team.</p>
      <p>Best regards,</p>
      <p>The Team</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    password_reset_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Password Reset Request</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Password Reset Request</h2>
      <p>Hello {{ user_name }},</p>
      <p>We received a request to reset your password. If you didn't make this request, you can safely ignore this email.</p>
      <p>To reset your password, click the button below:</p>
      <div class="button-container">
        <a href="{{ reset_url }}" class="button">Reset Password</a>
      </div>
      <p>If the button doesn't work, copy and paste this link:</p>
      <p class="link">{{ reset_url }}</p>
      <p>This link will expire in 24 hours for security reasons.</p>
      <p>If you need further assistance, please contact our support team.</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    password_reset_success_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Password Reset Successful</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Password Reset Successful</h2>
      <p>Hello {{ user_name }},</p>
      <p>Your password has been successfully reset.</p>
      <p>If you did not request this change, please contact our support team immediately.</p>
      <div class="button-container">
        <a href="{{ login_url }}" class="button">Login to Account</a>
      </div>
      <p>Thank you for using our service.</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    verification_success_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Email Verification Successful</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Email Verification Successful</h2>
      <p>Hello {{ user_name }},</p>
      <p>Your email has been successfully verified. Thank you for completing this important step.</p>
      <p>You now have full access to all features of our platform.</p>
      <div class="button-container">
        <a href="{{ dashboard_url }}" class="button">Go to Dashboard</a>
      </div>
      <p>If you have any questions or need assistance, please don't hesitate to contact our support team.</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    subscription_update_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Subscription Update</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Subscription Update</h2>
      <p>Hello {{ user_name }},</p>
      <p>Your subscription has been updated successfully.</p>
      
      <div class="subscription-details">
        <h3>New Subscription Details:</h3>
        <ul>
          <li>Plan: {{ plan_name }}</li>
          <li>Price: ${{ plan_price }}</li>
          <li>Billing Cycle: {{ billing_cycle }}</li>
          <li>Effective Date: {{ effective_date }}</li>
        </ul>
      </div>

      <p>Your new subscription benefits will take effect immediately.</p>
      <div class="button-container">
        <a href="{{ subscription_url }}" class="button">View Subscription Details</a>
      </div>

      <p>If you have any questions about your subscription or need assistance, please contact our support team.</p>
      <p>Thank you for your continued support!</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    payment_confirmation_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Payment Confirmation</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Payment Confirmation</h2>
      <p>Hello {{ user_name }},</p>
      <p>We are processing your payment for the following order:</p>
      
      <div class="payment-details">
        <h3>Order Details:</h3>
        <ul>
          <li>Amount: ${{ amount }}</li>
          <li>Plan: {{ plan_name }}</li>
          <li>Date: {{ payment_date }}</li>
          <li>Transaction ID: {{ transaction_id }}</li>
        </ul>
      </div>

      <p>Your payment is being processed. We will send you a confirmation email once it's complete.</p>
      <p>If you have any questions, please don't hesitate to contact our support team.</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    payment_failed_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Payment Failed</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Payment Failed</h2>
      <p>Hello {{ user_name }},</p>
      <p>We encountered an issue processing your recent payment.</p>
      
      <div class="payment-details">
        <h3>Payment Details:</h3>
        <ul>
          <li>Amount: ${{ amount }}</li>
          <li>Plan: {{ plan_name }}</li>
          <li>Date: {{ payment_date }}</li>
          <li>Transaction ID: {{ transaction_id }}</li>
        </ul>
      </div>

      <p>Possible reasons for the failure:</p>
      <ul>
        <li>Insufficient funds</li>
        <li>Expired card</li>
        <li>Incorrect payment information</li>
        <li>Bank restrictions</li>
      </ul>

      <div class="button-container">
        <a href="{{ payment_url }}" class="button">Update Payment Method</a>
      </div>

      <p>If you need assistance, please contact our support team.</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    payment_success_content = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Payment Successful</title>
    {% include "email/partials/styles.html" %}
  </head>
  <body>
    {% include "email/partials/header.html" %}
    <div class="container">
      <h2>Payment Successful!</h2>
      <p>Hello {{ user_name }},</p>
      <p>Your payment has been processed successfully.</p>
      
      <div class="payment-details">
        <h3>Payment Details:</h3>
        <ul>
          <li>Amount: ${{ amount }}</li>
          <li>Plan: {{ plan_name }}</li>
          <li>Date: {{ payment_date }}</li>
          <li>Transaction ID: {{ transaction_id }}</li>
        </ul>
      </div>

      <p>Your subscription has been activated and you now have full access to all features.</p>
      <div class="button-container">
        <a href="{{ dashboard_url }}" class="button">Go to Dashboard</a>
      </div>

      <p>If you have any questions, please don't hesitate to contact our support team.</p>
      <p>Thank you for choosing us!</p>
    </div>
    {% include "email/partials/footer.html" %}
  </body>
</html>
    """
    
    required_templates = {
        'verify_email.html': ('Email verification template', verify_email_content),
        'welcome.html': ('Welcome email template', welcome_content),
        'password_reset.html': ('Password reset template', password_reset_content),
        'password_reset_success.html': ('Password reset success template', password_reset_success_content),
        'verification_success.html': ('Email verification success template', verification_success_content),
        'subscription_update.html': ('Subscription update template', subscription_update_content),
        'payment_confirmation.html': ('Payment confirmation template', payment_confirmation_content),
        'payment_failed.html': ('Payment failed template', payment_failed_content),
        'payment_success.html': ('Payment success template', payment_success_content)
    }
    
    for template, (description, content) in required_templates.items():
        template_path = template_dir / template
        if not template_path.exists():
            logger.info(f"Creating {description}: {template}")
            template_path.write_text(content)
        else:
            logger.info(f"Template already exists: {template}")

def ensure_partial_templates():
    """Ensure all partial templates exist"""
    base_dir = Path(__file__).resolve().parent
    partials_dir = base_dir / 'templates/email/partials'
    
    header_content = """
<div class="header">
  <div class="logo">
    <img src="{{ logo_url|default('https://via.placeholder.com/200x50?text=Your+Logo') }}" alt="Company Logo">
  </div>
</div>
    """
    
    footer_content = """
<div class="footer">
  <p>&copy; {{ current_year }} {{ company_name|default('Your Company') }}. All rights reserved.</p>
  <p>
    <a href="{{ privacy_url|default('#') }}">Privacy Policy</a> | 
    <a href="{{ terms_url|default('#') }}">Terms of Service</a> | 
    <a href="{{ unsubscribe_url|default('#') }}">Unsubscribe</a>
  </p>
  <p class="address">{{ company_address|default('123 Main Street, City, State, ZIP') }}</p>
</div>
    """
    
    styles_content = """
<style>
  body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    color: #333333;
    margin: 0;
    padding: 0;
    background-color: #f4f4f4;
  }
  .container {
    max-width: 600px;
    margin: 0 auto;
    padding: 20px;
    background-color: #ffffff;
  }
  .header {
    text-align: center;
    padding: 20px 0;
    background-color: #f8f8f8;
  }
  .logo img {
    max-width: 200px;
    height: auto;
  }
  h2 {
    color: #2c3e50;
    margin-top: 0;
  }
  h3 {
    color: #3498db;
  }
  .button-container {
    margin: 25px 0;
    text-align: center;
  }
  .button {
    display: inline-block;
    padding: 10px 20px;
    background-color: #3498db;
    color: #ffffff !important;
    text-decoration: none;
    border-radius: 4px;
    font-weight: bold;
  }
  .button:hover {
    background-color: #2980b9;
  }
  .link {
    word-break: break-all;
    color: #3498db;
  }
  .footer {
    text-align: center;
    margin-top: 30px;
    padding: 20px 0;
    font-size: 12px;
    color: #777777;
    border-top: 1px solid #eeeeee;
  }
  .footer a {
    color: #3498db;
    text-decoration: none;
  }
  .footer a:hover {
    text-decoration: underline;
  }
  .address {
    margin-top: 10px;
    font-style: italic;
  }
  .payment-details, .subscription-details {
    background-color: #f9f9f9;
    padding: 15px;
    border-radius: 4px;
    margin: 20px 0;
  }
  ul {
    padding-left: 20px;
  }
</style>
    """
    
    required_partials = {
        'header.html': ('Email header partial', header_content),
        'footer.html': ('Email footer partial', footer_content),
        'styles.html': ('Email styles partial', styles_content)
    }
    
    for partial, (description, content) in required_partials.items():
        partial_path = partials_dir / partial
        if not partial_path.exists():
            logger.info(f"Creating {description}: {partial}")
            partial_path.write_text(content)
        else:
            logger.info(f"Partial already exists: {partial}")

def main():
    """Main function to initialize email templates"""
    logging.info("Starting email template initialization")
    ensure_template_directories()
    ensure_partial_templates()
    ensure_email_templates()
    logging.info("Email template initialization complete")

if __name__ == "__main__":
    main()
    