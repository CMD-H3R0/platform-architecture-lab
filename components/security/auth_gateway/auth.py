import os
import hmac
import logging
from fastapi import Security, HTTPException, Depends
from fastapi.security import APIKeyHeader
from .models import UserContext
from dotenv import load_dotenv

load_dotenv() # Load .env file locally

logger = logging.getLogger("auth_gateway")
logger.setLevel(logging.INFO)

# --- PRODUCTION IDENTITY PROVIDER ---
# Keys are now loaded from the Environment (12-Factor App methodology)
# If env vars are missing, this defaults to None, which simply won't match incoming requests.
ADMIN_KEY = os.getenv("ADMIN_API_KEY")
WORKER_KEY = os.getenv("WORKER_API_KEY")

if not ADMIN_KEY or not WORKER_KEY:
    logger.warning("⚠️ Security Warning: API Keys not set in environment variables.")

API_IDENTITY_MAP = {
    ADMIN_KEY: {
        "user_id": "u_admin", 
        "client_id": "platform_admin", 
        "roles": ["admin", "finance_approver"],
        "tenant_id": "TENANT_01"
    },
    WORKER_KEY: {
        "user_id": "u_bot_01", 
        "client_id": "automation_worker", 
        "roles": ["worker"],
        "tenant_id": "TENANT_02"
    }
}

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_user(api_key: str = Security(api_key_header)) -> UserContext:
    if not api_key:
        raise HTTPException(status_code=403, detail="Missing Authentication Header")

    # Filter out None keys to prevent security bypass if env vars are missing
    valid_keys = {k: v for k, v in API_IDENTITY_MAP.items() if k is not None}

    for valid_key, user_data in valid_keys.items():
        if hmac.compare_digest(api_key, valid_key):
            return UserContext(**user_data)
            
    logger.warning("⛔ Auth Failure: Invalid Credentials.")
    raise HTTPException(status_code=403, detail="Invalid Credentials")

class RequireRole:
    def __init__(self, required_role: str):
        self.required_role = required_role

    def __call__(self, user: UserContext = Depends(get_current_user)):
        if "admin" in user.roles: return True
        if self.required_role not in user.roles:
            logger.warning(f"⛔ RBAC Deny: User {user.user_id} needs role '{self.required_role}'")
            raise HTTPException(status_code=403, detail="Insufficient Permissions")
        return True