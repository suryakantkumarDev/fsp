import motor.motor_asyncio
from config import settings

# Create a MongoDB client
client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL)

# Get database instance directly
db = client[settings.DB_NAME]

# Define collections directly
users = db.users
verification_tokens = db.verification_tokens
blacklisted_tokens = db.blacklisted_tokens
subscriptions = db.subscriptions
payments = db.payments
plans = db.plans
features = db.features

# Function to get database instance
async def get_database():
    return db

# Initialize database function
async def init_db():
    """Initialize database indexes and collections"""
    try:
        # User indexes
        await users.create_index("email", unique=True)
        await users.create_index("username", unique=True)
        await users.create_index([
            ("social_accounts.provider", 1),
            ("social_accounts.provider_user_id", 1)
        ])

        # Subscription indexes
        await subscriptions.create_index("user_id")
        await subscriptions.create_index("status")

        # Payment indexes
        await payments.create_index("user_id")
        await payments.create_index("status")

        # Blacklisted tokens index with TTL
        await blacklisted_tokens.create_index(
            "created_at", 
            expireAfterSeconds=86400
        )
        await blacklisted_tokens.create_index("token", unique=True)

        # Verification tokens index with TTL
        await verification_tokens.create_index(
            "created_at", 
            expireAfterSeconds=86400
        )

        # Seed default data
        await seed_default_data()

        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        raise e

async def seed_default_data():
    # Default features
    default_features = [
        {"text": "24/7 Support"},
        {"text": "Unlimited Storage"},
        {"text": "Custom Domain"},
        {"text": "Analytics Dashboard"},
        {"text": "API Access"},
        {"text": "Team Collaboration"},
        {"text": "Priority Support"},
        {"text": "Advanced Security"}
    ]
    
    # Insert features if not exist
    feature_ids = []
    for feature in default_features:
        result = await features.update_one(
            {"text": feature["text"]},
            {"$setOnInsert": feature},
            upsert=True
        )
        if result.upserted_id:
            feature_ids.append(result.upserted_id)
        else:
            f = await features.find_one({"text": feature["text"]})
            feature_ids.append(f["_id"])

    # First, delete all existing plans
    await plans.delete_many({})

    # New default plans with clear billing periods and discounts
    default_plans = [
        # Free Plan
        {
            "title": "Free Starter",
            "description": "Basic features for individuals",
            "price": 0.00,
            "original_price": 0.00,
            "discount_percentage": 0,
            "features": feature_ids[:2],
            "billing_period": "free"
        },
        # Monthly Plans
        {
            "title": "Pro Monthly",
            "description": "Professional features for growing teams",
            "price": 29.99,
            "original_price": 29.99,
            "discount_percentage": 0,
            "features": feature_ids[:4],
            "billing_period": "monthly"
        },
        {
            "title": "Business Monthly",
            "description": "Advanced features for businesses",
            "price": 59.99,
            "original_price": 59.99,
            "discount_percentage": 0,
            "features": feature_ids[:6],
            "billing_period": "monthly"
        },
        # Yearly Plans (with ~20% discount)
        {
            "title": "Pro Yearly",
            "description": "Professional features with yearly savings",
            "original_price": 359.88,  # 29.99 * 12
            "price": 287.90,
            "discount_percentage": 20,
            "features": feature_ids[:4],
            "billing_period": "yearly"
        },
        {
            "title": "Business Yearly",
            "description": "Advanced features with yearly savings",
            "original_price": 719.88,  # 59.99 * 12
            "price": 575.90,
            "discount_percentage": 20,
            "features": feature_ids[:6],
            "billing_period": "yearly"
        },
        {
            "title": "Enterprise Yearly",
            "description": "Complete solution for large organizations",
            "original_price": 1199.88,
            "price": 959.90,
            "discount_percentage": 20,
            "features": feature_ids,
            "billing_period": "yearly"
        }
    ]

    # Insert new plans
    for plan in default_plans:
        await plans.insert_one(plan)
