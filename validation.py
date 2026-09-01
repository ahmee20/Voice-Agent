import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Tuple


STATE_NAMES = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
}

VALID_STATES = set(STATE_NAMES.values())
VALID_SEXES = {"Male", "Female", "Other", "Decline to Answer"}
NAME_PATTERN = re.compile(r"^[A-Za-z\s'\-]+$")
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
ZIP_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")


class ValidationError(ValueError):
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(message)

    def result_string(self) -> str:
        label = self.field.replace("_", " ")
        if label == "date of birth":
            label = "date of birth"

        message = self.message
        if message.startswith("is "):
            message = message[3:]
        elif message.startswith("are "):
            message = message[4:]

        return f"The {label} provided is {message}"


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_phone_number(value: Any) -> str:
    digits = re.sub(r"\D", "", _normalize_text(value))
    if len(digits) > 10 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return digits
    raise ValidationError("phone_number", "not a valid 10-digit U.S. phone number")


def normalize_uuid(value: Any) -> str:
    try:
        import uuid

        normalized = str(value).strip()
        uuid.UUID(normalized)
        return normalized
    except Exception as exc:
        raise ValidationError("patient_id", "not a valid UUID") from exc


def normalize_state(value: Any) -> str:
    raw = _normalize_text(value)
    if not raw:
        raise ValidationError("state", "required and can't be blank")

    candidate = raw.upper()
    if len(candidate) == 2 and candidate in VALID_STATES:
        return candidate

    full_name = raw.title()
    if full_name in STATE_NAMES:
        return STATE_NAMES[full_name]

    raise ValidationError("state", "is not a valid 2-letter U.S. state code")


def normalize_zip_code(value: Any) -> str:
    raw = _normalize_text(value)
    if not ZIP_PATTERN.fullmatch(raw):
        raise ValidationError("zip_code", "is not a valid ZIP code")
    return raw


def normalize_email(value: Any) -> str | None:
    if value is None:
        return None
    raw = _normalize_text(value)
    if not raw:
        return None
    if not EMAIL_PATTERN.fullmatch(raw):
        raise ValidationError("email", "is not a valid email address")
    return raw


def normalize_name(value: Any, field_name: str) -> str:
    raw = _normalize_text(value)
    if not raw:
        raise ValidationError(field_name, "is required and can't be blank")
    if len(raw) > 50:
        raise ValidationError(field_name, "is too long and must be 50 characters or fewer")
    if not NAME_PATTERN.fullmatch(raw):
        raise ValidationError(field_name, "contains invalid characters; only letters, spaces, hyphens, and apostrophes are allowed")
    return raw


