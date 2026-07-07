"""
Created on April 6, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Constants for the device_analysis organization microservice.
"""

# Data request references
DATA_REQUEST_REFERENCE_DEVICES = "device_analysis_devices"
DATA_REQUEST_REFERENCE_PARAMS = "device_analysis_params"

# State variable for in-progress analysis
STATE_VAR_ANALYSIS_IN_PROGRESS = "device_analysis_in_progress"

# LLM reference for routing responses
LLM_REFERENCE_DEVICE_ANALYSIS = "device_analysis_llm"

# LLM enhancement task types (3 max)
TASK_DEVICE_OVERVIEW = "device_overview"
TASK_PARAMETER_INSIGHTS = "parameter_insights"
TASK_RECOMMENDATIONS = "recommendations"

# Data request timeout/retry constants
DATA_REQUEST_TIMEOUT_S = 10
MAX_DATA_REQUEST_RETRIES = 6

# Timer argument types
TIMER_TYPE_DATA_REQUEST_TIMEOUT = "data_request_timeout"

# Analysis phase names
PHASE_DEVICES = "devices"
PHASE_PARAMETERS = "parameters"
PHASE_ANALYSIS = "analysis"

# LLM configuration
LLM_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.2
LLM_MAX_TOKENS_OVERVIEW = 400
LLM_MAX_TOKENS_INSIGHTS = 400
LLM_MAX_TOKENS_RECOMMENDATIONS = 300

# 7-day lookback for parameter data
PARAM_LOOKBACK_DAYS = 7

# HIPAA-compliant system prompt
SYSTEM_PROMPT = (
    "You are a product analytics specialist for an IoT device deployment platform "
    "that serves senior living communities. You analyze device parameter data across "
    "multiple locations to identify patterns, anomalies, and operational insights.\n\n"
    "WHAT THE DATA REPRESENTS:\n"
    "- Each 'location' is a deployment site identified by a numeric ID\n"
    "- 'device_type' is a numeric identifier for a product category\n"
    "- 'Parameters' are named measurements reported by devices "
    "(e.g., motionStatus, state, currentLevel)\n"
    "- Statistics are aggregated across all locations in the organization\n\n"
    "AUDIENCE: Organization administrators who manage device fleets.\n\n"
    "CRITICAL RULES:\n"
    "- Only reference data explicitly provided. Never invent statistics.\n"
    "- Use location IDs only, never names or addresses.\n"
    "- Do not include any personally identifiable information.\n"
    "- Do not speculate about the identity or health of any individual.\n"
    "- If data is limited, say so rather than fabricating details."
)
