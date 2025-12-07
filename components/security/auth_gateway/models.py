from pydantic import BaseModel
from typing import List, Optional

class UserContext(BaseModel):
    user_id: str
    client_id: str
    roles: List[str] = []
    tenant_id: Optional[str] = None
