import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

logger = logging.getLogger(__name__)


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured.")

    return create_client(url, key)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def list_patients(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    try:
        client = get_supabase_client()
        query = client.table("patients").select("*").is_("deleted_at", "null")

        if filters:
            for key, value in filters.items():
                if value is None or value == "":
                    continue
                if key == "last_name":
                    query = query.ilike("last_name", f"%{value}%")
                elif key in {"date_of_birth", "phone_number"}:
                    query = query.eq(key, value)

        response = query.execute()
        return getattr(response, "data", []) or []
    except Exception:
        logger.exception("Supabase list failed for patients")
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


def soft_delete_patient(patient_id: str) -> Dict[str, Any]:
    try:
        client = get_supabase_client()
        timestamp = utc_now_iso()
        response = client.table("patients").update({"deleted_at": timestamp}).eq("patient_id", patient_id).execute()
        rows = getattr(response, "data", []) or []
        if not rows:
            raise RuntimeError("Supabase delete returned no patient data")
        return rows[0]
    except Exception:
        logger.exception("Supabase soft-delete failed for patient_id=%s", patient_id)
        raise
