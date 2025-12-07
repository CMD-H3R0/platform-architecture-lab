from fastapi import FastAPI, UploadFile, File, Depends
from pydantic import BaseModel
import httpx
import os
import logging
from dotenv import load_dotenv
from components.security.auth_gateway.auth import get_current_user, RequireRole, UserContext
from implementations.receipt_processor.compliance import check_business_rules

load_dotenv() # Load .env

app = FastAPI(title="Receipt Processing Worker")
logger = logging.getLogger("receipt_worker")
logger.setLevel(logging.INFO)

# Service Discovery & Auth
REFLECTION_URL = os.getenv("REFLECTION_URL", "http://localhost:8001/reflect")
# The worker needs the ADMIN key to talk to the Reflection Engine
INTERNAL_AUTH_TOKEN = os.getenv("ADMIN_API_KEY") 

class ProcessResponse(BaseModel):
    merchant: str
    amount: float
    status: str
    meta: dict

@app.post("/process", dependencies=[Depends(RequireRole("worker"))])
async def process_document(
    file: UploadFile = File(...),
    user: UserContext = Depends(get_current_user)
):
    logger.info(f"Processing for Tenant: {user.tenant_id}")

    # 1. Mock Extraction (Simulating Future Date Error)
    data = {"merchant": "Costco", "amount": 150.00, "date": "2026-01-01", "confidence": 0.75}

    # 2. Agentic Handoff (Self-Correction)
    if data["confidence"] < 0.85:
        logger.warning("⚠️ Low Confidence. Requesting AI Reflection...")
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    REFLECTION_URL,
                    json={
                        "data_payload": data,
                        "validation_rules": "Date must be past. Amount positive."
                    },
                    # Uses the Env Var, not a hardcoded string
                    headers={"X-API-Key": INTERNAL_AUTH_TOKEN}
                )
                if resp.status_code == 200:
                    result = resp.json()
                    if result["was_modified"]:
                        data.update(result["refined_data"])
                        logger.info(f"✨ AI Fixed Data: {result['notes']}")
        except Exception as e:
            logger.error(f"Reflection Service Failed: {e}")

    # 3. Compliance Logic
    compliance = check_business_rules(data["amount"], data["merchant"])

    return {
        "merchant": data["merchant"], 
        "amount": data["amount"], 
        "status": compliance["status"],
        "meta": {"processed_by": user.user_id, "role": "worker"}
    }