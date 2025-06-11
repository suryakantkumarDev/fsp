from typing import Dict, Any, Tuple, Optional
from config import settings
import importlib

# Initialize payment clients with error handling
stripe = None
razorpay_client = None

try:
    stripe = importlib.import_module('stripe')
    stripe.api_key = settings.STRIPE_SECRET_KEY
except ImportError:
    print("Warning: stripe module not found. Stripe payments will be disabled.")

try:
    from razorpay import Client
    razorpay_client = Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except ImportError:
    print("Warning: razorpay module not found. Razorpay payments will be disabled.")

async def create_stripe_payment(amount: float, currency: str = "usd") -> Dict[str, Any]:
    if not stripe:
        raise ValueError("Stripe is not configured")
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=currency,
            payment_method_types=['card'],
            metadata={'integration_check': 'accept_a_payment'}
        )
        return {
            "client_secret": intent.client_secret,
            "payment_id": intent.id
        }
    except Exception as e:
        raise ValueError(f"Stripe payment creation failed: {str(e)}")

async def create_razorpay_order(amount: float, currency: str = "INR") -> Dict[str, Any]:
    if not razorpay_client:
        raise ValueError("Razorpay is not configured")
    try:
        order = razorpay_client.order.create({
            'amount': int(amount * 100),  # Convert to paise
            'currency': currency,
            'payment_capture': '1'
        })
        return {
            "order_id": order['id'],
            "currency": currency,
            "amount": amount
        }
    except Exception as e:
        raise ValueError(f"Razorpay order creation failed: {str(e)}")

async def verify_stripe_payment(payment_intent_id: str) -> Tuple[bool, str]:
    if not stripe:
        return False, "Stripe is not configured"
    try:
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        return intent.status == "succeeded", intent.status
    except Exception as e:
        return False, str(e)

async def verify_razorpay_payment(order_id: str, payment_id: str, signature: str) -> bool:
    if not razorpay_client:
        return False
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })
        return True
    except Exception:
        return False
