import uuid

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root_and_ui_are_200_json_not_required():
    response = client.get("/")
    assert response.status_code == 200

    response = client.get("/ui")
    assert response.status_code == 200


def test_list_patients_response_envelope_and_status():
    response = client.get("/patients")
    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert "error" in payload
    assert payload["error"] is None


def test_get_patient_bad_uuid_returns_400_and_envelope():
    response = client.get("/patients/not-a-uuid")
    assert response.status_code == 400
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"] is not None


def test_phone_number_is_normalized_by_removing_leading_one_when_needed():
    from validation import normalize_phone_number

    assert normalize_phone_number("2234567899") == "2234567899"
    assert normalize_phone_number("12234567899") == "2234567899"


def test_webhook_accepts_vapi_camel_case_field_names():
    response = client.post(
        "/webhook",
        json={
            "message": {
                "toolCallList": [
                    {
                        "id": "tool-camel-case",
                        "function": {
                            "name": "check_existing_patient",
                            "arguments": {"phoneNumber": "12234567899", "partialInfo": True},
                        },
                    }
                ]
            }
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["toolCallId"] == "tool-camel-case"
    assert "status" in payload["results"][0]["result"]


def test_create_patient_invalid_input_returns_422_and_envelope():
    response = client.post(
        "/patients",
        json={
            "first_name": "",
            "last_name": "",
            "email": "bad-email",
            "phone_number": "",
            "date_of_birth": "not-a-date",
            "state": "",
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"] is not None


def test_webhook_return_shape_for_empty_payload():
    response = client.post("/webhook", json={"message": {"toolCallList": []}})
    assert response.status_code == 200
    payload = response.json()
    assert "results" in payload
    assert isinstance(payload["results"], list)


def test_webhook_handles_uuid_values_in_tool_result():
    import main

    async def fake_dispatch(tool_name, arguments):
        return {
            "status": "found",
            "patient": {"patient_id": uuid.uuid4(), "first_name": "John"},
        }

    original = main._dispatch_tool
    main._dispatch_tool = fake_dispatch
    try:
        response = client.post(
            "/webhook",
            json={
                "message": {
                    "toolCallList": [
                        {
                            "id": "tool-1",
                            "function": {"name": "check_existing_patient", "arguments": {"phone_number": "2234567899"}},
                        }
                    ]
                }
            },
        )
    finally:
        main._dispatch_tool = original

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["result"]["status"] == "found"
    assert payload["results"][0]["result"]["patient"]["patient_id"]
