import asyncio
import inspect
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")


def api_response(data: Any = None, error: Any = None, status_code: int = 200) -> JSONResponse:
    payload = {
        "data": jsonable_encoder(data),
        "error": jsonable_encoder(error),
    }
    return JSONResponse(status_code=status_code, content=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    error_payload = {"message": detail} if not isinstance(detail, dict) else detail
    return api_response(data=None, error=error_payload, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error: %s", exc)
    return api_response(data=None, error={"message": "Internal server error"}, status_code=500)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _dispatch_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    tool_lookup = {
        "check_existing_patient": check_existing_patient,
        "create_patient": create_patient,
        "update_patient": update_patient,
    }
    tool_fn = tool_lookup.get(tool_name)
    if tool_fn is None:
        logger.warning("Unknown tool name encountered: %s", tool_name)
        return {"status": "error", "message": "I wasn't able to find a matching tool for that request."}

    result = tool_fn(arguments)
    if inspect.isawaitable(result):
        result = await result
    return result


@app.get("/")
async def root() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/ui")
async def ui() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/patients")
async def list_patients_route(last_name: str | None = None, date_of_birth: str | None = None, phone_number: str | None = None):
    filters: Dict[str, str | None] = {
        "last_name": last_name,
        "date_of_birth": date_of_birth,
        "phone_number": phone_number,
    }
    try:
        patients = await db_list_patients(filters)
        return api_response(data=patients)
    except Exception:
        logger.exception("Failed to list patients")
        return api_response(data=None, error={"message": "Unable to load patients"}, status_code=500)


@app.get("/patients/{patient_id}")
async def get_patient_route(patient_id: str):
    try:
        uuid.UUID(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid patient_id: must be a valid UUID") from exc

    patient = await db_fetch_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return api_response(data=patient)


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
        created = await db_insert_patient(cleaned)
        return api_response(data=created, status_code=201)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.result_string()) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("REST create patient failed")
        raise HTTPException(status_code=500, detail="Unable to create patient") from exc


@app.put("/patients/{patient_id}")
async def update_patient_route(patient_id: str, request: Request):
    try:
        uuid.UUID(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid patient_id: must be a valid UUID") from exc

    payload = await request.json()
    if not payload:
        raise HTTPException(status_code=400, detail="No update fields were provided")

    updates, errors = build_update_payload(payload)
    if errors:
        raise HTTPException(status_code=422, detail=errors[0])
    if not updates:
        raise HTTPException(status_code=400, detail="No valid patient fields to update")

    updates["updated_at"] = _utc_now_iso()
    updated = await db_update_patient(patient_id, updates)
    return api_response(data=updated)


@app.delete("/patients/{patient_id}")
async def delete_patient_route(patient_id: str):
    try:
        uuid.UUID(patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid patient_id: must be a valid UUID") from exc

    existing = await db_fetch_patient_by_id(patient_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Patient not found")

    deleted = await db_soft_delete_patient(patient_id)
    return api_response(
        data={"message": "Patient soft deleted successfully", "patient_id": patient_id, "deleted_at": deleted.get("deleted_at")}
    )


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
            tool_result = await _dispatch_tool(tool_name, arguments)
            logger.info("Tool call handled: tool_name=%s toolCallId=%s outcome=success", tool_name, tool_call_id)
        except Exception:
            logger.exception("Unhandled exception while processing tool_name=%s toolCallId=%s", tool_name, tool_call_id)
            tool_result = {
                "status": "error",
                "message": "I wasn't able to complete that action because of a system error, a staff member will need to follow up.",
            }

        results.append({"toolCallId": tool_call_id, "result": tool_result})

    response_body = {"results": results}
    return Response(
        content=json.dumps(response_body, separators=(",", ":")),
        media_type="application/json",
        status_code=200,
    )
