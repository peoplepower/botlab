"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Wellness Persona - LLM prompts and configuration for Health & Wellness reports
"""

# Email template filename (server-side Velocity template)
EMAIL_TEMPLATE_FILENAME = "bots/daily_report.vm" # "bots/org_report_wellness.vm"

# Persona identifier
PERSONA_ID = "wellness"

# Report title and icon
REPORT_TITLE = "Health & Wellness Report"
REPORT_ICON = "heartbeat"

def get_extraction_prompt(master_report_content, organization_name="the organization"):
    """
    Generate LLM prompt to extract Health & Wellness insights from master report
    
    :param master_report_content: The full master report content (dict or JSON string)
    :param organization_name: Name of the organization
    :return: Prompt string for LLM
    """
    prompt = f"""You are creating a Health & Wellness executive report for caregiving staff and clinicians at {organization_name}.

Your audience includes:
- Directors of Nursing
- Care Coordinators
- Clinical Staff
- Wellness Managers

**GOAL**: Help them prioritize their attention on the locations and residents that need care TODAY.

**MASTER REPORT DATA**:
{master_report_content}

**YOUR TASK**:
Analyze these reports and identify the TOP LOCATIONS needing attention TODAY.

Focus on:
1. **Critical Issues** - Sleep deprivation, bathroom pattern changes, fall risk, isolation
2. **Trending Problems** - Issues worsening over multiple days
3. **Actionable Intelligence** - Specific data points that indicate need for intervention

**OUTPUT FORMAT** - Pure Structured Data (NO HTML):

Return ONLY a JSON object with this structure:

{{
  "executive_summary": {{
    "total_locations": number,
    "locations_needing_attention": number,
    "critical_count": number,
    "warning_count": number,
    "top_concern": "string - one sentence describing most critical issue"
  }},
  "top_priorities": [
    {{
      "location_id": "string",
      "location_name": "string",
      "primary_concern": "string - clear, specific description",
      "severity": "critical|warning",
      "days_active": number,
      "specific_data": {{
        "metric_name": value,
        "another_metric": value
      }},
      "context": "string - why this matters clinically",
      "recommended_action": "string - specific, actionable next step"
    }}
  ],
  "trends": [
    {{
      "category": "sleep|bathroom|social|activity",
      "description": "string - what's happening",
      "locations_affected": number,
      "direction": "positive|negative|neutral",
      "specifics": "string - quantitative details"
    }}
  ],
  "resolutions": [
    {{
      "location_id": "string",
      "location_name": "string",
      "description": "string - what was resolved",
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

1. **Use ONLY data from the reports provided** - Do not invent locations, metrics, or issues
2. **Specific numbers required** - Include actual values (visits/day, hours of sleep, etc.)
3. **Verify severity matches data** - Critical = immediate health risk, Warning = concerning trend
4. **Days active must be accurate** - Count from first report of issue
5. **Context must be clinical** - Explain WHY this concern matters (dehydration risk, fall risk, etc.)
6. **Actions must be specific** - "Call resident" not just "Monitor"
7. **Trends need quantitative support** - "8 locations" not "many locations"
8. **No assumptions** - If data incomplete, note it in context
9. **Sort by severity then days_active** - Most urgent first
10. **Maximum 10 top priorities** - Focus on truly critical issues

**Examples of Good vs Bad Output:**

GOOD Priority:
{{
  "location_name": "Apartment 103",
  "primary_concern": "Bathroom visits declined from 6/day to 2/day over 3 days",
  "specific_data": {{
    "current_visits_per_day": 2,
    "baseline_visits_per_day": 6,
    "decline_percentage": 67
  }},
  "context": "Possible dehydration or urinary tract infection risk",
  "recommended_action": "Call resident to assess hydration, check for pain/burning, schedule wellness check if needed"
}}

BAD Priority (hallucinated details):
{{
  "location_name": "Apartment 103",
  "primary_concern": "Resident may be depressed",  ❌ Not in data
  "context": "They seemed sad yesterday",  ❌ Made up
  "recommended_action": "Prescribe medication"  ❌ Too specific, not actionable by staff
}}

**CRITICAL**: Output ONLY valid JSON, no markdown, no explanations, no other text."""

    return prompt


