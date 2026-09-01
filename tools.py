import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from db import fetch_patient_by_id, fetch_patient_by_phone, insert_patient, update_patient as update_patient_record
from validation import ValidationError, build_update_payload, normalize_patient_data, normalize_phone_number, normalize_uuid

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _merge_patient_update(existing: Dict[str, Any], new_values: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    for key, value in new_values.items():
        if key in {"patient_id", "created_at", "deleted_at"}:
            continue
        if value is None:
            continue
        merged[key] = value
    return merged


async def check_existing_patient(arguments: Dict[str, Any]) -> Dict[str, Any]:
    phone_number = arguments.get("phone_number")
    partial_info = bool(arguments.get("partial_info", False))
    try:
        normalized_phone = normalize_phone_number(phone_number) if phone_number is not None else ""
        if not normalized_phone:
            return {"status": "error", "message": "The phone number is required and can't be blank."}

        patient_rows = await fetch_patient_by_phone(normalized_phone)
        if not patient_rows:
            return {"status": "not_found", "partial_info": partial_info, "message": "No patient found for this phone number."}

        patient = patient_rows[0]
        return {
            "status": "found",
            "partial_info": bool(patient.get("partial_info", False)) or partial_info,
            "patient": patient,
        }
    except ValidationError as exc:
        logger.warning("Validation failure in check_existing_patient: %s", exc)
        return {"status": "error", "message": exc.result_string()}
    except Exception:
        logger.exception("Unexpected error while checking for an existing patient")
        return {
            "status": "error",
            "message": "I wasn't able to check for an existing patient because of a system error, a staff member will need to follow up.",
        }


async def create_patient(arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        cleaned, errors = normalize_patient_data(arguments, partial=False)
        if errors:
            return {"status": "error", "message": errors[0]}

        if not cleaned:
            return {"status": "error", "message": "No patient information was provided to save."}

        phone_number = normalize_phone_number(cleaned["phone_number"])
        cleaned["phone_number"] = phone_number

        existing_rows = await fetch_patient_by_phone(phone_number)
        if existing_rows:
            existing = existing_rows[0]
            updates = {k: v for k, v in cleaned.items() if v is not None and k not in {"patient_id", "created_at", "updated_at"}}
            updates["updated_at"] = _utc_now_iso()
            updates["partial_info"] = bool(arguments.get("partial_info", False)) or bool(existing.get("partial_info", False))
            merged = await _merge_patient_update(existing, updates)
            updated = await update_patient_record(existing["patient_id"], {k: v for k, v in merged.items() if k not in {"patient_id", "created_at", "deleted_at"}})
            return {"status": "updated", "partial_info": bool(updated.get("partial_info", False)), "patient": updated, "existing_record": True}

        cleaned["patient_id"] = str(uuid.uuid4())
        cleaned["created_at"] = _utc_now_iso()
        cleaned["updated_at"] = _utc_now_iso()
        cleaned["partial_info"] = bool(arguments.get("partial_info", False)) or bool(cleaned.get("partial_info", False))

        record = await insert_patient(cleaned)
        return {"status": "created", "partial_info": bool(record.get("partial_info", False)), "patient": record, "existing_record": False}
    except ValidationError as exc:
        logger.warning("Validation failure in create_patient: %s", exc)
        return {"status": "error", "message": exc.result_string()}
    except Exception:
        logger.exception("Supabase create patient failed")
        return {
            "status": "error",
            "message": "I wasn't able to save that due to a system error, a staff member will need to follow up.",
        }


async def update_patient(arguments: Dict[str, Any]) -> Dict[str, Any]:
    patient_id = arguments.get("patient_id")
    if patient_id is None or str(patient_id).strip() == "":
        return {"status": "error", "message": "The patient ID is required to update an existing record."}

    try:
        patient_uuid = normalize_uuid(patient_id)
        existing = await fetch_patient_by_id(patient_uuid)
        if not existing:
            return {"status": "not_found", "partial_info": bool(arguments.get("partial_info", False)), "message": "I couldn't find a patient with that ID, so I couldn't update the record."}

        updates, errors = build_update_payload(arguments)
        if errors:
            return {"status": "error", "message": errors[0]}
        if not updates:
            return {"status": "error", "message": "I didn't receive any patient details to update."}

        updates["partial_info"] = bool(arguments.get("partial_info", False)) or bool(existing.get("partial_info", False))
        updates["updated_at"] = _utc_now_iso()
        updated = await update_patient_record(patient_uuid, updates)
        return {"status": "updated", "partial_info": bool(updated.get("partial_info", False)), "patient": updated}
    except ValidationError as exc:
        logger.warning("Validation failure in update_patient: %s", exc)
        return {"status": "error", "message": exc.result_string()}
    except Exception:
        logger.exception("Supabase update patient failed for patient ID %s", patient_id)
        return {
            "status": "error",
            "message": "I wasn't able to update that patient record due to a system error, a staff member will need to follow up.",
        }
