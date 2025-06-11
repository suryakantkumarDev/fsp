import stripe
import razorpay
from config import settings
from enum import Enum
from typing import Dict, Any, Optional

class PaymentProvider(str, Enum):
    STRIPE = "stripe"
    RAZORPAY = "razorpay"
    UPI = "upi"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"

# Initialize payment clients
stripe.api_key = settings.STRIPE_SECRET_KEY
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)

class PaymentService:
    @staticmethod
    async def create_payment(
        amount: float,
        currency: str,
        provider: PaymentProvider,
        metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        try:
            if provider == PaymentProvider.STRIPE:
                payment = await PaymentService._create_stripe_payment(
                    amount, currency, metadata
                )
            elif provider == PaymentProvider.RAZORPAY:
                payment = await PaymentService._create_razorpay_payment(
                    amount, currency, metadata
                )
            else:
                return None
            
            return {
                "provider": provider,
                "payment_id": payment["id"],
                "client_secret": payment.get("client_secret"),
                "amount": amount,
                "currency": currency
            }
        except Exception as e:
            print(f"Payment creation error: {str(e)}")
            return None

    @staticmethod
    async def _create_stripe_payment(amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        return await stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Convert to cents
            currency=currency.lower(),
            metadata=metadata,
            payment_method_types=['card']
        )

    @staticmethod
    async def _create_razorpay_payment(amount: float, currency: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        return razorpay_client.order.create({
            'amount': int(amount * 100),
            'currency': currency.upper(),
            'notes': metadata
        })

payment_service = PaymentService()
