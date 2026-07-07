"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Tech Persona - LLM prompts and configuration for IT Infrastructure reports
"""

# Email template filename (server-side Velocity template)
EMAIL_TEMPLATE_FILENAME = "bots/daily_report.vm" # "bots/org_report_tech.vm"

# Persona identifier
PERSONA_ID = "tech"

# Report title and icon
REPORT_TITLE = "IT Infrastructure Report"
REPORT_ICON = "server"

def get_extraction_prompt(master_report_content, organization_name="the organization"):
    """
    Generate LLM prompt to extract IT Infrastructure insights from master report
    
    :param master_report_content: The full master report content (dict or JSON string)
    :param organization_name: Name of the organization
    :return: Prompt string for LLM
    """
    prompt = f"""You are creating an IT Infrastructure executive report for technical staff at {organization_name}.

Your audience includes:
- IT Managers
- Technical Support Staff
- Infrastructure Team
- Facilities Managers

**GOAL**: Help them prioritize infrastructure problems and device issues that need technical attention TODAY.

**MASTER REPORT DATA**:
{master_report_content}

**YOUR TASK**:
Analyze these reports and identify the TOP INFRASTRUCTURE PROBLEMS requiring attention TODAY.

Focus on:
1. **Critical Outages** - Gateway offline, complete monitoring loss, network down
2. **Systemic Issues** - Problems affecting multiple locations (WiFi, ISP, firmware)
3. **Actionable Intelligence** - Specific device IDs, error patterns, troubleshooting steps

**OUTPUT FORMAT** - Pure Structured Data (NO HTML):

Return ONLY a JSON object with this structure:

{{
  "executive_summary": {{
    "total_locations": number,
    "locations_with_issues": number,
    "critical_count": number,
    "warning_count": number,
    "devices_offline": number,
    "top_concern": "string - one sentence describing most critical issue"
  }},
  "top_priorities": [
    {{
      "location_id": "string",
      "location_name": "string",
      "primary_concern": "string - specific technical issue",
      "severity": "critical|warning",
      "days_active": number,
      "specific_data": {{
        "device_type": "Gateway|Sensor|Camera",
        "device_id": "string",
        "devices_affected": number,
        "last_seen": "timestamp or relative time",
        "error_code": "optional string"
      }},
      "context": "string - impact (loss of monitoring, connectivity, etc.)",
      "recommended_action": "string - specific troubleshooting step"
    }}
  ],
  "trends": [
    {{
      "category": "connectivity|gateway|battery|firmware",
      "description": "string - what's happening",
      "locations_affected": number,
      "direction": "negative|neutral",
      "specifics": "string - technical details, potential root cause"
    }}
  ],
  "resolutions": [
    {{
      "location_id": "string",
      "location_name": "string",
      "description": "string - what was fixed",
      "days_to_resolve": number,
      "intervention": "string - what action was taken"
    }}
  ],
  "metadata": {{
    "total_locations_analyzed": number,
    "reports_processed": number,
    "time_range_hours": 24
  }}
}}

**CRITICAL RULES - Prevent Hallucination:**

1. **Use ONLY data from the reports provided** - Do not invent locations, devices, or issues
2. **Include specific device identifiers** - Device IDs, types, model numbers from reports
3. **Verify severity matches impact** - Critical = complete outage, Warning = degraded service
4. **Days active must be accurate** - Count from first report of issue
5. **Context must describe IMPACT** - Loss of monitoring, connectivity issues, etc.
6. **Actions must be technically specific** - "Check power/network at gateway" not "Fix it"
7. **Trends need quantitative support** - "12 gateways" not "many devices"
8. **No assumptions about cause** - "Possible ISP problem" not "ISP is down"
9. **Sort by severity then days_active** - Longest outages first
10. **Maximum 10 top priorities** - Focus on truly critical issues

**Examples of Good vs Bad Output:**

GOOD Priority:
{{
  "location_name": "Building A",
  "primary_concern": "Gateway offline for 3 days",
  "specific_data": {{
    "device_type": "Gateway",
    "device_id": "gw_12347_001",
    "devices_affected": 12,
    "last_seen": "2026-01-01 06:00:00"
  }},
  "context": "Complete loss of monitoring for entire building - all 12 devices unreachable",
  "recommended_action": "Dispatch technician to check physical power connection and network cable, verify ISP service status"
}}

BAD Priority (hallucinated details):
{{
  "location_name": "Building A",
  "primary_concern": "Network card failed",  ❌ Not in data
  "context": "Need to order new hardware",  ❌ Assumption
  "recommended_action": "Replace gateway"  ❌ Too specific without diagnosis
}}

**CRITICAL**: Output ONLY valid JSON, no markdown, no explanations, no other text."""

    return prompt


