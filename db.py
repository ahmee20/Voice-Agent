import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL must be configured to the Supabase Postgres connection string.")
    return url


def get_engine() -> Engine:
    return create_engine(get_database_url(), pool_pre_ping=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows_to_dicts(rows: Any) -> List[Dict[str, Any]]:
    if not rows:
        return []
    return [dict(row._mapping) for row in rows]


def fetch_patient_by_phone(phone_number: str) -> List[Dict[str, Any]]:
    try:
        with get_engine().connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT *
                    FROM patients
                    WHERE phone_number = :phone_number
                      AND deleted_at IS NULL
                    LIMIT 1
                    """
                ),
                {"phone_number": phone_number},
            )
            return _rows_to_dicts(result)
    except Exception:
        logger.exception("Database lookup failed for patient by phone_number")
        raise


def fetch_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
    try:
        with get_engine().connect() as connection:
            result = connection.execute(
                text(
                    """
                    SELECT *
                    FROM patients
                    WHERE patient_id = :patient_id
                      AND deleted_at IS NULL
                    LIMIT 1
                    """
                ),
                {"patient_id": patient_id},
            )
            rows = _rows_to_dicts(result)
            return rows[0] if rows else None
    except Exception:
        logger.exception("Database lookup failed for patient by patient_id")
        raise


def list_patients(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    try:
        clauses = ["deleted_at IS NULL"]
        params: Dict[str, Any] = {}

        if filters:
            for key, value in filters.items():
                if value is None or value == "":
                    continue
                if key == "last_name":
                    clauses.append("last_name ILIKE :last_name")
                    params["last_name"] = f"%{value}%"
                elif key == "date_of_birth":
                    clauses.append("date_of_birth = :date_of_birth")
                    params["date_of_birth"] = value
                elif key == "phone_number":
                    clauses.append("phone_number = :phone_number")
                    params["phone_number"] = value

        query = "SELECT * FROM patients WHERE " + " AND ".join(clauses)
        with get_engine().connect() as connection:
            result = connection.execute(text(query), params)
            return _rows_to_dicts(result)
    except Exception:
        logger.exception("Database list failed for patients")
        raise


def insert_patient(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        columns = ", ".join(patient_data.keys())
        placeholders = ", ".join(f":{key}" for key in patient_data.keys())
        query = text(f"INSERT INTO patients ({columns}) VALUES ({placeholders}) RETURNING *")

        with get_engine().connect() as connection:
            result = connection.execute(query, patient_data)
            connection.commit()
            rows = _rows_to_dicts(result)
            if not rows:
                raise RuntimeError("Database insert returned no patient data")
            return rows[0]
    except Exception:
        logger.exception("Database insert failed for patients table")
        raise


def update_patient(patient_id: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        assignments = ", ".join(f"{key} = :{key}" for key in patient_data.keys())
        query = text(
            f"UPDATE patients SET {assignments} WHERE patient_id = :patient_id RETURNING *"
        )
        params = {**patient_data, "patient_id": patient_id}

        with get_engine().connect() as connection:
            result = connection.execute(query, params)
            connection.commit()
            rows = _rows_to_dicts(result)
            if not rows:
                raise RuntimeError("Database update returned no patient data")
            return rows[0]
    except Exception:
        logger.exception("Database update failed for patient_id=%s", patient_id)
        raise


def soft_delete_patient(patient_id: str) -> Dict[str, Any]:
    try:
        timestamp = utc_now_iso()
        query = text(
            "UPDATE patients SET deleted_at = :deleted_at WHERE patient_id = :patient_id RETURNING *"
        )
        with get_engine().connect() as connection:
            result = connection.execute(query, {"deleted_at": timestamp, "patient_id": patient_id})
            connection.commit()
            rows = _rows_to_dicts(result)
            if not rows:
                raise RuntimeError("Database delete returned no patient data")
            return rows[0]
    except Exception:
        logger.exception("Database soft-delete failed for patient_id=%s", patient_id)
        raise
