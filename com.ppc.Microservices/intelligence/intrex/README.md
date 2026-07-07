# Intrex

## Documentation

Real Time API V1 - https://intrexis.atlassian.net/wiki/external/NTI0ODM4Y2RlMzMxNDJhYjhiNzdjNzQzMDg0MzI0Mjg

REST API V1 - https://intrexis.atlassian.net/wiki/external/MTc1NTE5YjY4MTMzNDJjMjlmZDA5YWQ5NTM0NmJiNWY

## Tests and Samples

To Test, add the `com.ppc.Microservices/intelligence/intrex` microservice to your bot's `structure.py`.

### Unit Tests

See `tests/test_intrex.py`.

### Live Tests

See `tools/intrex_run_test.py`.

### Intrex Sample Data

Execute using `./botengine --playback "com.ppc.Microservices/intelligence/intrex/_.json" --run com.ppc.ExampleBot`.

## Event Stream

### Intrex Events

**Address**: `intrex_event`

The Intrex (Rythmos) Real Time API delivers alert events on this data stream. Each event carries an
`eventType` (the `AlertType` enum) and an event object. See `docs/Real Time API V1 - Confluence.pdf` for
the full enumeration; `event_types.py` mirrors it.

#### Payload

The handler consumes the flat `intrex_event` feed (the fields published to the bot), for example a staff
deactivation:

```json
{
  "eventType": 2001,
  "type": "alert",
  "deviceId": "1404890704",
  "deactivationOptionId": 235,
  "deactivationOptionName": "Emergency ",
  "deactivationOptionFallType": null
}
```

* `eventType` — the `AlertType` enum value (see ranges below).
* `deviceId` — Intrex/Rythmos device id, resolved to the local device to target the correct conversation.
* `deactivationOption*` — the deactivation reason selected by staff (deactivations only).
  `deactivationOptionFallType` is a numeric fall classification: `0` = no fall, `1` = soft fall, `2` = hard fall.

#### Lifecycle and event-type ranges

| Stage | `eventType` | Delivery | Handling |
|-------|-------------|----------|----------|
| Activation | `1`–`37`, `1001`–`1007` | Device measurement (`buttonStatus`, `fallStatus`, …) | An alert/conversation is raised by the owning microservice (e.g. `care/mpers`). Ignored on this stream. |
| Accept by staff | `3001`–`3026` (`*AcceptedByStaff`) | `intrex_event` | Notifies the active alert's participants ("Staff is responding") via `conversation.accept_conversation`. |
| Deactivation by staff | `2001`–`2026` (`*DeactivationFromRythmos`) | `intrex_event` | Resolves the active alert via `conversation.resolve_conversation`, classified real vs false alarm. |

The accept range is a one-for-one `+1000` mirror of the deactivation range (e.g. `ButtonPressDeactivationFromRythmos=2001` ↔ `ButtonPressAcceptedByStaff=3001`).

#### Conversation signals

Because alert conversations stack and run concurrently, accept/resolve are targeted by the originating
`device_id`. Two location-scoped signals (in `signals/conversation.py`) act on the matching conversation —
whether focused or queued in a backlog — without the caller owning the conversation object:

* `conversation.accept_conversation(botengine, location_object, device_id=..., message=...)` — notifies the
  active alert's participants. If the alert has a labeling follow-up enabled, accepting also resolves the
  current conversation so the labeling conversation can begin.
* `conversation.resolve_conversation(botengine, location_object, device_id=..., label=...)` — resolves the
  active alert.

`label` is a `ConversationType.CONVERSATION_LABELING_OPTION_*` value. When the alert has a chained labeling
conversation, resolving with a label drives that labeling step (delivering `SIGNAL_TYPE_LABELED` with the
label) so the owning microservice applies the outcome — e.g. for a fall, mapping the label to a
`FallConfirmation` and keeping false positives out of the falls trend. A false-alarm label (`EXPECTED`,
`FALSE_POSITIVE`, `OTHER_PARTY`) otherwise resolves through the false-alarm path
(`SIGNAL_TYPE_CONVERSATION_FALSEALARM`).

#### Deactivation classification (real vs false alarm)

Each staff deactivation is classified into `"real"` / `"false_alarm"`:

* **Fall alerts** use the numeric `deactivationOptionFallType` directly: `0` (no fall) → false alarm, `> 0`
  (soft/hard fall) → real.
* **All other alerts** look up the normalized `deactivationOptionName` in a configurable mapping, resolved
  with precedence:
  1. Organization property `INTREX_DEACTIVATION_OPTIONS`
  2. Bot bundle domain property `INTREX_DEACTIVATION_OPTIONS` (`domain.py`)
  3. Service default `DEFAULT_INTREX_DEACTIVATION_OPTIONS` in `location_intrex_microservice.py`

Unmapped options default to a real, attended alert. A false-alarm deactivation resolves the conversation
through the false-alarm path (`SIGNAL_TYPE_CONVERSATION_FALSEALARM`), which the owning microservice uses to
**keep the false positive out of existing trend metrics** (e.g. the falls trend) — no Intrex-specific trend
is created.

