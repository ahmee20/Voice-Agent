import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from db import fetch_patient_by_id, fetch_patient_by_phone, insert_patient, update_patient as update_patient_record
from validation import ValidationError, build_update_payload, normalize_patient_data, normalize_phone_number, normalize_uuid

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def check_existing_patient(arguments: Dict[str, Any]) -> str:
    phone_number = arguments.get("phone_number")
    try:
        normalized_phone = normalize_phone_number(phone_number) if phone_number is not None else ""
        if not normalized_phone:
            return "The phone number is required and can't be blank."

        patient_rows = await fetch_patient_by_phone(normalized_phone)
        if not patient_rows:
            return "I couldn't find an existing patient with that phone number, so this looks like a new registration."

        patient = patient_rows[0]
        first_name = patient.get("first_name", "Unknown")
        last_name = patient.get("last_name", "Unknown")
        patient_id = patient.get("patient_id")
        return (
            f"I found an existing patient record for {first_name} {last_name} "
            f"with patient ID {patient_id}. You can update that record instead of creating a new one."
        )
    except ValidationError as exc:
        logger.warning("Validation failure in check_existing_patient: %s", exc)
        return exc.result_string()
    except Exception:
        logger.exception("Unexpected error while checking for an existing patient")
        return "I wasn't able to check for an existing patient because of a system error, a staff member will need to follow up."


async def create_patient(arguments: Dict[str, Any]) -> str:
    try:
        cleaned, errors = normalize_patient_data(arguments, partial=False)
        if errors:
            return errors[0]

        if not cleaned:
            return "No patient information was provided to save."

        cleaned["phone_number"] = normalize_phone_number(cleaned["phone_number"])
        cleaned["patient_id"] = str(uuid.uuid4())
        cleaned["created_at"] = _utc_now_iso()
        cleaned["updated_at"] = _utc_now_iso()

        record = await insert_patient(cleaned)
        patient_id = record.get("patient_id")
        return f"The patient record was saved successfully with patient ID {patient_id}."
    except ValidationError as exc:
        logger.warning("Validation failure in create_patient: %s", exc)
        return exc.result_string()
    except Exception:
        logger.exception("Supabase create patient failed")
        return "I wasn't able to save that due to a system error, a staff member will need to follow up."


async def update_patient(arguments: Dict[str, Any]) -> str:
    patient_id = arguments.get("patient_id")
    if patient_id is None or str(patient_id).strip() == "":
        return "The patient ID is required to update an existing record."

    try:
        patient_uuid = normalize_uuid(patient_id)
        existing = await fetch_patient_by_id(patient_uuid)
        if not existing:
            return "I couldn't find a patient with that ID, so I couldn't update the record."

        updates, errors = build_update_payload(arguments)
        if errors:
            return errors[0]
        if not updates:
            return "I didn't receive any patient details to update."

        updates["updated_at"] = _utc_now_iso()
        await update_patient_record(patient_uuid, updates)
        updated_fields = ", ".join(sorted(updates.keys())) if updates else "the record"
        return f"I updated the following fields: {updated_fields}."
    except ValidationError as exc:
        logger.warning("Validation failure in update_patient: %s", exc)
        return exc.result_string()
    except Exception:
        logger.exception("Supabase update patient failed for patient ID %s", patient_id)
        return "I wasn't able to update that patient record due to a system error, a staff member will need to follow up."
