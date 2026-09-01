import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from validation import normalize_phone_number

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    normalized = url.strip()
    if "+asyncpg" in normalized:
        logger.warning("SUPABASE_URL used asyncpg; converting to the psycopg async dialect.")
        normalized = normalized.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    elif normalized.startswith("postgresql://"):
        normalized = normalized.replace("postgresql://", "postgresql+psycopg://", 1)
    elif "+psycopg2" in normalized:
        normalized = normalized.replace("postgresql+psycopg2://", "postgresql+psycopg://")
    return normalized


def get_database_url() -> str:
    url = os.getenv("SUPABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "SUPABASE_URL/DATABASE_URL must be configured to the Supabase Postgres connection string."
        )
    normalized_url = _normalize_database_url(url)
    if normalized_url.startswith("postgresql+asyncpg://"):
        raise RuntimeError(
            "SUPABASE_URL must not use asyncpg. Use a psycopg async Postgres URL, for example: "
            "postgresql+psycopg://postgres:password@db.project-ref.supabase.co:5432/postgres"
        )
    return normalized_url


def get_engine() -> AsyncEngine:
    return create_async_engine(get_database_url(), pool_pre_ping=True)


def get_session_factory():
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rows_to_dicts(rows: Any) -> List[Dict[str, Any]]:
    if not rows:
        return []
    return [dict(row._mapping) for row in rows]


async def fetch_patient_by_phone(phone_number: str) -> List[Dict[str, Any]]:
    try:
        normalized_phone = normalize_phone_number(phone_number)
        engine = get_engine()
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT *
                    FROM patients
                    WHERE phone_number = :phone_number
                      AND deleted_at IS NULL
                    ORDER BY created_at ASC
                    """
                ),
                {"phone_number": normalized_phone},
            )
            rows = result.mappings().all()
            await connection.close()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Database lookup failed for patient by phone_number")
        raise


async def fetch_patient_by_id(patient_id: str) -> Optional[Dict[str, Any]]:
    try:
        engine = get_engine()
        async with engine.connect() as connection:
            result = await connection.execute(
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
            rows = result.mappings().all()
            return dict(rows[0]) if rows else None
    except Exception:
        logger.exception("Database lookup failed for patient by patient_id")
        raise


async def list_patients(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
                    params["phone_number"] = normalize_phone_number(value)

        query = "SELECT * FROM patients WHERE " + " AND ".join(clauses)
        engine = get_engine()
        async with engine.connect() as connection:
            result = await connection.execute(text(query), params)
            rows = result.mappings().all()
            return [dict(row) for row in rows]
    except Exception:
        logger.exception("Database list failed for patients")
        raise


async def insert_patient(patient_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        columns = ", ".join(patient_data.keys())
        placeholders = ", ".join(f":{key}" for key in patient_data.keys())
        query = text(f"INSERT INTO patients ({columns}) VALUES ({placeholders}) RETURNING *")

        engine = get_engine()
        async with engine.begin() as connection:
            result = await connection.execute(query, patient_data)
            row = result.mappings().first()
            if row is None:
                raise RuntimeError("Database insert returned no patient data")
            return dict(row)
    except Exception:
        logger.exception("Database insert failed for patients table")
        raise


async def update_patient(patient_id: str, patient_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        assignments = ", ".join(f"{key} = :{key}" for key in patient_data.keys())
        query = text(
            f"UPDATE patients SET {assignments} WHERE patient_id = :patient_id RETURNING *"
        )
        params = {**patient_data, "patient_id": patient_id}

        engine = get_engine()
        async with engine.begin() as connection:
            result = await connection.execute(query, params)
            row = result.mappings().first()
            if row is None:
                raise RuntimeError("Database update returned no patient data")
            return dict(row)
    except Exception:
        logger.exception("Database update failed for patient_id=%s", patient_id)
        raise


async def soft_delete_patient(patient_id: str) -> Dict[str, Any]:
    try:
        timestamp = utc_now_iso()
        query = text(
            "UPDATE patients SET deleted_at = :deleted_at WHERE patient_id = :patient_id RETURNING *"
        )
        engine = get_engine()
        async with engine.begin() as connection:
            result = await connection.execute(query, {"deleted_at": timestamp, "patient_id": patient_id})
            row = result.mappings().first()
            if row is None:
                raise RuntimeError("Database delete returned no patient data")
            return dict(row)
    except Exception:
        logger.exception("Database soft-delete failed for patient_id=%s", patient_id)
        raise
