# Report Aggregator Microservice

**Service:** `org.caredaily.ChiefOfStaff`  
**Package:** `org.ppc.Microservices/intelligence/report_aggregator`  
**Created:** January 2, 2026  
**Version:** 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [How It Works](#how-it-works)
4. [Components](#components)
5. [Data Flow](#data-flow)
6. [State Management](#state-management)
7. [LLM Integration](#llm-integration)
8. [Report Schema](#report-schema)
9. [Email Delivery](#email-delivery)
10. [Configuration](#configuration)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)

---

## Overview

### What Is the AI Chief of Staff?

The AI Chief of Staff is an **organization-level intelligence service** that helps executives and staff prioritize their attention by:

1. **Gathering** reports from 10s-100s of location-level AI Ambient Assistants
2. **Aggregating** reports in a 48-hour cache (memory-efficient)
3. **Synthesizing** comprehensive master reports using LLM (daily at 6 AM)
4. **Extracting** persona-specific insights (Health & Wellness, IT Infrastructure)
5. **Delivering** executive reports via email to organizational administrators

### The Problem It Solves

**Question:** "Who should I focus on today and why? What's changed recently?"

**Without AI Chief of Staff:**
- Executives manually review 100+ individual location reports daily
- Critical issues buried in noise
- No cross-location pattern detection
- Reactive instead of proactive

**With AI Chief of Staff:**
- Automatic prioritization of top 5-10 locations needing attention
- LLM identifies patterns across the population
- Persona-specific reports (wellness staff get wellness reports, IT gets tech reports)
- Daily emails with actionable recommendations

---

## Architecture

### System Context

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORGANIZATION                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐    │
│  │           AI Chief of Staff Service                     │    │
│  │                                                          │    │
│  │  ┌──────────────────┐     ┌──────────────────────┐    │    │
│  │  │   llm_openai     │────▶│  report_aggregator   │    │    │
│  │  │   (LLM Provider) │     │  (Core Pipeline)     │    │    │
│  │  └──────────────────┘     └──────────────────────┘    │    │
│  │                                                          │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ pulls aggregated_report state
                            ▼
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────┴────┐        ┌────┴────┐        ┌────┴────┐
   │Location │        │Location │   ...  │Location │
   │  Bot 1  │        │  Bot 2  │        │  Bot N  │
   └─────────┘        └─────────┘        └─────────┘
    Apartment 101     Suite 205          Building A
```

### Service Foundation

**Organization Bot:** `org.ppc.Bot`
- Runs at the organizational level (not per-location)
- No device drivers (locations handle devices)
- Receives organization-level datastream messages
- Manages multiple microservices

**Microservices:**
1. `llm_openai` - OpenAI LLM provider with retry logic, timeout handling
2. `report_aggregator` - **This package** - Core reporting pipeline

---

## How It Works

### The Complete Pipeline

```
STEP 1: GATHER (Daily at 6 AM)
──────────────────────────────
Org Bot pulls ──▶ Location Bot 1 aggregated_report state ─┐
                  Location Bot 2 aggregated_report state ─┼─▶ all_reports_in_progress
                  Location Bot N aggregated_report state ─┘    (temporary state, purged after use)


STEP 2: SYNTHESIZE (Daily at 6 AM)
──────────────────────────────────────
Cache (past 24h) ──▶ LLM (gpt-4o) ──▶ Master Report
                     "Prioritize top      └─ org_report_master
                      locations needing       (state variable)
                      attention..."


STEP 3: EXTRACT (After master report)
─────────────────────────────────────────
Master Report ──▶ LLM (gpt-4o) ──▶ Wellness Report
                  "Extract health      └─ org_report_wellness
                   & wellness info"       (state variable)
                        │
                        └──▶ Tech Report
                             └─ org_report_tech
                                (state variable)


STEP 4: DELIVER (After extraction)
──────────────────────────────────────
Wellness Report ──▶ Email (Template: bots/org_report_wellness.vm)
                    └─ To: Admins [Category 1, 2]

Tech Report ─────▶ Email (Template: bots/org_report_tech.vm)
                   └─ To: Admins [Category 1, 2]
```

### Execution Timeline

**6:00 AM Daily (Cron: `0 6 * * *`):**
1. Load cache (auto-purge >48h old reports)
2. Filter past 24h reports
3. Send to LLM for master report synthesis (async)
4. *Wait for LLM response...*
5. Save master report
6. Extract wellness report (async LLM)
7. Extract tech report (async LLM)
8. *Wait for LLM responses...*
9. Save persona reports
10. Email wellness report to admins
11. Email tech report to admins

**6:00 AM Sunday (Cron: `0 6 * * 0`):**
- Same as daily, but pulls reports from past 48h for weekly trends

---

## Components

### File Structure

```
org.ppc.Microservices/intelligence/report_aggregator/
├── README.md (this file)
├── __init__.py
├── index.py (microservice registration)
├── runtime.json (triggers: datastream + schedules)
├── services.py (constants: collections, schedules, LLM references)
├── report_schema.py (unified JSON schema + helpers + examples)
├── organization_report_aggregator_microservice.py (main logic, 735 lines)
└── personas/
    ├── __init__.py
    ├── wellness.py (Health & Wellness LLM prompts + config)
    └── tech.py (IT Infrastructure LLM prompts + config)
```

### Core Class: `OrganizationReportAggregatorMicroservice`

**Inherits:** `Intelligence` (from `org.ppc.Bot/intelligence/intelligence.py`)

**Key Methods:**

**Datastream Handlers:**
- `datastream_updated()` - Routes incoming messages (`generate_master_report`, `clear_report_cache`, `openai`)

**Schedule Handlers:**
- `schedule_fired()` - Routes schedule triggers
- `_generate_daily_reports()` - Daily at 6 AM
- `_generate_weekly_reports()` - Sunday at 6 AM

**Cache Management:**
- `_load_report_cache()` - Load from state, auto-purge old reports
- `_save_report_cache()` - Save to state

**LLM Integration:**
- `_generate_master_report_llm()` - Send master synthesis request
- `_handle_master_report_llm_response()` - Process master report
- `_extract_wellness_report()` - Send wellness extraction request
- `_handle_wellness_extract_llm_response()` - Process wellness report
- `_extract_tech_report()` - Send tech extraction request
- `_handle_tech_extract_llm_response()` - Process tech report

**Email Delivery:**
- `_email_wellness_report()` - Format and send wellness email
- `_email_tech_report()` - Format and send tech email

---

## Data Flow

### 1. Report Collection (Location → Organization)

**Location Bot Code (Example):**
```python
import signals.report as report

# Location bot sends report to organization
report.send_org_report(
    botengine,
    location_object,
    report_type="stability",           # Type of report
    priority=report.CRITICALITY_WARNING,
    sentiment=report.SENTIMENT_CONCERN,
    report_id="stability_bathroom_decline",  # Unique ID for lifecycle
    summary="3-day decline in bathroom visits",
    concerns=["Bathroom visits dropped from 6/day to 2/day over 3 days"],
    context="Possible dehydration or UTI risk",
    recommended_action="Call resident to assess hydration",
    severity_rank=85,
    days_active=3,
    scores={"bathroom_frequency": 0.3}  # 0-1 scale
)
```

**What Happens:**
1. `send_org_report()` stores the report in the location bot's `aggregated_report` state variable (via the `report_to_org` datastream handler in the *reports* microservice — not this aggregator)
2. At 6 AM daily, the organization bot calls `_pull_all_location_reports()` to fetch the `aggregated_report` state from each child location via `async_data_request` / `request_data()`
3. Collected reports are held in `all_reports_in_progress` until all location responses arrive (with timeout/retry)
4. The pipeline (rules engine → report builder → LLM enhancement) runs against all collected reports

> **Architecture note:** The original push-based `report_to_org` datastream (where location bots pushed directly into this aggregator) was replaced by this pull-based model. The aggregator no longer registers `report_to_org` in its `runtime.json`.

### 2. Master Report Synthesis (Cache → Master Report)

**Input:** List of 100-500 reports from past 24 hours

**LLM Prompt Focus:**
```
Analyze 450 reports from 100 locations.

Identify TOP LOCATIONS needing attention. Extract specific metrics.

CRITICAL: Output STRUCTURED DATA, not HTML. Be specific, don't hallucinate.

Output JSON with:
- Executive summary (counts, top concern)
- Top priorities (location_name, primary_concern, severity, specific_data, context, action)
- Trends (category, description, locations_affected, direction)
- Resolutions (location_name, description, days_to_resolve)
```

**LLM Output (Structured Data):**
```json
{
  "executive_summary": {
    "total_locations": 45,
    "locations_needing_attention": 12,
    "critical_count": 3,
    "top_concern": "Sleep quality declining across multiple locations"
  },
  "top_priorities": [
    {
      "location_name": "Apartment 103",
      "primary_concern": "Bathroom visits declined from 6/day to 2/day over 3 days",
      "severity": "critical",
      "days_active": 3,
      "specific_data": {
        "current_visits_per_day": 2,
        "baseline_visits_per_day": 6,
        "decline_percentage": 67
      },
      "context": "Possible dehydration or UTI risk",
      "recommended_action": "Call resident to assess hydration..."
    }
  ]
}
```

**Python Formats to HTML:**
```python
# report_schema.py handles ALL HTML generation
formatted_report = report_schema.create_report_from_llm_output(
    persona="wellness",
    title="Health & Wellness Report",
    llm_data=llm_output  # Structured data from LLM
)
```

**Final Report (Ready for Email):**
```json
{
  "sections": [
    {
      "title": "Top Priorities",
      "icon": "exclamation-triangle",
      "color": "D0021B",
      "content": [
        "<b>Apartment 103</b><br>Bathroom visits declined from 6/day to 2/day...<br><i>Possible dehydration or UTI risk</i><br><b>Action:</b> Call resident..."
      ]
    }
  ]
}
```

**Key Principle:** LLM does intelligence (analyze, prioritize, extract), Python does formatting (HTML, colors, structure)

### 3. Persona Extraction (Master → Persona Reports)

**Input:** Master report JSON (already synthesized)

**Wellness LLM Prompt Focus:**
```
Extract Health & Wellness insights from master report.

Audience: Directors of Nursing, Care Coordinators, Clinical Staff

FILTERING: ONLY wellness, stability, bathroom, sleep categories

CRITICAL RULES (Anti-Hallucination):
1. Use ONLY data from reports - don't invent
2. Specific numbers required - actual values (visits/day, hours)
3. Verify severity matches data
4. Context must be clinical (WHY it matters)
5. Actions must be specific and actionable
6. Maximum 10 top priorities - focus on critical

Output: STRUCTURED JSON (location_name, primary_concern, severity, specific_data, context, action)
```

**LLM Output (Structured):**
```json
{
  "top_priorities": [
    {
      "location_name": "Apartment 103",
      "primary_concern": "3-day decline in bathroom visits",
      "severity": "critical",
      "specific_data": {
        "current_visits_per_day": 2,
        "baseline_visits_per_day": 6
      },
      "context": "Possible dehydration or UTI risk",
      "recommended_action": "Call resident to assess hydration..."
    }
  ]
}
```

**Python Formats:**
```python
# _format_priority_item() generates HTML from structured data
html = "<b>Apartment 103</b><br>3-day decline in bathroom visits<br><i>Possible dehydration or UTI risk</i><br><b>Action:</b> Call resident..."
```

**Output:** Wellness report saved to `org_report_wellness` state variable

**Tech extraction works identically** with IT-specific filtering and context

### 4. Email Delivery (Persona → Admins)

**Wellness Email:**
```python
botengine.email_admins(
    email_subject="🏥 Health & Wellness Report - Friday, January 2, 2026",
    email_html=True,
    email_template_filename="bots/org_report_wellness.vm",  # Server-side template
    email_template_model={
        "title": "Health & Wellness Report",
        "subtitle": "Friday, January 2, 2026",
        "icon": "heartbeat",
        "contentArray": [
            {
                "title": "Executive Summary",
                "icon": "clipboard-list",
                "color": "694fee",
                "content": [
                    "<b>12 of 45 locations</b> need attention today..."
                ]
            },
            {
                "title": "Top Priorities - Action Needed Today",
                "icon": "exclamation-triangle",
                "color": "D0021B",
                "content": [
                    "<b>Apartment 103</b>: 3-day decline...",
                    "<b>Suite 205</b>: Sleep dropped to 4.2 hours..."
                ]
            }
        ],
        "metadata": {
            "total_locations": 45,
            "locations_needing_attention": 12,
            "critical_count": 3,
            "warning_count": 6
        }
    },
    categories=[1, 2]  # Manager + Technician notification categories
)
```

**Who Receives Emails:**
- Organization administrators who have opted into notification categories:
  - Category 1 = Manager
  - Category 2 = Technician
- Phase 2 will add user properties filtering for granular opt-out

---

## State Management

### Why NO Class Variables?

**Problem:** Class variables persist across all executions
- Bot executes 1000s of times per day
- Memory grows unbounded
- Cache bloats over time
- Lost on bot restart

**Solution:** Store EVERYTHING in state variables
```python
# ❌ WRONG - Don't do this
class Microservice:
    def __init__(self, botengine, parent):
        self._report_cache = []  # Memory leak!
        self._cached_at = None

# ✅ CORRECT - Do this
class Microservice:
    def __init__(self, botengine, parent):
        # NO cache variables!
        pass
    
    def _load_report_cache(self, botengine):
        # Load from state on-demand
        return botengine.get_state("org_report_cache")
    
    def _save_report_cache(self, botengine, reports):
        # Save immediately
        botengine.set_state("org_report_cache", reports, overwrite=True)
```

### State Variables Used

**State Variables:**

| Name | Purpose | Retention | Size (1000 locs) |
|------|---------|-----------|------------------|
| `org_report_cache` | Temporary staging for incoming reports | 48 hours (auto-purge) | ~10 MB |

| `org_report_master` | Comprehensive daily master reports | Overwritten each run | ~50 KB |
| `org_report_wellness` | Health & Wellness persona reports | Overwritten each run | ~30 KB |
| `org_report_tech` | IT Infrastructure persona reports | Overwritten each run | ~30 KB |

**Loading Report Data:**
```python
# Load the latest master report
master_report = botengine.load_variable("org_report_master")
```

### Cache Auto-Purge

**When:** Every time cache is loaded
**Logic:**
```python
cutoff_ms = botengine.get_timestamp() - (48 * utilities.ONE_HOUR_MS)
reports = [r for r in cached_reports if r.get('timestamp_ms', 0) >= cutoff_ms]
```

**Why 48 Hours?**
- Daily reports need past 24 hours
- LLM comparisons need "yesterday vs day before" (48 hours)
- Weekly synthesis uses cached reports from the 48-hour window
- Keeps cache small: 1-10 MB for 100-1000 locations

---

## LLM Integration

### Pattern: Async Request → Callback

**1. Send Request:**
```python
import signals.llm as llm

llm.chat(
    botengine,
    self.parent,  # Organization object
    self.intelligence_id,  # This microservice's ID
    reference="master_report",  # Unique reference for tracking
    argument={"is_weekly": False},  # Optional context
    provider_api=llm.PROVIDER_API_OPENAI_CHAT_COMPLETION,
    **{
      "messages": [{"role": "user", "content": prompt}],
      "model": "gpt-4o",
      "temperature":0.2
    }
)
```

**2. Receive Response:**
```python
def llm_response(self, botengine, response, reference, argument):
    if reference == "master_report":
        self._handle_master_report_llm_response(botengine, response, argument)
    elif reference == "wellness_extract":
        self._handle_wellness_extract_llm_response(botengine, response, argument)
```

**3. Process Response:**
```python
def _handle_master_report_llm_response(self, botengine, response, argument):
    content = response.get('content', '').strip()
    try:
        master_report = json.loads(content)  # Parse JSON from LLM
        
        # Save master report
        botengine.save_variable(
            "org_report_master",
            master_report,
            overwrite=True
        )
        
        # Continue pipeline: extract personas
        self._extract_wellness_report(botengine, master_report)
        self._extract_tech_report(botengine, master_report)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
```

### LLM Configuration

**Model:** `gpt-4o` (OpenAI's most capable model)  
**Temperature:** `0.2` (focused, consistent, minimal creativity)  
**Provider:** `llm_openai` microservice  
**Retry Logic:** Exponential backoff, max 10 retries, 5-minute timeout  
**Token Tracking:** Automatic via `Intelligence.track_llm_usage()`

### LLM References (Tracking)

Defined in `services.py`:
```python
LLM_REFERENCE_MASTER_REPORT = "master_report"
LLM_REFERENCE_WELLNESS_EXTRACT = "wellness_extract"
LLM_REFERENCE_TECH_EXTRACT = "tech_extract"
LLM_REFERENCE_WEEKLY_SYNTHESIS = "weekly_synthesis"
```

**Why?** Multiple async LLM requests in flight simultaneously - need to route responses correctly

---

## Report Schema

### Unified Structure (All Personas)

**Design Principle:** ONE schema for ALL personas (wellness, tech, safety, energy, CEO, etc.)

**Schema Location:** `report_schema.py`

**Structure:**
```json
{
  "sections": [
    {
      "title": "Section Title",
      "icon": "fontawesome-icon-name",
      "color": "HEX_COLOR",
      "items": [
        {
          "comment": "HTML-formatted content",
          "criticality": "critical|warning|info",
          "location_id": "optional",
          "location_name": "optional",
          "days_active": optional_number,
          "recommended_action": "optional"
        }
      ]
    }
  ],
  "metadata": {
    "total_locations": 45,
    "locations_needing_attention": 12,
    "critical_count": 3,
    "warning_count": 6,
    "resolved_count": 2
  }
}
```

**Why Unified?**
- Future-proof: Add new personas without changing core structure
- Consistent: Same as location-level reports (`dailyreport` format)
- Maintainable: Single schema definition
- Testable: Schema validation functions provided

**Helper Functions:**
```python
from . import report_schema

# Create a report
report = report_schema.create_report(
    persona="wellness",
    title="Health & Wellness Report",
    subtitle="Friday, January 2, 2026",
    sections=[...]
)

# Create a section
section = report_schema.create_section(
    title="Top Priorities",
    icon="exclamation-triangle",
    items=[...],
    criticality="critical"
)

# Create an item
item = report_schema.create_item(
    comment="<b>Apartment 103</b>: Issue description",
    criticality="critical",
    location_id="12345",
    days_active=3,
    recommended_action="Take specific action"
)
```

### Color Codes (Criticality)

| Criticality | Hex Color | Visual | Use Case |
|-------------|-----------|--------|----------|
| `critical` | `D0021B` | 🔴 Red | Urgent issues requiring immediate action |
| `warning` | `F5A623` | 🟠 Orange | Important issues needing attention soon |
| `info` | `694fee` | 🟣 Purple | Informational, positive trends |
| Success | `27AE60` | 🟢 Green | Resolutions, improvements, wins |

### HTML Formatting in Comments

**Allowed Tags:**
- `<b>bold</b>` - Important facts, location names
- `<i>italic</i>` - Context, parenthetical notes
- `<br>` - Line breaks
- `<code>monospace</code>` - Technical identifiers (tech reports only)

**Example:**
```html
<b>Apartment 103</b>: Sleep declined to 4 hours. <i>Significant disruption.</i><br><b>Action:</b> Contact family to investigate cause.
```

---

## Email Delivery

### Server-Side Templates (Velocity)

**Why Server-Side?**
- ✅ Branding controlled by server (not hardcoded)
- ✅ Consistent with platform patterns (`bots/daily_report.vm`)
- ✅ Templates shared across mobile/web/email
- ✅ Easy to update without code changes

**Templates Required:**

1. **`bots/org_report_wellness.vm`** - Health & Wellness emails
2. **`bots/org_report_tech.vm`** - IT Infrastructure emails

**Template Model Structure:**
```velocity
{
  title: String,          ## "Health & Wellness Report"
  subtitle: String,       ## "Friday, January 2, 2026"
  icon: String,           ## "heartbeat"
  contentArray: [         ## Array of sections
    {
      title: String,      ## "Executive Summary"
      icon: String,       ## "clipboard-list"
      color: String,      ## "694fee" (hex without #)
      content: [String]   ## Array of HTML-formatted strings
    }
  ],
  metadata: {             ## Report metrics
    total_locations: Integer,
    locations_needing_attention: Integer,
    critical_count: Integer,
    warning_count: Integer,
    resolved_count: Integer
  }
}
```

### Recipient Targeting

**Phase 1: Notification Categories**
```python
botengine.email_admins(
    email_subject="Report Title",
    email_template_filename="bots/org_report_wellness.vm",
    email_template_model={...},
    categories=[1, 2]  # Manager + Technician
)
```

**Who Gets Emails:**
- Org admins who opted into notification category 1 (Manager)
- Org admins who opted into notification category 2 (Technician)

**Category Definitions:**
- 1 = `ORGANIZATION_USER_NOTIFICATION_CATEGORY_MANAGER`
- 2 = `ORGANIZATION_USER_NOTIFICATION_CATEGORY_TECHNICIAN`
- 3 = Billing
- 4 = Researcher
- 5 = Provider
- 6 = Responder

**Phase 2: User Properties Filtering (Future)**
- Query `botengine.get_organization_users()` for user list
- Check user properties for `bot.chief_of_staff_preferences`
- Filter to users who opted into specific personas
- Use `email_addresses=[list]` for explicit targeting

---

## Configuration

### Runtime Configuration (`runtime.json`)

```json
{
  "version": {
    "trigger": 2497,
    "dataStreams": [
      { "address": "generate_master_report" },
      { "address": "clear_report_cache" },
      { "address": "openai" }
    ],
    "schedules": {
      "DAILY_MASTER_REPORT": "0 0 6 * * ? *"
    },
    "communications": [
      {
        "category": 0,
        "email": true,
        "push": false,
        "sms": false,
        "msg": false
      }
    ]
  }
}
```

**Trigger Breakdown:**
- `2497` = Schedule (1) + DataStream (256) + Timer (64) + DataRequest (2048) + Config (128)
- Datastreams: `generate_master_report` (manual trigger), `clear_report_cache` (cache reset), `openai` (LLM responses)
- Schedules: Daily at 6 AM
- Communications: Email only (no push/SMS at org level)

> **Note:** `report_to_org` is **not** registered here. Reports are pulled from child locations via `request_data()` / `aggregated_report` state, not pushed to this microservice.

### Service Constants (`services.py`)

```python
# State variable keys
COLLECTION_ORG_REPORT_CACHE = "org_report_cache"
COLLECTION_ORG_REPORT_MASTER = "org_report_master"
COLLECTION_ORG_REPORT_WELLNESS = "org_report_wellness"
COLLECTION_ORG_REPORT_TECH = "org_report_tech"

# Schedule IDs
SCHEDULE_DAILY_MASTER_REPORT = "DAILY_MASTER_REPORT"
SCHEDULE_WEEKLY_SYNTHESIS = "WEEKLY_SYNTHESIS"

# LLM references
LLM_REFERENCE_MASTER_REPORT = "master_report"
LLM_REFERENCE_WELLNESS_EXTRACT = "wellness_extract"
LLM_REFERENCE_TECH_EXTRACT = "tech_extract"
```

### Persona Configuration

**Wellness (`personas/wellness.py`):**
```python
EMAIL_TEMPLATE_FILENAME = "bots/org_report_wellness.vm"
PERSONA_ID = "wellness"
REPORT_TITLE = "Health & Wellness Report"
REPORT_ICON = "heartbeat"
```

**Tech (`personas/tech.py`):**
```python
EMAIL_TEMPLATE_FILENAME = "bots/org_report_tech.vm"
PERSONA_ID = "tech"
REPORT_TITLE = "IT Infrastructure Report"
REPORT_ICON = "server"
```

---

## Testing

### Local Testing

**1. Commit Service:**
```bash
./botengine --commit org.caredaily.ChiefOfStaff
```

**2. Enable for Organization (Dev Mode):**
```bash
./botengine --add_organization org.caredaily.ChiefOfStaff \
    --organization_development_mode \
    -o <ORG_ID>
```

**3. Purchase Service:**
```bash
./botengine --purchase org.caredaily.ChiefOfStaff -o <ORG_ID>
```

**4. Run Locally:**
```bash
./botengine --run org.caredaily.ChiefOfStaff \
    -i <INSTANCE_ID> \
    -o <ORG_ID>
```

**5. Send Test Report from Location Bot:**
```python
# In a location bot
import signals.report as report

report.send_org_report(
    botengine,
    location_object,
    report_type="stability",
    priority=report.CRITICALITY_WARNING,
    sentiment=report.SENTIMENT_CONCERN,
    report_id="test_report_001",
    summary="Test report for AI Chief of Staff",
    concerns=["This is a test concern"],
    context="Testing the reporting pipeline",
    recommended_action="Verify report received and cached",
    severity_rank=50,
    days_active=1
)
```

**6. Verify Cache:**
```python
# In organization bot logs
logger.info("Cache loaded: X reports, Y.YY MB")
```

**7. Trigger Report Generation:**
- Wait until 6 AM for automatic generation
- OR manually invoke `schedule_fired()` for testing

### What to Monitor

**Cache Loading:**
```
INFO |_load_report_cache() Cache loaded: 450 reports, 4.52 MB
INFO |_load_report_cache() Auto-purged 23 reports older than 48 hours
```

**Report Generation:**
```
INFO >_generate_daily_reports()
INFO |_generate_daily_reports() Processing 450 reports from past 24 hours
INFO <_generate_master_report_llm() LLM request sent
```

**LLM Responses:**
```
INFO >_handle_master_report_llm_response()
INFO |_handle_master_report_llm_response() Master report saved at timestamp 1735862400000
```

**Email Delivery:**
```
INFO |_email_wellness_report() Sending email to admins (categories [1, 2])
INFO |_email_wellness_report() Email sent successfully
```

---

## Troubleshooting

### Common Issues

**1. No Reports Collected**

**Symptom:**
```
WARNING |_generate_daily_reports() No reports found. Skipping report generation.
```

**Causes:**
- Location bots not calling `report.send_org_report()` or `report.add_event()` with `organizational_visibility: True`
- `aggregated_report` state not being written to child location state variables
- `request_data()` / `async_data_request_ready()` timeout before all locations respond

**Fix:**
- Verify location bots are calling `report.send_org_report()` or that event schemas have `"organizational_visibility": True`
- Confirm the reports microservice at child locations is writing to the `aggregated_report` state address
- Check for timeout logs in `timer_fired()` — retry count is capped at 6 attempts

**2. LLM Returns Invalid JSON**

**Symptom:**
```
ERROR |_handle_master_report_llm_response() Failed to parse LLM response as JSON
```

**Causes:**
- LLM returned markdown code fences (```json```)
- LLM returned explanation text before/after JSON
- Temperature too high (more creative = less structured)

**Fix:**
- Prompt explicitly says "Output ONLY valid JSON, no markdown"
- Temperature set to 0.2 (low)
- Add retry logic with better prompt

**3. Emails Not Delivered**

**Symptom:**
- No error, but admins don't receive emails

**Causes:**
- No admins opted into categories [1, 2]
- Email templates not created on server
- Email template model format incorrect

**Fix:**
- Verify admins exist: `botengine.get_organization_users()`
- Check admin notification category subscriptions
- Coordinate with server team to create templates
- Test template model format against `daily_report.vm`

**4. Cache Too Large**

**Symptom:**
```
INFO |_load_report_cache() Cache loaded: 10000 reports, 45.23 MB
```

**Causes:**
- More than 1000 locations reporting
- Report size exceeds 1 KB average
- Auto-purge not working

**Fix:**
- Verify auto-purge logic runs on every load
- Check report schema - are reports too large?
- Consider reducing cache retention to 24 hours if >2000 locations

**5. Schedule Not Firing**

**Symptom:**
- 6 AM arrives, no report generation

**Causes:**
- Timezone mismatch (cron in UTC, expected local time)
- Bot not running
- Schedule ID mismatch

**Fix:**
- Verify `runtime.json` schedule configuration
- Check bot is active: `./botengine --status`
- Test schedule manually: invoke `schedule_fired("DAILY_MASTER_REPORT")`
- Note: Org-level timezone behavior may differ from location-level

---

## Performance Characteristics

### Memory Usage

| Component | Size (100 locs) | Size (1000 locs) |
|-----------|------------------|------------------|
| Cache (48h) | ~1 MB | ~10 MB |
| Master Report | ~50 KB | ~50 KB |
| Wellness Report | ~30 KB | ~30 KB |
| Tech Report | ~30 KB | ~30 KB |
| **Total** | **~1.1 MB** | **~10.1 MB** |

**Why So Small?**
- Cache stored in state variables (loaded on-demand)
- Master reports are synthesized summaries (not raw data)
- Persona reports are filtered extracts (subset of master)

### Execution Time (Estimated)

| Stage | Time | Notes |
|-------|------|-------|
| Cache load | <100ms | Read from database |
| LLM Master (450 reports) | 10-30s | Depends on OpenAI load |
| LLM Wellness Extract | 5-10s | Smaller prompt |
| LLM Tech Extract | 5-10s | Smaller prompt |
| Email Delivery (2 emails) | 1-2s | API calls |
| **Total Pipeline** | **~30-60s** | Async, non-blocking |

**Daily Cost (LLM):**
- Master synthesis: ~10K tokens × $0.01/1K = $0.10
- Wellness extract: ~5K tokens × $0.01/1K = $0.05
- Tech extract: ~5K tokens × $0.01/1K = $0.05
- **Daily Total:** ~$0.20 per organization

---

## Future Enhancements

### Phase 2 (Weeks 5-8)

- Questions API for admin preferences onboarding
- User properties filtering for granular opt-out
- Additional personas (Safety, Energy, CEO, CFO, COO)
- Monthly synthesis (every 4 weeks)

### Phase 3 (Weeks 9-12)

- Custom personas with job descriptions
- Interactive web dashboard
- Drill-down from org → location reports
- Export capabilities (PDF, CSV)

### Phase 4 (Weeks 13-14)

- Load testing with 100+ organizations
- LLM cost optimization strategies
- Performance tuning
- Production deployment

---

## Related Documentation

- **Service README:** `org.caredaily.ChiefOfStaff/README.md` (user-facing)
- **Design Document:** `AI_CHIEF_OF_STAFF_DESIGN.md` (root, 2709 lines)
- **Implementation Summary:** `IMPLEMENTATION_SUMMARY.md` (root)
- **Cache Analysis:** `CACHE_SIZE_ANALYSIS.md` (root)
- **Schema Examples:** `report_schema.py` (this package)

---

**Copyright © 2026 Care Daily. All Rights Reserved.**