def normalize_date_of_birth(value: Any) -> str:
    if value is None:
        raise ValidationError("date_of_birth", "is required and can't be blank")

    if isinstance(value, datetime):
        parsed = value.date()
    elif isinstance(value, date):
        parsed = value
    else:
        raw = _normalize_text(value)
        try:
            if "T" in raw or " " in raw:
                iso_like = raw.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(iso_like).date()
            else:
                parsed = date.fromisoformat(raw)
        except ValueError:
            for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%m-%d-%Y", "%d-%m-%Y", "%B %d, %Y", "%b %d, %Y"):
                try:
                    parsed = datetime.strptime(raw, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                raise ValidationError("date_of_birth", "is not a real date")

    if parsed > date.today():
        raise ValidationError("date_of_birth", "is in the future and can't be saved")

    return parsed.isoformat()


def normalize_sex(value: Any) -> str:
    raw = _normalize_text(value)
    if not raw:
        raise ValidationError("sex", "is required and can't be blank")
    if raw not in VALID_SEXES:
        raise ValidationError("sex", "must be one of Male, Female, Other, or Decline to Answer")
    return raw


def normalize_optional_string(value: Any, field_name: str, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    raw = _normalize_text(value)
    if not raw:
        return None
    if max_length is not None and len(raw) > max_length:
        raise ValidationError(field_name, f"is too long and must be {max_length} characters or fewer")
    return raw


def normalize_phone_optional(value: Any) -> str | None:
    if value is None:
        return None
    raw = _normalize_text(value)
    if not raw:
        return None
    return normalize_phone_number(raw)


def normalize_patient_data(payload: Dict[str, Any], partial: bool = False) -> Tuple[Dict[str, Any], List[str]]:
    normalized: Dict[str, Any] = {}
    errors: List[str] = []

    field_map = {
        "first_name": ("first_name", lambda v: normalize_name(v, "first_name")),
        "last_name": ("last_name", lambda v: normalize_name(v, "last_name")),
        "date_of_birth": ("date_of_birth", normalize_date_of_birth),
        "sex": ("sex", normalize_sex),
        "phone_number": ("phone_number", normalize_phone_number),
        "email": ("email", normalize_email),
        "address_line_1": ("address_line_1", lambda v: _require_text(v, "address_line_1")),
        "address_line_2": ("address_line_2", lambda v: normalize_optional_string(v, "address_line_2", 255)),
        "city": ("city", lambda v: _require_text(v, "city", max_length=100)),
        "state": ("state", normalize_state),
        "zip_code": ("zip_code", normalize_zip_code),
        "insurance_provider": ("insurance_provider", lambda v: normalize_optional_string(v, "insurance_provider", 255)),
        "insurance_member_id": ("insurance_member_id", lambda v: normalize_optional_string(v, "insurance_member_id", 255)),
        "preferred_language": ("preferred_language", lambda v: normalize_optional_string(v, "preferred_language", 100) or "English"),
        "partial_info": ("partial_info", lambda v: bool(v)),
        "emergency_contact_name": ("emergency_contact_name", lambda v: normalize_optional_string(v, "emergency_contact_name", 255)),
        "emergency_contact_phone": ("emergency_contact_phone", normalize_phone_optional),
    }

    for field_name, transform in field_map.items():
        if field_name in payload and payload[field_name] is not None:
            try:
                normalized[field_name] = transform[1](payload[field_name])
            except ValidationError as exc:
                errors.append(exc.result_string())
        elif not partial and field_name not in payload:
            if field_name in {"first_name", "last_name", "date_of_birth", "sex", "phone_number", "address_line_1", "city", "state", "zip_code"}:
                errors.append(f"The {field_name.replace('_', ' ')} provided is required and can't be blank")

    if "preferred_language" not in payload and not partial:
        normalized["preferred_language"] = "English"
    elif "preferred_language" in payload and payload["preferred_language"] is None:
        normalized["preferred_language"] = "English"

    if "partial_info" in payload and payload["partial_info"] is not None:
        normalized["partial_info"] = bool(payload["partial_info"])

    return normalized, errors


def _require_text(value: Any, field_name: str, max_length: int | None = None) -> str:
    raw = _normalize_text(value)
    if not raw:
        raise ValidationError(field_name, "is required and can't be blank")
    if max_length is not None and len(raw) > max_length:
        raise ValidationError(field_name, f"is too long and must be {max_length} characters or fewer")
    return raw


def build_update_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    allowed_fields = [
        "first_name",
        "last_name",
        "date_of_birth",
        "sex",
        "phone_number",
        "email",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "zip_code",
        "insurance_provider",
        "insurance_member_id",
        "preferred_language",
        "partial_info",
        "emergency_contact_name",
        "emergency_contact_phone",
    ]

    normalized: Dict[str, Any] = {}
    errors: List[str] = []

    for field_name in allowed_fields:
        if field_name not in payload or payload[field_name] is None:
            continue
        try:
            if field_name == "preferred_language":
                normalized[field_name] = normalize_optional_string(payload[field_name], field_name, 100) or "English"
            elif field_name == "partial_info":
                normalized[field_name] = bool(payload[field_name])
            elif field_name == "phone_number":
                normalized[field_name] = normalize_phone_number(payload[field_name])
            elif field_name == "state":
                normalized[field_name] = normalize_state(payload[field_name])
            elif field_name == "date_of_birth":
                normalized[field_name] = normalize_date_of_birth(payload[field_name])
            elif field_name == "email":
                normalized[field_name] = normalize_email(payload[field_name])
            elif field_name in {"first_name", "last_name"}:
                normalized[field_name] = normalize_name(payload[field_name], field_name)
            elif field_name == "sex":
                normalized[field_name] = normalize_sex(payload[field_name])
            elif field_name == "zip_code":
                normalized[field_name] = normalize_zip_code(payload[field_name])
            elif field_name == "emergency_contact_phone":
                normalized[field_name] = normalize_phone_optional(payload[field_name])
            else:
                normalized[field_name] = _require_text(payload[field_name], field_name) if field_name in {"address_line_1", "city"} else normalize_optional_string(payload[field_name], field_name, 255)
        except ValidationError as exc:
            errors.append(exc.result_string())

    return normalized, errors
