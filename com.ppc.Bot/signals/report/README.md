# Report Signal Module

## Why This Module Exists

This module provides the centralized event-driven architecture for all report generation
in the bot ecosystem. It replaces the legacy `signals/dailyreport.py` module with a cleaner,
event-type-based approach that eliminates the confusion of separate `section_id` and `event_type`
concepts.

## What It Does

- Defines comprehensive event type constants for all observable events in a home
- Provides an `EVENT_TYPE_SCHEMA` that maps event type prefixes to presentation properties
- Offers a simple `add_event()` function that microservices use to log events
- Automatically routes events to organizational bots when appropriate
- Supports multiple report periods (daily, 24h, 12h, weekly, monthly)

## How It Works

1. Microservices call `report.add_event()` with an `event_type` and `comment`
2. The `event_type` prefix (e.g., `"sleep"` from `"sleep.wakeup"`) is looked up in `EVENT_TYPE_SCHEMA`
3. Presentation properties (`title`, `icon`, `color`, `weight`) are automatically applied
4. Events are stored in a local cache for later synthesis by LLM
5. At report generation time, events are grouped by prefix and synthesized into coherent narratives

---

## Organizational Reporting Architecture

Organizational reports use a **Hybrid AI-First Schema** that balances programmatic routing
with LLM-powered interpretation. This enables an "AI Chief of Staff" to intelligently
triage, synthesize, and route intelligence from hundreds of locations to the right people.

### Core Design Principles

1. **Multi-Dimensional Prioritization**
   - Criticality: How urgent is this? (`critical` | `warning` | `info`)
   - Report Type: What domain? (`stability` | `bathroom` | `social_isolation` | `infrastructure`)
   - Category: Higher-level grouping (`wellness` | `operations` | `it`)
   - Sentiment: Good news or bad? (`concern` | `resolution` | `update` | `celebration`)

2. **Minimal Required Fields** (for programmatic routing)
   - Just enough structure to route reports without LLM
   - Enables simple filtering by `report_type`, `criticality`, `location`

3. **Flexible Natural Language Content** (for LLM interpretation)
   - Summary, concerns, and context in human-readable format
   - LLM understands nuance, compares across locations, synthesizes insights
   - Extensible: Add new concern types without schema migrations

4. **State Tracking for Lifecycle**
   - Track bad news → resolution lifecycle
   - Celebrate improvements after concerns
   - Share daily summaries even when no problems exist

5. **Location Identity**
   - `location_id`: Immutable identifier for grouping
   - `location_name`: Mutable display name (user can rename)

6. **Separation of Concerns**
   - Location bots categorize (`report_type`)
   - Organizational bots route (based on admin preferences)
   - No hard-coded audiences at location level

---

## Organizational Report Schema (`send_org_report`)

### Required Fields (for routing — programmatic access)

**`location_id`** `int`
Immutable identifier for this location. Used to group reports over time.

**`location_name`** `str`
Current display name for the location. User can rename this.
Example: `"Casa de Mossa"`, `"Grandma's House"`, `"Ilene Johnson"`

**`timestamp_ms`** `int`
Unix timestamp in milliseconds when this report was generated.

**`priority`** `str`
Overall urgency level for triage. One of:
- `"critical"` — Requires immediate attention (within 24 hours)
- `"warning"` — Requires attention soon (within 1-3 days)
- `"info"` — Informational, no immediate action required

**`report_type`** `str`
Category of report for organizational routing. Examples:
- `"stability"` — Fall risk, stability score concerns
- `"bathroom"` — Bathroom visit patterns (UTI indicators)
- `"social_isolation"` — Extended periods without leaving home
- `"infrastructure"` — Device offline, connectivity issues
- `"daily_summary"` — Routine daily report summary
- `"weekly_summary"` — Weekly trend report summary

The organizational bot maps `report_type` to interested admins:
- Admins configure: `"I'm interested in [stability, bathroom, sleep]"`
- Reports are routed to matching admins automatically
- No hard-coded audiences at location level
- Note: This is not an exhaustive enum — new types can be added as needed.

