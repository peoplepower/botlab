# Trends Report - Organization Microservice

Organization-level microservice that aggregates trend data from all child locations and generates a PDF report with statistical plots and LLM-enhanced narrative text.

## Trigger

Manual only via `trends_report_run_test` datastream:

```json
{
  "test_case": "generate_report"
}
```

Optional `disable_llm` flag skips LLM enhancement and generates the PDF with deterministic text only:

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
| `trends` (TRENDS_NOW) | Time-series | `request_data(DATA_REQUEST_TYPE_LOCATION_TIME_STATES)` across all child locations, past 30 days (excluding current day) |
| `trends_metadata` | Non-time-series | `botengine.get_state()` merged from all child locations that have it |

## Report Sections

### Section 1 - Analysis Overview
Population-level statistics aggregated across all locations. Includes category breakdowns (Sleep, Bathroom, Activity, etc.), outlier detection via z-scores (top 20), and an LLM-generated narrative overview.

**Charts:** Category overview dual horizontal bar chart (trend counts + location coverage per category), paginated z-score heatmap (locations x categories, sorted by most deviant first, max 20 rows/page).

**LLM:** `gpt-4o-mini` generates `overview_text` (3-4 sentences, max 150 words, temp 0.2).

### Section 2 - Individual Analysis
One page per location (up to `MAX_DETAILED_LOCATIONS=20`, sorted most-critical-first) with three parts:

1. **LLM Narrative** - Description of outlying trend values for the individual.
2. **Charts** - Side-by-side pie chart (healthy/concerning/critical trend distribution) and wellness score timeline.
3. **Trends Table** - Current trends data table (Trend, Value, Avg, Std Dev, Z-Score) with severity row highlighting (light orange for concerning, light red for critical).

**Wellness score timeline** is extracted by priority:
1. A trend with "wellness" in the title
2. A `category.summary` trend
3. Synthetic: `100 - (avg |z-score| * 20)`, clamped to [0, 100]

**LLM:** `gpt-4o-mini` generates `individual_text` per location (2-3 sentences, max 100 words, temp 0.2).

### Section 2B - Additional Locations Summary
Locations beyond the top 20 appear in a compact summary table showing category-level average |z-score| per location. No LLM text, no charts, no historical data.

### Section 3 - Review
Cross-location pattern analysis (top 15 patterns by affected location count) and category health classification (healthy / concerning / critical based on z-score thresholds). LLM-generated recommendations.

**Charts:** Category health stacked bar chart, cross-location patterns table.

**LLM:** `gpt-4o-mini` generates `review_text` (4-6 sentences, max 200 words, temp 0.2).

## Pipeline

```
trends_report_run_test (datastream, test_case="generate_report", disable_llm=False)
  |
  v
_request_trends_data()
  |-- Guard: skip if report already in progress
  |-- botengine.request_data(LOCATION_TIME_STATES, names=["trends"], exclude current day)
  |-- start_timer_s(10s, data_request_timeout, retry_count=0)
  |
  v
async_data_request_ready()  [async context - no timers/state]
  |-- botengine.get_state("trends_metadata", location_id) merged from all locations
  |-- _sort_by_criticality(): sort locations by critical > concerning > avg |z-score|
  |-- report_builder.build_report_skeleton()
  |-- botengine.save_variable(report + ready_for_processing=True + disable_llm flag)
  |
  v
timer_fired()  [sync context, retries up to 6x @ 10s]
  |-- Detect ready skeleton
  |-- If disable_llm: skip LLM pipeline, jump to _finalize_report()
  |-- Otherwise: _process_next_enhancement_task(task[0])  -->  analysis_overview
  |
  v
llm_response()  -->  apply enhancement  -->  _process_next_enhancement_task(task[1..N])  -->  individual_analysis per location
  |
  v
llm_response()  -->  apply enhancement  -->  _process_next_enhancement_task(task[N+1])  -->  review_summary
  |
  v
llm_response()  -->  apply enhancement  -->  _finalize_report()
  |
  v
_generate_and_email_pdf()
  |-- plot_builder.generate_*()  -->  BytesIO PNGs
  |-- fpdf2: title, Section 1, Section 2 (per-location pages), Section 2B (summary), Section 3
  |-- Unicode-to-Latin-1 sanitization for fpdf2 compatibility
  |-- base64 encode  -->  botengine.email_admins()
  |-- Clean up STATE_VAR_REPORT_IN_PROGRESS
```

## Files

| File | Purpose |
|---|---|
| `organization_trends_report_microservice.py` | Main orchestration class (pipeline, LLM message builders, PDF generation) |
| `report_builder.py` | Deterministic report skeleton builder (no LLM). Sections 1-3, enhancement task extraction, LLM text injection |
| `plot_builder.py` | Matplotlib chart generation (returns BytesIO buffers). Category overview, paginated z-score heatmap, individual pie+timeline, category health stacked bar |
| `services.py` | Constants (references, thresholds, category labels, LLM config, system prompt) |
| `runtime.json` | Trigger config: Timer + DataStream + DataRequest |
| `structure.json` | Remote pip deps: `fpdf2`, `matplotlib` |
| `index.py` | ORGANIZATION_MICROSERVICES registration |
| `tools/trends_report_run_test.py` | CLI test tool (two test cases: `GENERATE_REPORT`, `GENERATE_REPORT_NO_LLM`) |
| `tests/test_trends_report.py` | Unit tests |

## Z-Score Thresholds

| Level | Threshold | Usage |
|---|---|---|
| Concerning | \|z\| >= 1.5 | Alerts in Section 2, outliers in Section 1, cross-location patterns in Section 3 |
| Critical | \|z\| >= 2.5 | Category health classification in Section 3, criticality sorting |

## Location Criticality Sorting

Locations are sorted most-critical-first before report generation. Scoring per location from latest trends:
1. **Primary:** count of critical trends (|z| >= 2.5)
2. **Secondary:** count of concerning trends (|z| >= 1.5)
3. **Tertiary:** average absolute z-score

## Constants

| Constant | Value | Purpose |
|---|---|---|
| `MAX_DETAILED_LOCATIONS` | 20 | Locations receiving full individual analysis (LLM + charts) |
| `DATA_REQUEST_TIMEOUT_S` | 10 | Seconds between data request timeout retries |
| `MAX_DATA_REQUEST_RETRIES` | 6 | Maximum timer retries before giving up |
| `HEATMAP_ROWS_PER_PAGE` | 20 | Z-score heatmap pagination limit |
| `LLM_TEMPERATURE` | 0.2 | LLM sampling temperature |

## Dependencies

- **fpdf2** - PDF generation (installed remotely via `structure.json`)
- **matplotlib** - Statistical plots (installed remotely, `Agg` backend for headless)
- **llm_openai** org microservice - Routes LLM requests to OpenAI (`gpt-4o-mini`)
- **trends** location microservice - Produces the `trends` and `trends_metadata` states at each child location

## Notification

Emails sent to organization admins in category `ORGANIZATION_USER_NOTIFICATION_CATEGORY_MANAGER` with the PDF attached as `Trends_Analysis_Organization_Report.pdf`.
