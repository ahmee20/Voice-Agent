import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from db import list_patients as db_list_patients
from db import fetch_patient_by_id as db_fetch_patient_by_id
from db import insert_patient as db_insert_patient
from db import soft_delete_patient as db_soft_delete_patient
from db import update_patient as db_update_patient
from tools import check_existing_patient, create_patient, update_patient
from validation import ValidationError, build_update_payload, normalize_patient_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("carecloud.webhook")

app = FastAPI(title="CareCloud API")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dispatch_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    if tool_name == "check_existing_patient":
        return check_existing_patient(arguments)
    if tool_name == "create_patient":
        return create_patient(arguments)
    if tool_name == "update_patient":
        return update_patient(arguments)
    logger.warning("Unknown tool name encountered: %s", tool_name)
    return "I wasn't able to find a matching tool for that request."


@app.get("/")
async def root() -> Dict[str, str]:
    return {"service": "CareCloud API", "status": "ok"}


@app.get("/patients")
async def list_patients_route(last_name: str | None = None, date_of_birth: str | None = None, phone_number: str | None = None):
    filters: Dict[str, str | None] = {
        "last_name": last_name,
        "date_of_birth": date_of_birth,
        "phone_number": phone_number,
    }
    return db_list_patients(filters)


@app.get("/patients/{patient_id}")
async def get_patient_route(patient_id: str):
    patient = db_fetch_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


@app.post("/patients")
async def create_patient_route(request: Request):
    payload = await request.json()
    try:
        cleaned, errors = normalize_patient_data(payload, partial=False)
        if errors:
            raise HTTPException(status_code=422, detail=errors[0])
        cleaned["patient_id"] = str(uuid.uuid4())
        cleaned["created_at"] = _utc_now_iso()
        cleaned["updated_at"] = _utc_now_iso()
        cleaned["preferred_language"] = cleaned.get("preferred_language", "English")
        created = db_insert_patient(cleaned)
        return created
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.result_string()) from exc
    except Exception as exc:
        logger.exception("REST create patient failed")
        raise HTTPException(status_code=500, detail="Unable to create patient") from exc


@app.put("/patients/{patient_id}")
async def update_patient_route(patient_id: str, request: Request):
    payload = await request.json()
    if not payload:
        raise HTTPException(status_code=400, detail="No update fields were provided")

    updates, errors = build_update_payload(payload)
    if errors:
        raise HTTPException(status_code=422, detail=errors[0])
    if not updates:
        raise HTTPException(status_code=400, detail="No valid patient fields to update")

    updates["updated_at"] = _utc_now_iso()
    updated = db_update_patient(patient_id, updates)
    return updated


@app.delete("/patients/{patient_id}")
async def delete_patient_route(patient_id: str):
    existing = db_fetch_patient_by_id(patient_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Patient not found")

    deleted = db_soft_delete_patient(patient_id)
    return {"message": "Patient soft deleted successfully", "patient_id": patient_id, "deleted_at": deleted.get("deleted_at")}


@app.post("/webhook")
async def webhook(request: Request) -> Response:
    try:
        payload = await request.json()
    except Exception:
        logger.exception("Webhook request was not valid JSON")
        fallback = {
            "results": [
                {
                    "toolCallId": "unknown",
                    "result": "I wasn't able to process that tool request because the payload was invalid.",
                }
            ]
        }
        return Response(
            content=json.dumps(fallback, separators=(",", ":")),
            media_type="application/json",
            status_code=200,
        )

    tool_calls: List[Dict[str, Any]] = payload.get("message", {}).get("toolCallList", []) or []
    if not isinstance(tool_calls, list):
        tool_calls = []

    results: List[Dict[str, Any]] = []
    for tool_call in tool_calls:
        function = tool_call.get("function", {}) or {}
        tool_name = function.get("name")
        arguments = function.get("arguments", {}) or {}
        tool_call_id = tool_call.get("id", "unknown")

        if not isinstance(arguments, dict):
            arguments = {}

        logger.info("Incoming tool call: tool_name=%s arguments=%s", tool_name, arguments)

        try:
            result_text = _dispatch_tool(tool_name, arguments)
            logger.info("Tool call handled: tool_name=%s toolCallId=%s outcome=success", tool_name, tool_call_id)
        except Exception:
            logger.exception("Unhandled exception while processing tool_name=%s toolCallId=%s", tool_name, tool_call_id)
            result_text = "I wasn't able to complete that action because of a system error, a staff member will need to follow up."

        results.append({"toolCallId": tool_call_id, "result": result_text})

    # Vapi requires a top-level object with a results array and no embedded line breaks in the body.
    response_body = {"results": results}
    return Response(
        content=json.dumps(response_body, separators=(",", ":")),
        media_type="application/json",
        status_code=200,
    )