**`sentiment`** `str`
Nature of this report. One of:
- `"concern"` — New problem detected
- `"resolution"` — Previous problem has been resolved
- `"update"` — Status update on ongoing issue
- `"celebration"` — Positive trend worth celebrating
- `"summary"` — Daily/weekly summary (no specific concern)

**`report_id`** `str` *(optional but recommended)*
Unique identifier for this specific report instance.
Used to track concern → resolution lifecycle.
Example: `"stability_concern_755735_1767239825686"`

### Recommended Fields (for LLM interpretation — natural language)

**`summary`** `str`
One-sentence executive summary of this report.
Write as if briefing a human chief of staff.

Examples:
```
"Stability score dropped to 58% - fall event and declining mobility"
"Gateway offline for 12 hours - residents unable to receive alerts"
"Wellness score improved to 85% - mobility and sleep both trending up"
```

**`concerns`** `list[str]`
Specific issues in natural language, presented as bullet points.
Each concern should be a complete, self-contained statement.

Example:
```json
[
    "Fall at 3:24 PM on Friday January 1 lasting 8 minutes",
    "Mobility below average for 4 consecutive days (scores: 45%, 42%, 38%, 40%)",
    "5 nighttime bathroom visits on Thursday (baseline: 2 visits)"
]
```

**`context`** `dict`
Flexible object with supporting data for LLM interpretation.
No strict schema — include whatever helps explain the situation.
Can include scores, trends, historical comparisons, etc.

Example:
```json
{
    "stability_score_current": 58,
    "stability_score_last_week": 78,
    "rate_of_decline": "rapid",
    "contributing_factors": {
        "falls": "45% weight, 1 event with 8-minute duration",
        "mobility": "15% weight, 4 consecutive days below average"
    }
}
```

**`recommended_action`** `str`
Suggested next steps for caregiving staff or administrators.
Be specific and actionable.

Examples:
```
"Immediate wellness check within 24 hours. Evaluate fall risk interventions."
"Contact resident or care coordinator to assess need for medical evaluation."
"Dispatch technician to check gateway connectivity and replace if needed."
```

### Optional Fields (for programmatic access without LLM)

**`severity_rank`** `float` (0–100)
Numerical score for sorting reports by severity without LLM.
Higher = more severe. Can be based on wellness score, stability score, etc.
Example: `92` (critical), `68` (warning), `25` (info)

**`days_active`** `int`
How many days this concern has been active.
Useful for filtering chronic vs. acute issues.

**`scores`** `dict`
Any relevant numerical scores for trend analysis.
Example:
```json
{
    "wellness_score": 62,
    "stability_score": 58,
    "mobility_score": 42,
    "sleep_score": 75
}
```

**`previous_report_id`** `str`
If this is a resolution/update, reference the original concern report.
Enables lifecycle tracking: concern → resolution.

---

## Example Organizational Reports

### Example 1: Stability Concern (Wellness Domain, Critical)

```json
{
    "location_id": 755735,
    "location_name": "Casa de Mossa",
    "timestamp_ms": 1767239825686,
    "priority": "critical",
    "report_type": "stability",
    "sentiment": "concern",
    "report_id": "stability_concern_755735_1767239825686",

    "summary": "Stability score dropped to 58% - fall event and declining mobility",
    "concerns": [
        "Fall at 3:24 PM on Friday January 1 lasting 8 minutes",
        "Mobility below average for 4 consecutive days (scores: 45%, 42%, 38%, 40%)",
        "5 nighttime bathroom visits on Thursday (baseline: 2 visits)"
    ],
    "context": {
        "stability_score_current": 58,
        "stability_score_last_week": 78,
        "delta": -20,
        "rate_of_decline": "rapid",
        "contributing_factors": {
            "falls": "45% weight, 1 event with 8-minute duration",
            "mobility": "15% weight, 4 consecutive days below average",
            "sleep_quality": "20% weight, elevated nighttime bathroom visits"
        }
    },
    "recommended_action": "Immediate wellness check within 24 hours. Evaluate fall risk interventions.",

    "severity_rank": 92,
    "days_active": 4,
    "scores": {
        "stability_score": 58,
        "mobility_score": 42,
        "wellness_score": 65
    }
}
```

