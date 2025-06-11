from fastapi import APIRouter, Request, HTTPException
from services.subscription_service import process_payment_webhook
from config import settings
import hmac
import hashlib

try:
    import stripe
    STRIPE_ENABLED = True
except ImportError:
    STRIPE_ENABLED = False
    print("Warning: stripe module not found. Stripe webhooks will be disabled.")

router = APIRouter()

def verify_stripe_signature(payload: bytes, sig_header: str) -> bool:
    if not STRIPE_ENABLED:
        return False
    try:
        stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        return True
    except Exception:
        return False

@router.post("/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_ENABLED:
        raise HTTPException(status_code=501, detail="Stripe payments not configured")
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    if not verify_stripe_signature(payload, sig_header):
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_data = await request.json()
    if event_data["type"] == "payment_intent.succeeded":
        success, status = await process_payment_webhook(
            payment_method="stripe",
            payment_data=event_data["data"]["object"]
        )
        if not success:
            raise HTTPException(status_code=400, detail=status)
    
    return {"status": "processed"}

@router.post("/razorpay")
async def razorpay_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    
    # Verify Razorpay signature
    expected_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if signature != expected_signature:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_data = await request.json()
    if event_data["event"] == "payment.captured":
        success, status = await process_payment_webhook(
            payment_method="razorpay",
            payment_data=event_data["payload"]["payment"]
        )
        if not success:
            raise HTTPException(status_code=400, detail=status)
    
    return {"status": "processed"}
