"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Collection name constants for the report_aggregator microservice.
Following the pattern established across microservices to keep collection names consistent.
"""

# Bot variable keys for report storage
COLLECTION_ORG_REPORT_CACHE = "org_report_cache"  # DEPRECATED: Reports now pulled from locations. Kept for legacy cache cleanup.
COLLECTION_ORG_REPORT_MASTER = "org_report_master"  # Comprehensive daily master reports (overwritten each run)

COLLECTION_ORG_REPORT_WELLNESS = "org_report_wellness"  # Health & Wellness persona reports (overwritten each run)
COLLECTION_ORG_REPORT_TECH = "org_report_tech"  # IT Infrastructure persona reports (overwritten each run)

# State variable address for org-bound reports cached at each child location.
# Must match the address used by location_reports_microservice.AGGREGATED_REPORT_STATE_ADDRESS.
LOCATION_AGGREGATED_REPORT_STATE_ADDRESS = "aggregated_report"

# Schedule IDs
SCHEDULE_DAILY_MASTER_REPORT = "DAILY_MASTER_REPORT"  # Daily at 6 AM - checks if Sunday for weekly synthesis

# LLM references for tracking async responses
LLM_REFERENCE_MASTER_REPORT = "master_report"  # Master report generation
LLM_REFERENCE_WELLNESS_EXTRACT = "wellness_extract"  # Wellness persona extraction
LLM_REFERENCE_TECH_EXTRACT = "tech_extract"  # Tech persona extraction
LLM_REFERENCE_WEEKLY_SYNTHESIS = "weekly_synthesis"  # Weekly synthesis

