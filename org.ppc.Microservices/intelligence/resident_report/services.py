"""
Created on May 5, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Constants for the resident_report organization microservice.
"""

# Data request reference
DATA_REQUEST_REFERENCE_RESIDENT = "resident_report_location_states"

# State variable for in-progress report
STATE_VAR_REPORT_IN_PROGRESS = "resident_report_in_progress"

# LLM reference for routing the executive summary response
LLM_REFERENCE_RESIDENT_REPORT = "resident_report_executive_summary"

# LLM enhancement task type (single task: executive summary)
TASK_EXECUTIVE_SUMMARY = "executive_summary"

# Data request timeout/retry constants
DATA_REQUEST_TIMEOUT_S = 10
MAX_DATA_REQUEST_RETRIES = 6

# Per-location state name written by location_reports_resident_microservice
STATE_RESIDENT_REPORT = "resident_report"

# Wellness score thresholds for row highlighting / criticality sorting
WELLNESS_SCORE_CONCERNING = 50

# Notification categories property reused from location_reports_resident_microservice
NOTIFICATION_CATEGORIES_PROPERTY = "RESIDENT_REPORT_NOTIFICATION_CATEGORIES"

# LLM configuration
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS_SUMMARY = 400

# Score categories rendered in the per-resident detail page
SCORE_CATEGORIES = [
    ("sleep", "Sleep"),
    ("bathroom", "Bathroom"),
    ("stability", "Stability"),
    ("social", "Social"),
    ("mobility", "Mobility"),
]

# Shared system prompt preamble (static, cacheable)
SYSTEM_PROMPT_BASE = (
    "You are a healthcare data analyst summarizing a daily roster of "
    "resident wellness reports for senior living organization "
    "administrators. The platform produces a per-resident summary each day "
    "covering wellness score, falls, bathroom activity, and a journal "
    "narrative; this report aggregates those summaries across all "
    "residents in the organization.\n\n"
    "WHAT THE DATA REPRESENTS:\n"
    "- Each resident lives in a single location (apartment or home) "
    "monitored by ambient (non-wearable) sensors\n"
    "- 'Wellness score' is a 0-100 daily composite; below 50 is "
    "concerning\n"
    "- 'Falls' are detected fall events from radar / motion devices in "
    "the resident's home today\n"
    "- 'Categories' (sleep, bathroom, stability, social, mobility) are "
    "today's individual sub-scores feeding the wellness score\n"
    "- 'Journal' is a short narrative describing the resident's day\n\n"
    "AUDIENCE: Organization administrators and care coordinators who "
    "oversee multiple senior living residents.\n\n"
    "CRITICAL: Only reference data explicitly provided. Never invent "
    "statistics, names, falls, or events not present in the data. "
    "Never identify any individual resident by name."
)
