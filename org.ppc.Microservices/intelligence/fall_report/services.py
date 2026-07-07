"""
Fall Report service constants.
"""

# Data request reference for querying falls across locations
DATA_REQUEST_REFERENCE_FALLS = "fall_report_location_states"

# Bot variable key for in-progress report data
STATE_VAR_REPORT_IN_PROGRESS = "fall_report_in_progress"

# Timeout/retry configuration for async data requests
DATA_REQUEST_TIMEOUT_S = 10
MAX_DATA_REQUEST_RETRIES = 6

# State variable name matching FALLS_TIMESERIES_STATE_NAME in signals/falls
FALLS_STATE_NAME = "falls"
