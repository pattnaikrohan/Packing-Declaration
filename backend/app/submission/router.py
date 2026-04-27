"""
Submission router — POSTs the file info to Power Automate,
receives the AI Builder response, and transforms it into
a PackingDeclaration matching the OCR extraction format.
"""
import logging
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
import httpx

from app.ingestion.schema import PackingDeclaration
from app.ingestion.pa_transformer import transform_pa_response
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["submission"])


@router.post("/submit")
async def submit(declaration: PackingDeclaration):
    """
    Send the reviewed packing declaration JSON to Power Automate.
    Stamps submitted_at timestamp before sending.
    """
    import uuid
    dump = declaration.model_dump()
    
    # Construct a minimal payload containing ONLY serial number and filename
    payload = {
        "serial_number": dump.get("serial_number") or "1",
        "filename": dump.get("file_name", "unknown")
    }

    if not settings.POWER_AUTOMATE_URL:
        logger.info(f"[submit] No PA URL configured — mock mode. Payload: {payload}")
        return {
            "ok": True,
            "mock": True,
            "message": "No Power Automate URL configured — payload logged only.",
            "payload": payload,
        }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                settings.POWER_AUTOMATE_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        logger.info(f"[submit] POST → Power Automate: HTTP {resp.status_code}")
        return {
            "ok": resp.status_code < 300,
            "mock": False,
            "status_code": resp.status_code,
            "message": f"Sent to Power Automate (HTTP {resp.status_code})",
        }
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Power Automate request timed out")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach Power Automate: {str(e)}")


@router.post("/pa-extract")
async def pa_extract(declaration: PackingDeclaration):
    """
    Send file reference to Power Automate AI Builder, receive the
    AI Builder response, and transform it into a PackingDeclaration
    matching the same format as the OCR extraction engine.
    
    Returns the transformed PackingDeclaration as JSON.
    """
    dump = declaration.model_dump()
    filename = dump.get("file_name", "unknown")
    
    payload = {
        "serial_number": dump.get("serial_number") or "1",
        "filename": filename
    }

    if not settings.POWER_AUTOMATE_URL:
        logger.info(f"[pa-extract] No PA URL configured — mock mode.")
        return {
            "ok": False,
            "mock": True,
            "message": "No Power Automate URL configured.",
        }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                settings.POWER_AUTOMATE_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
        
        if resp.status_code >= 300:
            logger.error(f"[pa-extract] PA returned HTTP {resp.status_code}")
            raise HTTPException(
                status_code=502,
                detail=f"Power Automate returned HTTP {resp.status_code}"
            )
        
        pa_response = resp.json()
        logger.info(f"[pa-extract] Received PA response, transforming...")
        
        # Transform the AI Builder response into our PackingDeclaration format
        pkd = transform_pa_response(pa_response, filename=filename)
        
        return {
            "ok": True,
            "mock": False,
            "extraction": pkd.model_dump(),
        }
        
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Power Automate request timed out")
    except Exception as e:
        logger.error(f"[pa-extract] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"PA extraction failed: {str(e)}")


@router.post("/pa-transform")
async def pa_transform_raw(pa_response: dict):
    """
    Accepts a raw Power Automate AI Builder JSON response and transforms
    it into a PackingDeclaration. Useful for debugging / testing the
    transformer without calling Power Automate.
    """
    try:
        pkd = transform_pa_response(pa_response, filename="manual_test")
        return {
            "ok": True,
            "extraction": pkd.model_dump(),
        }
    except Exception as e:
        logger.error(f"[pa-transform] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail=f"Transform failed: {str(e)}")
