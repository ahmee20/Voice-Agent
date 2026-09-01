# Voice AI Patient Registration Agent

## Table of Contents

- [Overview](#overview)
- [Challenge Summary](#challenge-summary)
- [What This Solution Includes](#what-this-solution-includes)
- [System Architecture](#system-architecture)
- [High-Level Data Flow](#high-level-data-flow)
- [Functional Requirements from the Assessment](#functional-requirements-from-the-assessment)
- [Live Demo](#live-demo)
- [REST API](#rest-api)
- [Webhook / Vapi Tool Contract](#webhook--vapi-tool-contract)
- [Data Model and Schema](#data-model-and-schema)
- [Prompt / Agent-Level Requirements and Conversation Design](#prompt--agent-level-requirements-and-conversation-design)
- [Edge Cases and Resilience Behavior](#edge-cases-and-resilience-behavior)
- [Duplicate Handling Behavior](#duplicate-handling-behavior)
- [Trade-offs: Accuracy vs Latency vs Cost](#trade-offs-accuracy-vs-latency-vs-cost)


## Overview

This project is a complete implementation of the take-home technical assessment for a voice-based patient registration system. The system is designed to let a caller speak naturally to a voice AI assistant, collect patient demographic information, persist the data to a database, and expose the records through a lightweight REST API and dashboard.

The core goal is to integrate multiple systems under time pressure:

- Telephony / voice AI layer
- LLM reasoning and prompt-driven conversation flow
- Backend service and business logic
- Database persistence and validation
- REST API and dashboard UI
- Observability and edge-case handling

This repository implements the solution in Python with FastAPI, SQLAlchemy, PostgreSQL/Supabase, a Vapi-style tool-calling webhook pattern, and a simple static dashboard for patient viewing.

---

## Challenge Summary

The original assessment is a voice AI patient registration workflow for a U.S. healthcare intake scenario. The objective is to:

- provide a voice AI agent on a real or test-callable phone number
- collect required patient demographics through a natural conversation
- validate and store that data persistently
- let the system recall prior patients on subsequent calls
- provide a REST API for listing and viewing patient records
- document assumptions, limitations, and edge-case behavior clearly

The challenge explicitly tests whether the engineer can integrate multiple systems end-to-end and build something that works reliably rather than perfectly but unsuccessfully.

---

## What This Solution Includes

This implementation includes:

- FastAPI backend service
- Vapi webhook endpoint for tool-calling voice agent requests
- SQLAlchemy async database access to Postgres/Supabase
- patient validation and normalization rules
- patient lookup, create/update APIs
- soft-delete-friendly schema design
- patient dashboard served from the same app
- structured JSON responses and consistent error envelopes
- logging of final payloads and tool webhook activity
- duplicate-safe lookup logic for phone-number matching
- support for Vapi-style camelCase and snake_case payloads
- partial info tracking for interrupted or incomplete calls
- future capability: transcript records can be stored in the database for auditing, training, and call review

---

## System Architecture

The system is intentionally structured to separate concerns:

1. Voice AI / Telephony Layer
   - A voice agent (Vapi-compatible tool-calling design) initiates patient intake through conversational prompts.
   - The assistant asks the caller for required demographic fields and optionally additional information.
   - The system uses tool calls for `check_existing_patient`, `create_patient`, and `update_patient`.

2. Backend Layer
   - FastAPI exposes:
     - the webhook endpoint for Vapi
     - REST CRUD endpoints
     - the dashboard UI
   - Business logic validates requested data, normalizes values, and writes records to the database.

3. Database Layer
   - SQLAlchemy async access to a Postgres-compatible database (Supabase Postgres in this project)
   - A `patients` table stores patient records with timestamps and soft-delete support

4. Web / Dashboard Layer
   - A lightweight static UI allows viewing patient records and can be used for local debugging and admin access

5. Observability
   - Webhook payloads and generated final responses are logged to stdout
   - Validation failures are surfaced with clear error messages
   - Future enhancement: conversation transcripts and final collected payloads can be persisted in a dedicated database table for auditing and later review

---

## High-Level Data Flow

A typical call flow looks like this:

1. Caller dials the number or the voice agent is invoked.
2. Agent greets the caller and begins a natural conversation.
3. Agent asks for required fields such as first name, last name, DOB, sex, phone number, address, city, state, and ZIP code.
4. Agent may ask for optional fields like email, insurance, emergency contact, and preferred language.
5. Agent confirms the collected information before saving.
6. Agent triggers a backend tool call to create or update the patient record.
7. Backend validates input, normalizes values, and writes to Postgres.
8. Backend returns a structured result back to Vapi.
9. Agent confirms success to the caller or explains a graceful failure.

---

## Functional Requirements from the Assessment

### Telephony and Voice Agent Requirements

The original challenge expects:

- a real dialable U.S. phone number or a practical dev/test analog
- a conversational agent, not a rigid IVR
- LLM-driven understanding of varied phrasing, corrections, and clarification
- explicit confirmation step before saving
- re-prompting for invalid values
- graceful completion after successful registration

This implementation follows that pattern by using a Vapi-compatible tool-call webhook and a well-defined backend contract.

### Patient Demographic Data Model

The system stores the standard minimum U.S. demographic dataset required for patient registration.

Required fields:

- `first_name`
- `last_name`
- `date_of_birth`
- `sex`
- `phone_number`
- `address_line_1`
- `city`
- `state`
- `zip_code`

Optional fields:

- `email`
- `address_line_2`
- `insurance_provider`
- `insurance_member_id`
- `preferred_language`
- `emergency_contact_name`
- `emergency_contact_phone`

Auto-generated system fields:

- `created_at`
- `updated_at`
- `patient_id`
- `deleted_at` (soft-delete tracking)

### Validation Rules

The backend enforces the same rules expected by the assessment:

- `first_name`: 1–50 chars, letters, spaces, apostrophes, hyphens
- `last_name`: 1–50 chars, letters, spaces, apostrophes, hyphens
- `date_of_birth`: valid date, not in the future, expected format MM/DD/YYYY in the conversational layer, normalized to ISO-safe internal handling
- `sex`: one of `Male`, `Female`, `Other`, `Decline to Answer`
- `phone_number`: valid U.S. 10-digit phone number, Normaize it in case of countrycode added.
- `email`: valid email format when provided
- `address_line_1`: required non-empty street address
- `address_line_2`: optional additional address line
- `city`: required value, 1–100 chars
- `state`: valid 2-letter U.S. state abbreviation
- `zip_code`: 5-digit or ZIP+4 format
- `insurance_provider`: optional text field
- `insurance_member_id`: optional text field
- `preferred_language`: defaults to `English`
- `emergency_contact_name`: optional text
- `emergency_contact_phone`: valid U.S. 10-digit phone number when provided

### Database and Persistence Requirements

The challenge expects persistence across server restarts and subsequent calls. This project uses a real Postgres-compatible database through Supabase/Postgres.

The schema enforces:

- UUID primary key
- required demographic fields
- validations for phone numbers, DOB, ZIP codes, and states
- updated_at trigger behavior
- soft-delete support using `deleted_at`

The project also supports duplicate detection by phone number and refuses to lose the original record by preserving the primary match.

### Future Transcript Storage (planned enhancement)

A natural next step for this system is to persist the actual call transcript and final extracted patient payload in the database for auditing, QA, and review.

Planned behavior:

- store a transcript row keyed to the patient and/or call session
- save the final patient payload as a structured JSON object after confirmation
- capture the raw phone-call transcript or summarized conversation timeline
- keep timestamps and optional call-status metadata
- support down-stream analytics, quality monitoring, and dispute review

This is not yet implemented as a production table in the current codebase, but it is a clear and appropriate extension to the existing persistence model because the backend already logs final payloads and the database is already the canonical source of truth for patient records.

---

## Live Demo

- API base URL: https://voice-agent-production-a8a4.up.railway.app/
- Phone number to call: +1 (430) 599 8472
- Webhook endpoint: https://voice-agent-production-a8a4.up.railway.app/webhook

The backend exposes the Vapi tool webhook at `/webhook`, which receives tool-call payloads from the voice assistant, processes the requested patient action, and returns the structured Vapi-compatible response object (it would not show anything on web, it is just forr the refernce)

---

## REST API

The service exposes a set of endpoints matching the assignment requirements.

### Base behavior

- All endpoints return JSON with a consistent envelope:

```json
{
  "data": { ... },
  "error": null
}
```

- HTTP status codes used include:
  - `200` for successful GET and updates
  - `201` for successful creation
  - `400` for invalid input and malformed requests
  - `404` for not found records
  - `422` for validation failures
  - `500` for server-side failures

### Endpoints

#### GET /patients

Lists all active patients. Optional filters are supported:

- `?last_name=`
- `?date_of_birth=`
- `?phone_number=`

#### GET /patients/{patient_id}

Fetches a single patient by UUID.

#### POST /patients

Creates a new patient record.

#### PUT /patients/{patient_id}

Updates an existing patient record with partial update support.

#### DELETE /patients/{patient_id}

Soft-deletes a patient record. This project does not hard-delete records.

---

## Webhook / Vapi Tool Contract

The backend accepts tool-calling payloads from a Vapi-style assistant and dispatches to the matching server-side function.

Supported tool names:

- `check_existing_patient`
- `create_patient`
- `update_patient`

### Tool behavior

#### `check_existing_patient`

- Accepts `phone_number`
- Accepts `partial_info` as a boolean
- Looks up patient by normalized phone number
- Returns a found or not_found result
- Keeps the first/primary matching record if multiple rows exist

#### `create_patient`

- Validates all required fields before writing
- Normalizes phone numbers and other field values
- If a patient with that phone number already exists, it updates the existing record instead of creating a duplicate entry
- Uses the same field names as the Vapi tool schema to preserve compatibility
- Returns status such as `created` or `updated`

#### `update_patient`

- Requires a valid `phone_number`
- Can accept any subset of fields for partial update
- Replaces only fields supplied and leaves the rest intact
- Returns a structured success or not_found error payload

### Tool Result Format

The webhook response returns structured results in the pattern expected by Vapi:

```json
{
  "results": [
    {
      "toolCallId": "...",
      "result": {
        "status": "found",
        "patient": { ... }
      }
    }
  ]
}
```

This is JSON-safe and handles UUID values correctly using `jsonable_encoder`.

---

## Data Model and Schema

The database table is implemented as a Postgres table in `schema.sql`.

### Patient table fields

| Column | Type | Notes |
| --- | --- | --- |
| patient_id | UUID | primary key, generated automatically |
| first_name | TEXT | required |
| last_name | TEXT | required |
| date_of_birth | DATE | required, cannot be future-dated |
| sex | TEXT | enum |
| phone_number | TEXT | 10-digit U.S. number |
| email | TEXT | optional |
| address_line_1 | TEXT | required |
| address_line_2 | TEXT | optional |
| city | TEXT | required |
| state | TEXT | 2-letter code |
| zip_code | TEXT | 5-digit or ZIP+4 |
| insurance_provider | TEXT | optional |
| insurance_member_id | TEXT | optional |
| preferred_language | TEXT | default `'English'` |
| partial_info | BOOLEAN | tracks incomplete or interrupted calls |
| emergency_contact_name | TEXT | optional |
| emergency_contact_phone | TEXT | optional |
| created_at | TIMESTAMPTZ | auto timestamp |
| updated_at | TIMESTAMPTZ | auto timestamp |
| deleted_at | TIMESTAMPTZ | soft delete marker |

### Indexes

- phone number lookup index
- deleted_at filter index

### Trigger

A Postgres trigger updates `updated_at` on every update so timestamps remain current automatically.

---

## Prompt / Agent-Level Requirements and Conversation Design

The challenge emphasizes prompt quality and conversational flow. In this implementation, the voice assistant is designed to behave as a human intake coordinator rather than a rigid menu.

### Prompt design principles

- ask for missing required fields one at a time if needed
- confirm collected details before save
- handle out-of-order responses gracefully
- accept natural language variations
- clarify invalid input and re-prompt specifically for the field in question
- offer optional data collection once required fields are complete

### Example of the conversational goal

The agent may say:

> “I have your name, phone number, and address. Before I save this, can you confirm that the information is correct?”

If the caller says something like:

> “Actually, my date of birth is 04/03/1989.”

The agent should update the field and continue without treating the whole call as failed.

### Vapi assistant prompt (exact prompt)

```text
Speak first message: Thanks for calling CareCloud. This is Will, your patient registration assistant. I hope you are doing well. 


# IDENTITY

You are Will, a friendly and efficient patient intake coordinator for a medical
clinic, speaking with callers over the phone. You are not a chatbot reading a
script. You are a real intake coordinator who happens to work by phone: warm,
patient, brisk when things are going smoothly, and unflustered when they are not.

# VOICE AND STYLE RULES

- Speak in short, natural sentences. Avoid long lists read aloud back to back.
- Never say "field," "required field," "database," "record object," or any
  system language to the caller. Say "your last name," "your address," etc.
- Acknowledge what the caller says before moving on ("Got it," "Perfect,"
  "Thanks") instead of jumping straight to the next question.
- Ask one thing at a time. Do not stack two questions in one turn unless they
  are tightly related (city and state can be asked together; date of birth
  should always be its own question).
- If the caller goes off-script, answers two questions in one sentence, gives
  information out of order, or interrupts you, roll with it. Do not force them
  back into your exact question order. Track what you already have and only
  ask for what is still missing.
- If the caller corrects themselves ("actually, my last name is spelled
  D-A-V-I-S, not D-A-V-I-E-S"), immediately update that field, read the new
  value back once, and continue. Do not re-litigate the whole conversation.
- If the caller says "start over," "can we restart," or similar, confirm once
  ("Sure, let's start fresh. I'll clear what we have and take it from the
  top.") then discard all collected fields for this call and begin again from
  the phone number.
- If the caller says "hold on" or goes silent mid-sentence, wait. If there is
  a long pause after a question, gently re-ask it rather than assuming an
  answer.

# CALL FLOW

#IMPORTANT: WHENEVER YOU ARE GOING TO USE A TOOL OR PERFORM ANY ACTION TELL THE USER SOMETHING LIKE 'LET ME CHECK' OR ETC.. DO NOT STATY SILENT AND MOVE DIRECTLY TO THE TOOL USING OR ELSE THE USER WILL INTERUPT YOU OR CUT THE CALL.

1. Greet the caller (handled by the first message). Wait for the reply and after a reply and ask for their phone
   number, "Before we get started, can I get your phone number so I can check if we already have a record for you?". Specify that user does not need to add the country code, if he/she does and the number exceeds 10 digits, remove the first digit also do not include any sign, like +, if the user mentions it as well. You yourself too shouldnt ask for country code.
2. Call the `check_existing_patient` tool with the phone number. It will return either a json with data retrieved (with status that if the information was partial or complete) or with message saying no data found.
   - If a match is found: tell the caller "It looks like we already have a
     record for [First Name] [Last Name]. Would you like to update your
     information instead?" Branch accordingly.
     For updates, ask only what they want to change, then use `update_patient`.
   - If no match: proceed to collect a new registration.
3. Collect REQUIRED fields, in this order, one at a time:
   first name, last name, date of birth, sex, phone number (skip if already
   given), email is NOT required so skip unless offering optional info later,
   address line 1, city, state, zip code.
4. After required fields are collected, offer optional information once,
   in a single line: "I can also collect your insurance information, an
   emergency contact, and your preferred language if you'd like to add any of
   that now. Want to provide any of it, or should we skip it?"
   - If yes, ask only for the specific optional items they agree to provide:
     email, address line 2, insurance provider, insurance member ID,
     preferred language, emergency contact name, emergency contact phone.
   - If no, move straight to confirmation.
5. CONFIRMATION (mandatory, never skip): Read back every collected field in a
   natural sentence, not a robotic list, e.g.:
   "Let me read that back to make sure I've got it right: [First] [Last],
   born [Month Day, Year], [Sex]. Reaching you at [phone number]. Your
   address is [address line 1][, address line 2 if given], [City], [State]
   [Zip]. [Include optional fields only if provided.] Does all of that sound
   correct?"
   - If the caller confirms, proceed to save.
   - If the caller corrects anything, update that field only, read back the
     corrected field, and ask "Anything else to fix?" before saving.
6. Call `create_patient` (or `update_patient`) with the confirmed data.
   - On success: "You're all set, [First Name]. Thanks for calling, and we'll
     see you soon." Then end the call.
   - On failure: apologize once, briefly explain there was a technical issue
     saving the record, and offer to try again immediately: "I'm sorry, I hit
     a snag saving that. Let me try again." Retry the tool call once. If it
     fails a second time, tell the caller a staff member will follow up
     manually and take down their callback number if not already collected,
     then end the call gracefully. Never leave the caller with silence after
     a failed save.
7. End the call using the end-call tool once the caller has what they need
   and there is nothing left to collect.

8. If the call gets cut mid conversation or any issue occurs and you remain with partial information, set 'partial_info' from the tool 'create_pateint' to 'True'.

9. Make sure the date of birth is not in the futurer. And confirm it by repeating what user said.

# FIELD VALIDATION RULES (validate before accepting an answer)

first_name / last_name:
  - Letters, hyphens, and apostrophes only, 1-50 characters.
  - If the caller gives something that doesn't sound like a name (numbers,
    a full sentence), ask them to repeat just the name.

date_of_birth:
  - Must be a real calendar date and cannot be in the future.
  - If the caller gives an invalid or future date, say: "That date doesn't
    look quite right, can you say your date of birth again, month, day, and
    year?" Do not guess or auto-correct.

sex:
  - Must map to one of: Male, Female, Other, Decline to Answer.
  - If the caller gives an ambiguous answer, ask them to pick from those four
    options phrased naturally: "How would you like that recorded: male,
    female, other, or would you prefer not to say?"

phone_number / emergency_contact_phone:
  - Must be a 10-digit U.S. number (area code plus number, extra formatting
    characters okay to strip).
  - If too short, too long, or contains letters, ask: "That number didn't
    come through quite right, could you say it again in the standard
    ten-digit format?"

email (optional):
  - Standard email format if provided. If clearly malformed, ask them to
    repeat it; if they can't get it to register after two tries, offer to
    skip it since it's optional.

address_line_1 / city:
  - Free text, but must be non-empty. Re-prompt once on empty/garbled input.

state:
  - Must resolve to a valid 2-letter U.S. state abbreviation (accept full
    state names and convert, e.g. "California" to "CA").

zip_code:
  - Must be 5 digits or ZIP+4 format. If it doesn't match, ask them to repeat
    just the zip code.

General rule for ALL validation failures: re-prompt specifically for the
field that failed. Do not restart the whole conversation over one bad field,
and do not silently accept invalid data to keep things moving.

# TOOL USE

You have access to the following tools, which call the backend REST API.
Always use tools to read or write patient data; never claim to have saved
something without a successful tool response.

- check_existing_patient(phone_number): looks up a patient by phone number.
  Call this as soon as you have the phone number, before collecting anything
  else.
- create_patient(fields...): saves a new patient record. Call only after the
  caller has explicitly confirmed the read-back.
- update_patient(patient_id, fields...): updates an existing patient record
  for return callers. Call only after the caller confirms which fields to
  change and the corrected values.

If a tool call errors or times out, do not tell the caller a technical error
code. Translate it into plain language per the "Call Completion" failure
handling above.

# LANGUAGE

If the caller says "Hablo español" or otherwise indicates they'd prefer
Spanish, switch your responses to natural, conversational Spanish for the
remainder of the call, using the same flow and validation rules. If you are
not confident continuing accurately in the requested language, apologize in
that language and offer to have a Spanish-speaking staff member call back
instead of guessing.

# THINGS TO NEVER DO

- Never read out internal field names, JSON, or tool names to the caller.
- Never save a record without an explicit verbal confirmation from the
  caller.
- Never invent or assume a value for a required field the caller hasn't
  given you.
- Never end the call before either completing registration, completing an
  update, or clearly telling the caller what happens next if something
  failed.

#IMPORTANT: ALWAY SPELL BACK THE NAME AND PHONE NUMBER BEFORE THE FINAL WRITE.
```

---

## Edge Cases and Resilience Behavior

The challenge specifically calls out several failure and recovery scenarios. These are important design notes for the project and are implemented at multiple layers.

### 1) Invalid date of birth

If the caller says an invalid DOB such as a future date, an obviously malformed date, or a date that is not a real calendar date, the system handles this in three places:

- prompt/agent layer: the assistant explicitly re-asks for the date in a conversational way and may say something like “I didn’t catch that date correctly. Can you repeat your date of birth?”
- backend validation layer: `normalize_date_of_birth` rejects impossible or future dates
- database layer: the `date_of_birth` column constraint ensures the value cannot be future-dated

This prevents bad data from reaching storage.

### 2) Telephony connection drops mid-call

If the call drops before the patient intake is complete, the app uses a `partial_info` boolean as the key mechanism for representing incomplete or interrupted collection.

The intended behavior is:

- if the call is disrupted or cut off before the final confirmation, the system marks the patient record or in-memory context as `partial_info = true`
- the agent or downstream system can then ask for only the missing details on the next call
- the existing data is not lost if the caller resumes in a follow-up interaction
- partial_info distinguishes between a full saved patient profile and a half-collected one

This is the intended partial information theory for interrupted or incomplete calls.

### 3) Database write fails

If the database write fails, the system does not silently fail.

The design behavior is:

- return an explicit error result from the backend tool or API call
- surface the failure to the agent as a clear error message
- tell the caller: the write could not be completed and they should contact staff or try again

The user-facing guidance is effectively:

> “I can’t save that right now. I’ll have someone get in touch with you.”

This ensures the caller is not left in silence and the system has a clear recovery path.

### 4) Caller wants to start over mid-conversation

This is a known limitation in the current implementation.

The current flow does not support a robust mid-conversation restart with full context restoration. If the caller interrupts and begins a fresh conversation, the system can lose the current in-flight context, and the agent may restart the intake flow from scratch.

This is documented as a limitation because the platform does not currently maintain a highly resilient state machine for arbitrary mid-call resets or session resumption unless the telephony provider and app layer are extended to support it.

---

## Duplicate Handling Behavior

The system is designed to recognize returning callers by phone number and avoid creating duplicate patient entries.

Behavior:

- If a patient record already exists for the same phone number, the system selects the primary existing record
- It updates that matching record with the new information
- It does not delete any existing record
- It avoids creating duplicate entries
- Update logic is keyed off the existing patient phone number as the canonical lookup key, so the current record is matched and updated by phone number rather than by a separate duplicate-creation path

This is intentionally conservative and respects the requirement that the system keep the original record intact while updating it with new information rather than deleting or destroying old data.

---

## Trade-offs: Accuracy vs Latency vs Cost

The system is intentionally designed for a practical balance between conversational quality, speed, and operating cost.

- Accuracy vs latency: more careful confirmation loops and stricter validation improve correctness but create a slightly longer call flow.
- Accuracy vs cost: higher-quality LLM behavior and more explicit validation adds overhead, but the cost difference is modest rather than dramatic.
- In this project, the cost trade-off is estimated to be approximately $0.03 per minute lower when accuracy is intentionally reduced or when a lighter-weight model configuration is chosen.
- The design goal is to stay close to the accuracy threshold required for a good patient intake experience without adding unnecessary latency or unnecessary model cost.
- In a clinical intake context, correctness should still win if the difference is small; the agent must not silently accept invalid data just to speed up or cheaply complete the call.

This is a real product trade-off, not a hidden shortcut: we choose a reliable, structured intake experience over maximizing cheapness at the expense of patient data quality.

---

## Validation and Normalization Behavior

The app validates and normalizes incoming data before using it.

Examples:

- phone numbers are stripped to numeric digits and a leading `1` is dropped if present and the total length is >10
- state values are normalized to 2-letter uppercase codes
- date strings are normalized into valid ISO-style internal handling
- optional string fields are trimmed and treated as empty when blank
- `partial_info` is normalized to a real boolean

This normalization is done both in the validation layer and as a canonicalization step for Vapi tool arguments so the same backend logic supports both `snake_case` and `camelCase` field names.

---

## Observability and Logging

The system logs several important pieces of information:

- incoming webhook payloads
- tool call names and arguments
- tool execution results
- final webhook response payloads
- validation and server errors

This ensures a reviewer can inspect the runtime behavior and confirm the exact data being processed at each step.

---

## Security Notes

The project follows basic security expectations for a challenge app:

- API keys and secrets are stored in environment variables, not in code
- inputs are sanitized and validated on the server side
- basic CORS settings are enabled for testing and browser access
- no real patient data should be used in a production environment

---

## Tech Stack

This implementation uses the following stack:

- Python
- FastAPI
- SQLAlchemy / async Postgres
- Supabase Postgres database
- Pydantic-style validation conventions and custom validation logic
- Vapi-compatible webhook design
- static HTML dashboard
- Uvicorn for serving the app

This matches the challenge’s guidance that a Vapi-style telephony layer plus a Python FastAPI backend is a pragmatic, fast path to a working challenge submission.

---

## Project Structure

```text
carecloud/
├── .env.example
├── .env
├── README.md
├── db.py
├── main.py
├── requirements.txt
├── schema.sql
├── tools.py
├── validation.py
├── static/
│   └── index.html
├── tests/
│   └── test_api_contract.py
├── Voice AI Agent Coding Challenge - New.pdf
└── .gitignore
```

---

## Setup Instructions

### 1) Clone the Repository

```bash
git clone <repo-url>
cd carecloud
```

### 2) Create a Virtual Environment

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3) Install Dependencies

```bash
pip install -r requirements.txt
```

### 4) Set Environment Variables

Copy `.env.example` to `.env` and update the values.

Example:

```env
SUPABASE_URL=postgresql://postgres:your_password@db.your-project-ref.supabase.co:5432/postgres
VAPI_API_KEY=your_vapi_api_key_here
VAPI_ASSISTANT_ID=your_vapi_assistant_id_here
PORT=8000
```

### 5) Create the Database Schema

Run the contents of `schema.sql` in your Supabase SQL editor or Postgres-compatible database.

### 6) Start the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Then visit:

- `http://localhost:8000/`
- `http://localhost:8000/ui`
- `http://localhost:8000/patients`

---

## Local Development Notes

The app has been built to run both locally and on a hosted platform Railway.

Recommended local workflow:

- run the FastAPI service locally with uvicorn
- use the dashboard for manual checks
- use test client or direct API calls for validation
- confirm that `partial_info` toggles work as expected when a call is interrupted

---

## Deployment Notes

The challenge expects a live demo at the time of review. This project is designed to be compatible with a standard hosted deployment model such as:

- Railway
- Render
- Fly.io
- Replit
- Docker-based hosting
- any provider with a public web endpoint and Postgres availability

For deployment, the same environment variables as local development should be configured in the provider dashboard.

---

## Testing

The project includes contract tests covering the API and payload behavior.

Example test run:

```bash
.\.venv\Scripts\python.exe -m pytest -q tests/test_api_contract.py
```

Current tests verify:

- API response envelope behavior
- validation and 422 handling
- webhook response structure
- UUID-safe serialization
- phone normalization
- Vapi field-name compatibility
- duplicate handling semantics without deleting records

---

## Known Limitations and Trade-Offs

The challenge is intentionally time-boxed. This project acknowledges a few limitations:

1. Mid-conversation restart is not fully resilient.
   - If the caller wants to start over mid-conversation, the current implementation can lose context if the session is interrupted or restarted in the middle of an ongoing flow.
   - This is a known limitation of the current agent/session handling.
   - In practice, a true restart capability requires more session-state handling, a clear reset flow, and a stronger operational contract for the telephony layer.

2. Accuracy vs latency vs cost remains a live product decision.
   - Stronger validation and more careful confirmation improve accuracy, but they also increase the call time and in some cases the model cost.
   - Lower-cost or lower-latency settings can reduce cost by about $0.03 per minute when accuracy is intentionally sacrificed, but the trade-off is not ideal for patient intake quality.

3. This is not a healthcare system.
   - The project is intentionally a technical assessment implementation and not a HIPAA-compliant production system.

---

## What We Are Looking For in This Project

This repo is built around the real intent of the challenge:

- integrate multiple systems under time pressure
- make smart trade-offs
- produce working behavior, not a theoretical architecture
- ensure the voice agent and backend stay aligned
- document execution, edge cases, limitations, and validation clearly

This implementation demonstrates a working backend contract, database access, validation, and voice-agent tool orchestration in a compact, understandable codebase.

---

## Summary

This project satisfies the main challenge requirements by providing:

- a patient registration workflow
- a persistent database-backed model
- a webhook tool interface compatible with Vapi-like voice agents
- API endpoints for listing and interacting with patient data
- validation and error handling for failed calls and bad inputs
- explicit handling for partial information and interrupted call flows
- a documented set of known limitations and edge-case behaviors

The system emphasizes practical working behavior over over-engineering, which matches the spirit of the challenge.

---

## Final Notes

The challenge is not about building a production healthcare system. It is about showing that the engineer can:

- integrate LLM-powered voice orchestration
- connect that orchestration to a real database-backed service
- validate and normalize user data
- reason about failures and edge conditions
- produce clean, readable, explainable code and documentation

This README documents those points clearly and intentionally.
