"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Well-Structured Predictable JSON Schemas for Report Storage
============================================================

WHY:
Consistent, future-proof JSON structure for ALL organizational reports.
Enables API access, dashboard rendering, historical analysis, and trend detection.

WHAT:
Defines schemas for:
- Master reports (comprehensive organizational intelligence)
- Persona reports (wellness, tech, safety, energy, etc.)
- Version control for schema evolution
- Validation functions

HOW:
Each schema defines:
- Schema version (for future compatibility)
- Timestamp (midnight of report day)
- Report type (daily, weekly, monthly)
- Executive summary
- Top priorities (by location)
- Trends and patterns
- Resolutions and wins
- Metadata (counts, statistics)
"""

import datetime
import pytz

# Schema versions (increment when structure changes)
SCHEMA_VERSION_MASTER = "1.0.0"
SCHEMA_VERSION_PERSONA = "1.0.0"

# Report types
REPORT_TYPE_DAILY = "daily"
REPORT_TYPE_WEEKLY = "weekly"
REPORT_TYPE_MONTHLY = "monthly"


def create_master_report_schema(
    timestamp_ms,
    report_type=REPORT_TYPE_DAILY,
    executive_summary=None,
    top_priorities=None,
    trends=None,
    resolutions=None,
    metadata=None
):
    """
    Create master report JSON schema (stored in org_report_master state variable)
    
    :param timestamp_ms: Report timestamp (midnight)
    :param report_type: daily | weekly | monthly
    :param executive_summary: Executive summary dict
    :param top_priorities: List of priority location dicts
    :param trends: List of trend dicts
    :param resolutions: List of resolution dicts
    :param metadata: Metadata dict
    :return: Master report dict
    """
    return {
        "schema_version": SCHEMA_VERSION_MASTER,
        "timestamp_ms": timestamp_ms,
        "report_date": _format_report_date(timestamp_ms),
        "report_type": report_type,
        
        "executive_summary": executive_summary or {
            "total_locations_with_concerns": 0,
            "critical_locations": 0,
            "warning_locations": 0,
            "top_concern": None,
            "summary_text": ""
        },
        
        "top_priorities": top_priorities or [],
        
        "trends": trends or [],
        
        "resolutions": resolutions or [],
        
        "metadata": metadata or {
            "total_reports_processed": 0,
            "total_locations": 0,
            "critical_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "category_counts": {},
            "generation_timestamp_ms": timestamp_ms,
            "processing_duration_ms": 0,
        }
    }


def create_priority_location(
    location_id,
    location_name,
    primary_concerns,
    severity="warning",
    days_active=1,
    categories=None,
    recommended_actions=None,
    specific_data=None,
    context=None
):
    """
    Create priority location dict
    
    :param location_id: Location ID
    :param location_name: Location name
    :param primary_concerns: List of concern strings
    :param severity: critical | warning | info
    :param days_active: Days this has been active
    :param categories: List of category strings (wellness, it, etc.)
    :param recommended_actions: List of recommended action strings
    :param specific_data: Dict of specific metrics
    :param context: Additional context string
    :return: Priority location dict
    """
    return {
        "location_id": location_id,
        "location_name": location_name,
        "primary_concerns": primary_concerns if isinstance(primary_concerns, list) else [primary_concerns],
        "severity": severity,
        "days_active": days_active,
        "categories": categories or [],
        "recommended_actions": recommended_actions or [],
        "specific_data": specific_data or {},
        "context": context or ""
    }


def create_trend(category, description, locations_affected, direction="stable", specific_metrics=None):
    """
    Create trend dict
    
    :param category: wellness | it | safety | energy
    :param description: Trend description string
    :param locations_affected: Number of locations affected
    :param direction: improving | declining | stable
    :param specific_metrics: Dict of specific metrics
    :return: Trend dict
    """
    return {
        "category": category,
        "description": description,
        "locations_affected": locations_affected,
        "direction": direction,
        "specific_metrics": specific_metrics or {}
    }


def create_resolution(location_id, location_name, description, days_to_resolve, category=None):
    """
    Create resolution dict
    
    :param location_id: Location ID
    :param location_name: Location name
    :param description: Resolution description
    :param days_to_resolve: How many days to resolve
    :param category: wellness | it | safety | energy
    :return: Resolution dict
    """
    return {
        "location_id": location_id,
        "location_name": location_name,
        "description": description,
        "days_to_resolve": days_to_resolve,
        "category": category or "other"
    }


def create_persona_report_schema(
    persona,
    timestamp_ms,
    report_type=REPORT_TYPE_DAILY,
    executive_summary=None,
    priorities=None,
    trends=None,
    resolutions=None,
    metadata=None
):
    """
    Create persona report JSON schema (stored in org_report_{persona} state variable)
    
    Same structure as master report but filtered for specific persona
    
    :param persona: wellness | tech | safety | energy | ceo | cfo | coo
    :param timestamp_ms: Report timestamp (midnight)
    :param report_type: daily | weekly | monthly
    :param executive_summary: Executive summary dict
    :param priorities: List of priority dicts
    :param trends: List of trend dicts
    :param resolutions: List of resolution dicts
    :param metadata: Metadata dict
    :return: Persona report dict
    """
    return {
        "schema_version": SCHEMA_VERSION_PERSONA,
        "persona": persona,
        "timestamp_ms": timestamp_ms,
        "report_date": _format_report_date(timestamp_ms),
        "report_type": report_type,
        
        "executive_summary": executive_summary or {
            "total_locations": 0,
            "critical_count": 0,
            "warning_count": 0,
            "top_concern": None,
            "summary_text": ""
        },
        
        "priorities": priorities or [],
        
        "trends": trends or [],
        
        "resolutions": resolutions or [],
        
        "metadata": metadata or {
            "source_master_report_timestamp_ms": timestamp_ms,
            "total_items_extracted": 0,
            "category_focus": [],
            "generation_timestamp_ms": timestamp_ms,
        }
    }


def _format_report_date(timestamp_ms):
    """
    Format report date as human-readable string
    
    :param timestamp_ms: Timestamp in milliseconds
    :return: Formatted date string (e.g., "Monday, January 1, 2026")
    """
    dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000, tz=pytz.utc)
    
    # Platform-agnostic formatting (no %-d directive which fails on Windows)
    day = dt.day
    month = dt.strftime("%B")
    weekday = dt.strftime("%A")
    year = dt.year
    
    return f"{weekday}, {month} {day}, {year}"


def validate_master_report(report):
    """
    Validate master report schema
    
    :param report: Master report dict
    :return: (is_valid, error_message)
    """
    required_fields = [
        "schema_version",
        "timestamp_ms",
        "report_type",
        "executive_summary",
        "top_priorities",
        "trends",
        "resolutions",
        "metadata"
    ]
    
    for field in required_fields:
        if field not in report:
            return False, f"Missing required field: {field}"
    
    # Validate report_type
    valid_types = [REPORT_TYPE_DAILY, REPORT_TYPE_WEEKLY, REPORT_TYPE_MONTHLY]
    if report["report_type"] not in valid_types:
        return False, f"Invalid report_type: {report['report_type']}"
    
    return True, None


def validate_persona_report(report):
    """
    Validate persona report schema
    
    :param report: Persona report dict
    :return: (is_valid, error_message)
    """
    required_fields = [
        "schema_version",
        "persona",
        "timestamp_ms",
        "report_type",
        "executive_summary",
        "priorities",
        "trends",
        "resolutions",
        "metadata"
    ]
    
    for field in required_fields:
        if field not in report:
            return False, f"Missing required field: {field}"
    
    return True, None


