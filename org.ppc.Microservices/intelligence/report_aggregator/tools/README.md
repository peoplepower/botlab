# Organization Bot Testing Tools

This directory contains CLI tools for testing the organization-level reporting system.

## Tools Overview

### 1. `generate_test_reports.py`
Generates synthetic location reports and sends them to an organization bot to populate its cache with realistic test data.

**Features:**
- Creates 25 virtual locations with diverse scenarios
- Generates reports across all categories (wellness, IT, safety, energy)
- Includes mix of concerns, resolutions, celebrations, and updates
- Varies severity and days_active for realistic patterns
- Saves generated data to JSON file for reference

**Usage:**
```bash
python generate_test_reports.py -o <organization_id> [--count 25]
```

**Example:**
```bash
python generate_test_reports.py -o 12345 --count 25
```

**Output:**
- Sends `report_to_org` datastream messages to organization bot
- Creates `test_reports_org_<org_id>.json` with generated data
- Displays statistics and breakdown of generated reports

---

### 2. `trigger_master_report.py`
Triggers the generation of a master report for an organization, which will be emailed to administrators.

**Features:**
- Forces immediate report generation (bypasses schedule)
- Triggers deterministic report building process
- Initiates LLM text enhancement
- Generates persona reports (wellness, tech)
- Sends email to organization administrators

**Usage:**
```bash
python trigger_master_report.py -o <organization_id>
```

**Example:**
```bash
python trigger_master_report.py -o 12345
```

**What Happens:**
1. Organization bot loads cached reports
2. Rules engine preprocesses and filters data
3. Deterministic report builder creates structure
4. LLM enhances text section-by-section
5. Persona reports extracted (wellness, tech)
6. Emails sent to administrators

**Expected Time:** 30-60 seconds

---

### 3. `clear_report_cache.py`
Clears an organization's report cache, allowing you to start fresh with new test data.

**Features:**
- Clears cached location reports
- Preserves generated reports (master reports, persona reports)
- Includes confirmation prompt for safety
- Resets counters and state

**Usage:**
```bash
python clear_report_cache.py -o <organization_id>
```

**Example:**
```bash
python clear_report_cache.py -o 12345
```

**What Gets Cleared:**
- ✓ `org_report_cache` state variable (incoming location reports)
- ✓ Report counters

**What's Preserved:**
- ✓ `org_report_master` state variable (latest master report)
- ✓ `org_report_wellness` state variable (latest wellness report)
- ✓ `org_report_tech` state variable (latest tech report)

---

### 4. `run_complete_test.py`
Runs the complete testing workflow end-to-end: clear cache, generate test reports, and trigger master report.

**Features:**
- Orchestrates all 3 tools in sequence
- Auto-confirms cache clear (no prompt)
- Progress tracking with timing
- Detailed summary and next steps

**Usage:**
```bash
python run_complete_test.py -o <organization_id> -u <username> -p <password> [--count 25]
```

**Example:**
```bash
python run_complete_test.py -o 12345 -u admin@example.com -p secret --count 25
```

**Steps Performed:**
1. Clear existing report cache
2. Generate synthetic test reports (25 virtual locations)
3. Trigger master report generation
4. Display summary and next steps

---

## Typical Testing Workflow

### Complete Test Cycle

```bash
# 1. Clear any existing test data
python clear_report_cache.py -o 12345

# 2. Generate synthetic test reports (25 virtual locations)
python generate_test_reports.py -o 12345 --count 25

# 3. Review generated data (optional)
cat test_reports_org_12345.json

# 4. Trigger master report generation
python trigger_master_report.py -o 12345

# 5. Check email and organization bot logs for results

# 6. Clear and start fresh (optional)
python clear_report_cache.py -o 12345
```

### Quick Iteration

```bash
# Modify test scenarios in generate_test_reports.py
# Then regenerate and trigger report
python clear_report_cache.py -o 12345 && \
python generate_test_reports.py -o 12345 && \
python trigger_master_report.py -o 12345
```

---

## Report Scenarios

The test data generator includes diverse scenarios across all categories:

### Wellness Reports (6 scenarios)
- **Critical**: Fall risk detected (3 near-falls in 48h)
- **Critical**: Bathroom visits declined 67%
- **Warning**: Sleep duration declined significantly
- **Warning**: Social isolation (14 days no departure)
- **Celebration**: Sleep quality improved
- **Resolution**: Bathroom pattern normalized

### IT Infrastructure Reports (5 scenarios)
- **Critical**: Gateway offline 3 days (complete monitoring loss)
- **Warning**: Motion sensor battery at 8%
- **Warning**: WiFi connectivity intermittent
- **Celebration**: Gateway back online after firmware update
- **Resolution**: Door sensor reconnected

### Safety Reports (4 scenarios)
- **Critical**: Water leak detected in bathroom
- **Critical**: Temperature dropped to 55°F (heating failure)
- **Warning**: High temperature (88°F for 6 hours)
- **Resolution**: Water leak resolved

### Energy Reports (2 scenarios)
- **Warning**: HVAC runtime increased 45%
- **Celebration**: Energy consumption down 18%

---

## Generated Data Format

Each report follows the organizational report schema defined in `org.ppc.Bot/signals/report.py`:

```json
{
  "location_id": 1000001,
  "location_name": "Alice Anderson",
  "timestamp_ms": 1735689600000,
  "report_id": "test_report_12345_0001",
  "priority": "critical",
  "report_type": "stability",
  "sentiment": "concern",
  "summary": "Fall risk detected - 3 near-falls in past 48 hours",
  "short_description": "Multiple stability events detected",
  "long_description": "Resident has experienced 3 near-fall events...",
  "concerns": ["Nighttime falls", "Reduced balance", "Poor lighting"],
  "context": "Recent medication change may be affecting balance",
  "recommended_actions": ["Immediate wellness check", "Review medications"],
  "severity_rank": 92,
  "days_active": 2,
  "resident_name": "Alice Anderson"
}
```

---

## Requirements

### Python Dependencies
- Python 3.7+
- `requests` library (`pip install requests`)

### API Integration
These tools send real datastream messages via the People Power REST API using `api_utils.py`.
Authentication supports username/password (with optional passcode) or cached API keys.

---

## Troubleshooting

### No reports generated
- Check organization bot logs for datastream message receipt
- Verify organization ID is correct
- Ensure organization bot has the report aggregator microservice installed

### Master report not triggered
- Check if organization bot has cached reports
- Verify schedule configuration in microservice
- Check for guardrails preventing generation

### Cache not clearing
- Verify organization bot is running
- Check datastream message delivery
- Review organization bot state variables

---

## Future Enhancements

- [ ] Add BotEngine API integration for live testing
- [ ] Support for custom scenario templates (YAML/JSON)
- [ ] Interactive mode for selecting specific scenarios
- [ ] Report validation and schema checking
- [ ] Integration with CI/CD for automated testing
- [ ] Support for historical data generation (weeks/months)
- [ ] Analytics dashboard for generated reports

---

## Notes

- Generated reports have random variation in severity_rank and days_active
- Timestamps are distributed across past 48 hours
- Each location gets 1-3 reports randomly
- Report IDs follow pattern: `test_report_{org_id}_{counter:04d}`
- Generated data is saved to `test_reports_org_{org_id}.json` for reference

