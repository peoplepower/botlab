"""
Created on March 13, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Constants for the trends_report organization microservice.
"""

# Data request reference
DATA_REQUEST_REFERENCE_TRENDS = "trends_report_location_states"

# State variable for in-progress report
STATE_VAR_REPORT_IN_PROGRESS = "trends_report_in_progress"

# LLM reference for routing responses
LLM_REFERENCE_TRENDS_REPORT = "trends_report_enhancement"

# LLM enhancement task types
TASK_ANALYSIS_OVERVIEW = "analysis_overview"
TASK_INDIVIDUAL_ANALYSIS = "individual_analysis"
TASK_REVIEW_SUMMARY = "review_summary"

# Data request timeout/retry constants
DATA_REQUEST_TIMEOUT_S = 10
MAX_DATA_REQUEST_RETRIES = 6

# Trend state variable names (matching signals/trends.py)
TRENDS_NOW_NAME = "trends"
TRENDS_METADATA_NAME = "trends_metadata"

# Trend category labels for display
TREND_CATEGORY_LABELS = {
    "category.sleep": "Sleep",
    "category.bathroom": "Bathroom",
    "category.activity": "Activity",
    "category.social": "Social",
    "category.stability": "Stability",
    "category.energy": "Energy",
    "category.ambient": "Ambient",
    "category.care": "Care",
    "category.health": "Health",
    "category.summary": "Summary",
    "category.other": "Other",
}

# Z-score thresholds for alerts/health classification
ZSCORE_CONCERNING = 1.5
ZSCORE_CRITICAL = 2.5

# Maximum locations that receive full individual analysis (LLM + charts)
MAX_DETAILED_LOCATIONS = 20

# LLM configuration
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.2

# Max tokens per task type
LLM_MAX_TOKENS_OVERVIEW = 300
LLM_MAX_TOKENS_INDIVIDUAL = 200
LLM_MAX_TOKENS_REVIEW = 400

# Shared system prompt preamble (static, cacheable)
SYSTEM_PROMPT_BASE = (
    "You are a healthcare data analyst for an ambient monitoring platform "
    "that serves senior living communities. The platform uses non-wearable "
    "IoT sensors (motion, door, and environmental sensors) placed throughout "
    "residences to passively monitor daily patterns without cameras or "
    "wearables.\n\n"
    "WHAT THE DATA REPRESENTS:\n"
    "- Each 'location' is a single residence (apartment or home) with one "
    "or more occupants\n"
    "- 'Trends' are rolling 30-day behavioral metrics computed daily from "
    "sensor data (e.g., bedtime, bathroom visit count, activity score)\n"
    "- 'Z-score' measures how many standard deviations the current value is "
    "from the resident's own 30-day rolling average. A z-score of 0 means "
    "normal; |z| >= 1.5 is concerning; |z| >= 2.5 is critical\n"
    "- 'Categories' group related trends: Sleep, Bathroom, Activity, Social, "
    "Stability, Energy, Ambient, Care, Health\n\n"
    "AUDIENCE: Organization administrators and care coordinators who oversee "
    "multiple senior living locations.\n\n"
    "CRITICAL: Only reference data explicitly provided. Never invent "
    "statistics, trend names, locations, or patterns not present in the "
    "data. If data is limited, say so rather than fabricating details."
)
