import json
import logging
from typing import Any, Dict, List

from fastapi import FastAPI, Request
from fastapi.responses import Response

from tools import check_existing_patient, create_patient, update_patient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("carecloud.webhook")

app = FastAPI(title="CareCloud Vapi Webhook")


def _dispatch_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    if tool_name == "check_existing_patient":
        return check_existing_patient(arguments)
    if tool_name == "create_patient":
        return create_patient(arguments)
    if tool_name == "update_patient":
        return update_patient(arguments)
    logger.warning("Unknown tool name encountered: %s", tool_name)
    return "I wasn't able to find a matching tool for that request."


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