### Example 2: Infrastructure Alert (Operations Domain, Critical)

```json
{
    "location_id": 755999,
    "location_name": "Grandma's House",
    "timestamp_ms": 1767240000000,
    "priority": "critical",
    "report_type": "infrastructure",
    "sentiment": "concern",
    "report_id": "infrastructure_concern_755999_1767240000000",

    "summary": "Gateway offline for 12 hours - residents unable to receive alerts",
    "concerns": [
        "Gateway 'Smart Home Center' went offline at 2:00 AM on Friday January 1",
        "12 hours without connectivity as of 2:00 PM",
        "4 other devices also offline (Entry Sensor, Motion Sensor x2, Radar)"
    ],
    "context": {
        "device_id": "ABC123",
        "device_description": "Smart Home Center",
        "offline_since_ms": 1767196800000,
        "offline_duration_hours": 12,
        "affected_devices": 4,
        "last_known_signal_strength": -85,
        "likely_cause": "Power outage or internet connectivity loss"
    },
    "recommended_action": "Dispatch technician to check gateway connectivity. Verify power and internet. Replace gateway if hardware failure.",

    "severity_rank": 95,
    "days_active": 1
}
```

### Example 3: Stability Resolution (Good News!)

```json
{
    "location_id": 755735,
    "location_name": "Casa de Mossa",
    "timestamp_ms": 1767326400000,
    "priority": "info",
    "report_type": "stability",
    "sentiment": "resolution",
    "report_id": "stability_resolution_755735_1767326400000",
    "previous_report_id": "stability_concern_755735_1767239825686",

    "summary": "Stability score improved to 82% - mobility returning to normal",
    "concerns": [
        "No new falls in the past 3 days",
        "Mobility score improved to 68% (was 42%)",
        "Nighttime bathroom visits normalized to 2-3 per night"
    ],
    "context": {
        "stability_score_current": 82,
        "stability_score_last_week": 58,
        "delta": 24,
        "improvement_rate": "rapid",
        "intervention_effectiveness": "Wellness check on Tuesday appeared to help"
    },
    "recommended_action": "Continue monitoring. No immediate action required.",

    "severity_rank": 18,
    "scores": {
        "stability_score": 82,
        "mobility_score": 68,
        "wellness_score": 78
    }
}
```

### Example 4: Daily Summary (Always Something to Talk About)

```json
{
    "location_id": 755888,
    "location_name": "Serenity Place",
    "timestamp_ms": 1767260400000,
    "priority": "info",
    "report_type": "daily_summary",
    "sentiment": "summary",
    "report_id": "daily_summary_755888_1767260400000",

    "summary": "All systems operating normally - resident had active and social day",
    "concerns": [
        "Left home at 10:30 AM and returned at 2:45 PM (4.3 hour outing)",
        "Sleep quality excellent (8.2 hours, minimal interruptions)",
        "Mobility above average (75% score)",
        "All devices online and functioning"
    ],
    "context": {
        "wellness_score": 88,
        "stability_score": 91,
        "mobility_score": 75,
        "sleep_score": 89,
        "social_score": 82,
        "daily_report_llm_summary": "Residents had an active and social day yesterday. They left home mid-morning for a 4-hour outing, suggesting healthy social engagement. Sleep quality was excellent with 8.2 hours of rest and minimal interruptions. Mobility remained above average with good activity distribution throughout the day. All monitoring systems are functioning properly."
    },
    "recommended_action": "No action required. Continue routine monitoring.",

    "severity_rank": 12,
    "scores": {
        "wellness_score": 88,
        "stability_score": 91
    }
}
```

---

## Admin Configuration and Routing

Organizational administrators configure their interests at the org level.
The org bot routes reports based on `report_type` preferences, not hard-coded audiences.

Example admin configuration:

