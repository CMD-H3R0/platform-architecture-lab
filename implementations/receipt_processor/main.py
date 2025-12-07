import os
import json
import base64
import logging
import httpx 
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Any

# === PLATFORM IMPORTS (Shared Security Logic) ===
# This imports from your 'components' package we installed via pip install -e .
from components.security.auth_gateway.auth import get_current_user, RequireRole, UserContext
from .compliance import check_business_rules

load_dotenv()

app = FastAPI(title="Receipt Processor Worker 🧾")
logger = logging.getLogger("receipt_worker")
logger.setLevel(logging.INFO)

# === CONFIGURATION & SERVICE DISCOVERY ===
# The URL of the Brain (Reflection Engine)
REFLECTION_URL = os.getenv("REFLECTION_URL", "http://localhost:8001/reflect")
# The Key used to talk to the Brain
INTERNAL_AUTH_TOKEN = os.getenv("ADMIN_API_KEY") 
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# === DEPENDENCIES ===
def get_ai_client():
    """Dependency: Creates OpenAI client on demand."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="Server Error: Missing OpenAI Key")
    return OpenAI(api_key=OPENAI_API_KEY)

def encode_image(file_bytes):
    """Helper: Prepares image for GPT-4o Vision."""
    return base64.b64encode(file_bytes).decode("utf-8")

# === HELPER: THE ORCHESTRATOR ===
async def call_reflection_engine(draft_data: Dict[str, Any], confidence: float):
    """
    Architectural Decision:
    If confidence is low, we don't guess. We delegate to the 'Reflection Engine' 
    microservice to perform a critique and fix loop.
    """
    logger.info(f"📞 Calling Reflection Engine at {REFLECTION_URL}...")
    
    payload = {
        "data_payload": draft_data,
        "validation_rules": "Date must be in YYYY-MM-DD format. Amount must be positive float. Merchant must be capitalized."
    }
    
    headers = {"X-API-KEY": INTERNAL_AUTH_TOKEN}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                REFLECTION_URL,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            
            result = response.json()
            if result["was_modified"]:
                logger.info(f"✨ Data Healed by AI: {result['notes']}")
                return result["refined_data"]
            return draft_data

    except Exception as e:
        logger.error(f"❌ Reflection Service Failed: {str(e)}")
        # Fail gracefully: Return original draft if Brain is down
        return draft_data

# === ENDPOINTS ===

@app.get("/")
def health_check():
    return {"status": "Receipt Processor Online", "architecture": "Microservice/Worker"}

@app.post(
    "/process",
    # 🔒 SECURITY GATE: Enforces RBAC before code runs
    dependencies=[Depends(RequireRole("worker"))]
)
async def process_receipt(
    file: UploadFile = File(...),
    client: OpenAI = Depends(get_ai_client),
    user: UserContext = Depends(get_current_user)
):
    logger.info(f"🧾 Processing request from User: {user.user_id} (Tenant: {user.tenant_id})")

    try:
        # 1. READ & ENCODE
        content = await file.read()
        b64_img = encode_image(content)
        
        # 2. INITIAL EXTRACTION (GPT-4o Vision)
        logger.info("👀 Sending to Vision Model...")
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system", 
                    "content": "Extract receipt data: merchant, date (YYYY-MM-DD), amount, category, confidence (0.0-1.0). Return JSON only."
                },
                {
                    "role": "user", 
                    "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}]
                }
            ],
            response_format={"type": "json_object"}
        )
        
        draft = json.loads(response.choices[0].message.content)
        confidence = float(draft.get("confidence", 0.5))
        
        # 3. ARCHITECTURAL DECISION ( The "Router" Pattern )
        # If confidence is low, route to the specialized AI service
        processing_route = "Direct Extraction"
        
        if confidence < 0.85:
            logger.warning(f"⚠️ Low Confidence ({confidence}). Routing to Reflection Engine.")
            draft = await call_reflection_engine(draft, confidence)
            processing_route = "Reflection Engine (Healed)"
            
        # 4. COMPLIANCE CHECK (The Business Logic Crate)
        compliance = check_business_rules(draft.get("amount", 0.0), draft.get("merchant", "Unknown"))

        return {
            **draft,
            "compliance_status": compliance["status"],
            "ui_blocks": compliance["ui_blocks"],
            "meta": {
                "processed_by": user.user_id,
                "route": processing_route,
                "role": "worker"
            }
        }

    except Exception as e:
        logger.error(f"Critical Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")