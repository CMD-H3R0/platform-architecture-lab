import os
import hmac
import logging
from fastapi import Security, HTTPException, Depends
from fastapi.security import APIKeyHeader
from .models import UserContext

logger = logging.getLogger('auth_gateway')
logger.setLevel(logging.INFO)

API_IDENTITY_MAP = {
    'sk_admin_master': {'user_id': 'u_admin', 'client_id': 'platform_admin', 'roles': ['admin'], 'tenant_id': 'TENANT_01'},
    'sk_worker_bot': {'user_id': 'u_bot_01', 'client_id': 'automation_worker', 'roles': ['worker'], 'tenant_id': 'TENANT_02'}
}

api_key_header = APIKeyHeader(name='X-API-Key', auto_error=False)

async def get_current_user(api_key: str = Security(api_key_header)) -> UserContext:
    if not api_key: raise HTTPException(status_code=403, detail='Missing Authentication Header')
    for valid_key, user_data in API_IDENTITY_MAP.items():
        if hmac.compare_digest(api_key, valid_key): return UserContext(**user_data)
    raise HTTPException(status_code=403, detail='Invalid Credentials')

class RequireRole:
    def __init__(self, required_role: str): self.required_role = required_role
    def __call__(self, user: UserContext = Depends(get_current_user)):
        if 'admin' in user.roles: return True
        if self.required_role not in user.roles: raise HTTPException(status_code=403, detail='Insufficient Permissions')
        return True
