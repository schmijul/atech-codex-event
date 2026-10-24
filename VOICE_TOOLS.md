# Voice intent tools

Scope: function tools, backend association/actions, and OpenAI tool calling.
The dashboard UI and device firmware are owned elsewhere and are unchanged here.

`voice_tools.py` exports `TOOLS` (Chat Completions function definitions) and
`execute_tool(database, name, arguments, request_id, patient_id=1)`.
`dashboard.py` hosts these actions alongside the existing database API on port
8000. Its HTML, CSS, and JavaScript match the pulled version exactly.

| Function | Arguments | Result |
| --- | --- | --- |
| `request_help` | `details`, `urgent` | Records an assistance request and urgency. Does not contact staff or emergency services. |
| `request_floor_activity` | `activity` | Looks up the requester's registered floor, finds other residents there, and queues one invitation per neighbor. |
| `choose_lunch` | `choice`, `details` | Records vegetarian, meat, vegan, fish, or other. Does not send a kitchen order. |
| `medication_reminder` | `action`, `time`, `timezone` | Reads, sets, or disables the existing dashboard schedule. Reads the last meds-button confirmation. |

`patient_id` comes from the application/device context, never from the model's
function arguments. The model selects the tool and interprets the spoken request;
the backend validates parameters and performs the association/action.

Medication settings/history currently belong to Patient 1. Other resident IDs
cannot use that medication tool. Speech never inserts a medication confirmation;
the existing button/API remains responsible for that. For `status` or `disable`,
send empty `time` and `timezone`. For `set`, use HH:MM and an IANA timezone.

## Backend contract for the dashboard/device implementers

- `GET /api/voice/tools`: function definitions.
- `POST /api/voice/tools/NAME`: JSON `request_id`, `arguments`, optional
  `patient_id` (defaults to 1). Returns the action result.
- `GET /api/voice/requests`: latest 100 recognized requests, arguments, resident
  IDs, and results for the dashboard to display.
- `GET /api/patients`: residents with `id`, `name`, and `floor`.
- `POST /api/patients`: save `{id, name, floor}`; use `id: null` for a new resident.
- `GET /api/social/invitations`: latest 100 invitations with sender, recipient,
  activity, and `played_at_utc` for dashboard display.
- `GET /api/patients/ID/invitations`: recipient inbox.
- `GET /api/patients/ID/invitations/next`: oldest pending invitation, or
  `{"invitation": null}`. Reading does not mark it played.
- `POST /api/patients/ID/invitations/INVITATION_ID/played`: JSON `{}` to acknowledge
  completed playback. Only the matching recipient ID can acknowledge it.
- `POST /api/social/requests/ID/dispatch`: JSON `{}` to retry a request that was
  blocked by missing floor/neighbors after the directory is configured.

The receiving-device integration should read its next invitation, speak it, then
acknowledge playback. This branch supplies the queue and acknowledgement API;
it does not add polling, speech playback, or new dashboard components.

The existing database has no resident directory. Startup adds `patients`,
`voice_requests`, and `social_invitations`; only the existing Patient 1 is
initialized, with no invented floor or neighbors. Add real directory data before
sending invitations. Floor labels are trimmed and matched case-insensitively;
`2` and `second floor` are different labels. Social results are
`invitations_created`, `needs_floor`, or `no_neighbors`.

Actions and invitations are saved in one transaction. The same `request_id`,
resident, and arguments return the saved result without repeating effects.
Changed arguments/resident return 400; database errors return 503. A fresh ID is
a new request. The existing trusted-LAN API remains unauthenticated.

## OpenAI voice integration

`voice_assistant.py` is the host bridge from `origin/codex/microphone-input` at
`dc19b18`, extended with the four tools and a bounded tool/result loop. It uses
`gpt-audio-1.5`, the existing PCM protocol, and `system_prompt.md`. Six complete
turns per device/resident provide context for lunch answers; context expires
after ten minutes or process restart. Unclear or negated action requests should
not write data. Tool failures are returned to the model without claiming success.

Run the backend with `python3 dashboard.py` and the voice bridge with
`python3 voice_assistant.py`. The bridge reads `OPENAI_API_KEY` from the environment
or ignored `.env`. Optional settings are `VOICE_BACKEND_URL` (default
`http://127.0.0.1:8000`), `VOICE_TIMEZONE` (default `Europe/Berlin`), and
`VOICE_PATIENT_ID` (default `1`). The `/api/voice` PCM endpoint accepts
`X-Patient-ID` for device-specific context. No credentials are committed.

Verify with `python3 -m unittest -v test_voice_tools.py`. Tests use real HTTP
servers and temporary databases, with mocked OpenAI audio. A live synthesized
speech check returned HTTP 401 (`invalid_api_key`), so live recognition remains
unverified until a working key is configured.

Official OpenAI references:
[audio in Chat Completions](https://developers.openai.com/api/docs/guides/audio-chat-completions),
[GPT-Audio-1.5](https://developers.openai.com/api/docs/models/gpt-audio-1.5),
and [function calling](https://developers.openai.com/api/docs/guides/function-calling).
