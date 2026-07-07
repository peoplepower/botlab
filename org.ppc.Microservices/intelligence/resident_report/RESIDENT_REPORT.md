# Resident Report - Organization Microservice

Organization-level microservice that aggregates each location's `resident_report` state into a single PDF and emails it to the organization's resident-report notification categories. Mirrors the `trends_report` pipeline, simplified for a single executive-summary LLM call.

## Trigger

Manual only via the `resident_report_run_test` datastream:

```json
{
  "test_case": "generate_report"
}
```

Optional `disable_llm` flag skips the LLM call and produces a deterministic PDF (also forced to true when `LLM_FEATURES_ALLOWED` is not granted on the org):

```json
{
  "test_case": "generate_report",
  "disable_llm": true
}
```

**Runtime trigger:** `2368` = Timer (64) + DataStream (256) + DataRequest (2048)

## Data Sources

| State Variable | Type | Source |
|---|---|---|
| `resident_report` | Time-series | `request_data(DATA_REQUEST_TYPE_LOCATION_TIME_STATES)` across all child locations, past week. The most recent timestamp per location is used. |

The `resident_report` state is written daily by the per-location microservice [`intelligence.reports.location_reports_resident_microservice`](../../../com.ppc.Microservices/intelligence/reports/location_reports_resident_microservice.py).

## Report Sections

### Title Page
Organization name + report date.

### Section 1 - Executive Overview
Population-level statistics across all reporting residents (total residents, residents with falls, total falls, residents with wellness < 50, average wellness, residents with journal narrative, total night bathroom visits) plus an LLM-generated narrative paragraph.

**LLM:** `gpt-4o-mini` generates `overview_text` (3-5 sentences, max 180 words, temp 0.2). The prompt receives anonymized counts and the top-5 most-critical resident snapshots (no names).

### Section 2 - Resident Roster
A single compact table covering every resident: name, location, wellness score, falls today, status one-liner. Rows are highlighted: light red if any fall today, light orange if wellness score < 50.

### Section 3 - Per-Resident Detail Pages
One page per resident, sorted most-critical-first:
1. Resident name + location heading
2. Wellness score header + 3-column scores table (sleep, bathroom, stability, social, mobility) with delta vs yesterday
3. Falls list (if any)
4. Bathroom narrative (if any)
5. Journal narrative (if any)
6. Inline matplotlib line chart of the wellness `score_history.summary` series

## Pipeline

```
resident_report_run_test (datastream, test_case="generate_report", disable_llm=False)
  |
  v
_request_resident_data()
  |-- Honor LLM_FEATURES_ALLOWED -> force disable_llm
  |-- Guard: skip if report already in progress
  |-- botengine.request_data(LOCATION_TIME_STATES, names=["resident_report"], past week)
  |-- start_timer_s(10s, data_request_timeout, retry_count=0)
  |
  v
async_data_request_ready()  [async context - no timers/state]
  |-- report_builder.latest_report_per_location(content)
  |-- report_builder.build_report_skeleton(reports_by_location, org_name, ts, disable_llm)
  |     |-- sort_by_criticality (falls first, then low wellness, then ascending wellness)
  |     |-- _population_metadata (counts)
  |     |-- enhancement_tasks = [executive_summary] when disable_llm=False
  |-- botengine.save_variable(report + ready_for_processing=True + disable_llm flag)
  |
  v
timer_fired()  [sync context, retries up to 6x @ 10s]
  |-- Detect ready skeleton
  |-- If disable_llm or no enhancement_tasks: -> _finalize_report()
  |-- Otherwise: _process_executive_summary_task(task[0])
  |
  v
llm_response() -> apply_llm_enhancement() -> _finalize_report()
  |
  v
_generate_and_email_pdf()
  |-- fpdf2 title page + Section 1 + Section 2 roster + Section 3 detail pages
  |-- matplotlib (Agg) inline charts of score_history.summary
  |-- Unicode-to-Latin-1 sanitization for fpdf2 compatibility
  |-- base64 encode -> botengine.email_admins(categories=...)
  |-- Clean up STATE_VAR_REPORT_IN_PROGRESS
```

## Files

| File | Purpose |
|---|---|
| `organization_resident_report_microservice.py` | Main orchestration class: pipeline, executive-summary LLM call, PDF generation |
| `report_builder.py` | Deterministic skeleton builder (no LLM): criticality sort, population metadata, executive-summary message builder, LLM text injection |
| `services.py` | Constants (references, thresholds, score categories, LLM config, system prompt) |
| `runtime.json` | Trigger config: Timer + DataStream + DataRequest |
| `structure.json` | Remote pip deps: `fpdf2`, `matplotlib` |
| `index.py` | ORGANIZATION_MICROSERVICES registration |
| `tools/resident_report_run_test.py` | CLI test tool (two test cases: `GENERATE_REPORT`, `GENERATE_REPORT_NO_LLM`) |
| `tests/test_resident_report.py` | Unit tests |

## Notification

Emails are sent to admins in the categories listed under the organization property `RESIDENT_REPORT_NOTIFICATION_CATEGORIES` (the same property consumed by the per-location resident report). When the property is unset or empty, the report falls back to the manager category. The PDF is attached as `Resident_Report_Organization.pdf`.

## Dependencies

- **fpdf2** - PDF generation (installed remotely via `structure.json`)
- **matplotlib** - Inline wellness charts (installed remotely, `Agg` backend)
- **llm_openai** org microservice - Routes LLM requests to OpenAI (`gpt-4o-mini`)
- **`intelligence.reports.location_reports_resident_microservice`** - Produces the per-location `resident_report` state this service consumes

## Constants

| Constant | Value | Purpose |
|---|---|---|
| `WELLNESS_SCORE_CONCERNING` | 50 | Threshold below which residents are flagged "concerning" |
| `DATA_REQUEST_TIMEOUT_S` | 10 | Seconds between data-request timeout retries |
| `MAX_DATA_REQUEST_RETRIES` | 6 | Maximum timer retries before giving up |
| `LLM_MAX_TOKENS_SUMMARY` | 400 | Max tokens for the executive summary call |
| `LLM_TEMPERATURE` | 0.2 | LLM sampling temperature |
