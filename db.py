import logging
import os
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured.")

    return create_client(url, key)


def fetch_patient_by_phone(phone_number: str) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_client()
        response = (
            client.table("patients")
            .select("*")
            .eq("phone_number", phone_number)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        return getattr(response, "data", []) or []
    except Exception:
        logger.exception("Supabase lookup failed for patient by phone_number")
        raise


def fetch_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
    try:
        client = get_supabase_client()
        response = (
            client.table("patients")
            .select("*")
            .eq("patient_id", patient_id)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", []) or []
        return rows[0] if rows else None
    except Exception:
        logger.exception("Supabase lookup failed for patient by patient_id")
        raise


def insert_patient(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        client = get_supabase_client()
        response = client.table("patients").insert(patient_data).execute()
        rows = getattr(response, "data", []) or []
        if not rows:
            raise RuntimeError("Supabase insert returned no patient data")
        return rows[0]
    except Exception:
        logger.exception("Supabase insert failed for patients table")
        raise


def update_patient(patient_id: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        client = get_supabase_client()
        response = client.table("patients").update(patient_data).eq("patient_id", patient_id).execute()
        rows = getattr(response, "data", []) or []
        if not rows:
            raise RuntimeError("Supabase update returned no patient data")
        return rows[0]
    except Exception:
        logger.exception("Supabase update failed for patient_id=%s", patient_id)
        raise