```json
{
    "admin_id": "admin_12345",
    "admin_name": "Sarah Johnson, RN",
    "role": "Director of Nursing",
    "report_preferences": {
        "interested_in": ["stability", "bathroom", "medication", "sleep"],
        "priority_filter": ["critical", "warning"],
        "exclude_report_types": ["infrastructure"],
        "include_celebrations": true,
        "digest_frequency": "daily",
        "digest_time": "07:00"
    }
}
```

```json
{
    "admin_id": "admin_67890",
    "admin_name": "Mike Chen",
    "role": "IT Manager",
    "report_preferences": {
        "interested_in": ["infrastructure", "device_offline", "battery_low"],
        "priority_filter": ["critical", "warning"],
        "exclude_report_types": ["stability", "bathroom"],
        "include_celebrations": false,
        "digest_frequency": "realtime",
        "alert_method": "sms"
    }
}
```

---

## How the AI Chief of Staff Operates

### Daily Workflow

1. **Collect Reports** (from all locations)
   - Programmatic filtering by `report_type`, `priority`
   - Group by `location_id`, sort by `severity_rank`

2. **LLM Synthesis** (per admin's interests)
   - Feed filtered reports to LLM
   - Synthesize cross-location insights
   - Identify patterns and trends
   - Celebrate improvements

3. **Generate Digests** (per admin)
   - Personalized based on admin's `interested_in` preferences
   - Ranked by `severity_rank`
   - Include both concerns and celebrations
   - Add LLM-generated insights

4. **Deliver Intelligently**
   - Email digests (daily/weekly)
   - Real-time SMS for critical items
   - Dashboard updates
   - Slack/Teams integration

---

## Best Practices for Microservice Developers

When sending reports to the organization:

1. **Always include location identity**
   - `location_id` (immutable)
   - `location_name` (current display name)

2. **Categorize, don't specify audiences**
   - Use `report_type` to categorize (e.g., `"stability"`, `"bathroom"`)
   - DON'T specify who should receive it
   - Let org bot route based on admin preferences

3. **Write natural language**
   - `summary` should be one clear sentence
   - `concerns` should be complete statements
   - `context` should include whatever helps explain

4. **Track lifecycles**
   - Generate `report_id` for concerns
   - Send resolution reports with `previous_report_id`
   - Include `sentiment` appropriately

5. **Share good news**
   - Don't only report problems
   - Celebrate improvements (`sentiment="celebration"`)
   - Always send daily summaries (even if no concerns)

6. **Be actionable**
   - `recommended_action` should be specific
   - Include urgency indicators
   - Provide enough context for decision-making

---

## State Management for Concern Lifecycle

Microservices should track active concerns:

```python
self.active_org_concerns = {
    "stability": {
        "report_id": "stability_concern_755735_1767239825686",
        "sent_at_ms": 1767239825686,
        "severity_rank": 92,
        "resolved": False
    }
}
```

When a concern resolves:

```python
# Send resolution report
report.send_org_report(
    botengine,
    location_object,
    priority=report.PRIORITY_INFO,
    report_type="stability",
    sentiment=report.SENTIMENT_RESOLUTION,
    summary="Stability score returned to normal",
    previous_report_id=self.active_org_concerns["stability"]["report_id"],
)

# Clear from active concerns
self.active_org_concerns["stability"]["resolved"] = True
```

---

## Implementation Notes

- `send_org_report()` sends via datastream message to the organizational bot
- Organizational bot runs separately from location bots
- LLM processing happens at the organizational level, not per-location
- Schema is intentionally flexible — extend `report_type` values as needed
- `add_event()` with `"organizational_visibility": True` in the event schema routes a full `send_org_report()`-compatible payload to `report_to_org` (maps `criticality`→`priority`, `event_type` prefix→`report_type`, defaults `sentiment` to `SENTIMENT_CONCERN`)
- `PROTECTED_REPORT_ADDRESSES` (`dailyreport`, `weeklyreport`, `monthlyreport`) cannot be deleted via `delete_report()`
