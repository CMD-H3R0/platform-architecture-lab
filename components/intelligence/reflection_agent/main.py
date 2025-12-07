import os
import json
import logging
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from components.security.auth_gateway.auth import RequireRole 

load_dotenv()

app = FastAPI(title="Reflection Agent Service")
logger = logging.getLogger("reflection_agent")
logger.setLevel(logging.INFO)

# Load Key Securely
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None

class ReflectionRequest(BaseModel):
    data_payload: dict
    validation_rules: str

class ReflectionResponse(BaseModel):
    refined_data: dict
    was_modified: bool
    notes: str

@app.post("/reflect", dependencies=[Depends(RequireRole("admin"))])
async def reflect(payload: ReflectionRequest):
    """
    Agentic Pattern: Reflection.
    Critiques and fixes data based on validation rules.
    """
    logger.info(f"🧠 Reflection Agent invoked.")

    # MOCK FALLBACK (Only runs if OpenAI Key is missing in Env)
    if not client:
        logger.warning("⚠️ No OpenAI Key in Environment. Using Mock Logic.")
        corrected = payload.data_payload.copy()
        was_fixed = False
        notes = "AI Unavailable (Env Var Missing). Checks passed."
        
        # Simple Mock Rule for Demo stability
        if "date" in corrected and "2026" in corrected["date"]:
            corrected["date"] = "2025-12-06"
            was_fixed = True
            notes = "Mock AI: Fixed future date error."
            
        return {"refined_data": corrected, "was_modified": was_fixed, "notes": notes}

    try:
        system_prompt = "You are a Data Quality Agent. Validate and fix JSON data."
        user_prompt = f"""
        RULES: {payload.validation_rules}
        DATA: {json.dumps(payload.data_payload)}
        
        INSTRUCTIONS:
        1. Critique data against rules.
        2. Fix errors if found.
        3. Return JSON: {{ "refined_data": {{...}}, "was_modified": bool, "notes": "string" }}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"AI Failure: {e}")
        raise HTTPException(status_code=500, detail=str(e))