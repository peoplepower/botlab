"""
Created on November 20, 2019

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

DEPRECATED: This module is deprecated. Please use signals.report instead.
===========================================================================

This module now serves as a backwards compatibility shim that redirects all calls
to the new signals.report module. Third-party code that still uses this module
will continue to work, but should migrate to signals.report for new development.

Migration Guide:
    OLD: import signals.dailyreport as dailyreport
         dailyreport.add_entry(botengine, location, dailyreport.SECTION_ID_SLEEP, comment="Went to sleep")
    
    NEW: import signals.report as report
         report.add_event(botengine, location, report.EVENT_TYPE_SLEEP_BEDTIME, comment="Went to sleep")
"""

import signals.report as report

# ==============================================================================
# DEPRECATED SECTION ID CONSTANTS
# ==============================================================================
# These constants are mapped to event_type prefixes in the new system.
# They are preserved here for backwards compatibility only.

SECTION_ID_WELLNESS = "wellness"
SECTION_ID_ALERTS = "alerts"
SECTION_ID_NOTES = "notes"
SECTION_ID_TASKS = "tasks"
SECTION_ID_SLEEP = "sleep"
SECTION_ID_ACTIVITIES = "activities"
SECTION_ID_MEALS = "meals"
SECTION_ID_MEDICATION = "medication"
SECTION_ID_BATHROOM = "bathroom"
SECTION_ID_SOCIAL = "social"
SECTION_ID_MEMORIES = "memories"
SECTION_ID_SYSTEM = "system"

# Section Keys (preserved for backwards compatibility)
SECTION_KEY_ID = "id"
SECTION_KEY_WEIGHT = "weight"
SECTION_KEY_TITLE = "title"
SECTION_KEY_DESCRIPTION = "description"
SECTION_KEY_ICON = "icon"
SECTION_KEY_COLOR = "color"
SECTION_KEY_ITEMS = "items"
SECTION_KEY_TREND_IDS = "trend_ids"
SECTION_KEY_INSIGHT_IDS = "insight_ids"

# Report Status (preserved for backwards compatibility)
REPORT_STATUS_CREATED = 0
REPORT_STATUS_COMPLETED = 1

# ==============================================================================
# SECTION ID TO EVENT TYPE MAPPING
# ==============================================================================
# Maps legacy section_id values to the appropriate event_type in the new system

_SECTION_TO_EVENT_TYPE = {
    SECTION_ID_SLEEP: report.EVENT_TYPE_SLEEP_SUMMARY,
    SECTION_ID_ACTIVITIES: report.EVENT_TYPE_ACTIVITY_SUMMARY,
    SECTION_ID_MEALS: report.EVENT_TYPE_MEALS_PREPARED,
    SECTION_ID_MEDICATION: report.EVENT_TYPE_MEDICATION_TAKEN,
    SECTION_ID_BATHROOM: report.EVENT_TYPE_BATHROOM_VISIT,
    SECTION_ID_SOCIAL: report.EVENT_TYPE_SOCIAL_VISITOR,
    SECTION_ID_ALERTS: report.EVENT_TYPE_ALERT_WARNING,
    SECTION_ID_WELLNESS: report.EVENT_TYPE_HEALTH_WELLNESS_SCORE,
    SECTION_ID_TASKS: report.EVENT_TYPE_TASK_ADDED,
    SECTION_ID_NOTES: report.EVENT_TYPE_ALERT_INFO,
    SECTION_ID_SYSTEM: report.EVENT_TYPE_IT_DEVICE_OFFLINE,
    SECTION_ID_MEMORIES: report.EVENT_TYPE_CARE_CHECK_IN,
}


def add_entry(
    botengine,
    location_object,
    section_id,
    comment=None,
    subtitle=None,
    identifier=None,
    include_timestamp=False,
    timestamp_override_ms=None,
):
    """
    DEPRECATED: Use report.add_event() instead.
    
    Add a section and bullet point the current daily report.
    This function now redirects to report.add_event() for backwards compatibility.
    
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param section_id: Section ID like dailyreport.SECTION_ID_ACTIVITIES
    :param comment: Comment like "Woke up."
    :param subtitle: Subtitle comment (now combined with comment)
    :param identifier: Optional identifier
    :param include_timestamp: True to include a timestamp (handled by new system)
    :param timestamp_override_ms: Optional timestamp override
    """
    # Map section_id to event_type
    event_type = _SECTION_TO_EVENT_TYPE.get(section_id, report.EVENT_TYPE_ALERT_INFO)
    
    # Combine comment and subtitle if both present
    full_comment = comment
    if subtitle and comment:
        full_comment = f"{comment} - {subtitle}"
    elif subtitle:
        full_comment = subtitle
    
    # If no comment provided, this was likely a delete operation - ignore
    if not full_comment:
        return
    
    # Call the new report.add_event()
    report.add_event(
        botengine,
        location_object,
        event_type=event_type,
        comment=full_comment,
        timestamp_override_ms=timestamp_override_ms,
        identifier=identifier,
    )


def add_weekly_entry(
    botengine,
    location_object,
    section_id,
    comment=None,
    subtitle=None,
    identifier=None,
    include_timestamp=False,
    timestamp_override_ms=None,
):
    """
    DEPRECATED: Use report.add_event() instead.
    
    Add a section and bullet point to the current weekly report.
    This function now redirects to report.add_event() for backwards compatibility.
    """
    # Weekly entries now go through the same add_event pathway
    # The report microservice handles time-based grouping automatically
    add_entry(
        botengine,
        location_object,
        section_id,
        comment=comment,
        subtitle=subtitle,
        identifier=identifier,
        include_timestamp=include_timestamp,
        timestamp_override_ms=timestamp_override_ms,
    )


def add_monthly_entry(
    botengine,
    location_object,
    section_id,
    comment=None,
    subtitle=None,
    identifier=None,
    include_timestamp=False,
    timestamp_override_ms=None,
):
    """
    DEPRECATED: Use report.add_event() instead.
    
    Add a section and bullet point to the current monthly report.
    This function now redirects to report.add_event() for backwards compatibility.
    """
    # Monthly entries now go through the same add_event pathway
    # The report microservice handles time-based grouping automatically
    add_entry(
        botengine,
        location_object,
        section_id,
        comment=comment,
        subtitle=subtitle,
        identifier=identifier,
        include_timestamp=include_timestamp,
        timestamp_override_ms=timestamp_override_ms,
    )


def report_status_updated(
    botengine, location_object, report_data, status=REPORT_STATUS_CREATED, metadata=None
):
    """
    DEPRECATED: The new report system handles status updates internally.
    
    This function is preserved for backwards compatibility but does nothing
    as the new report microservice manages report lifecycle internally.
    
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param report_data: Daily Report json object
    :param status: Report status
    :param metadata: Daily Report metadata
    """
    # The new report system handles this internally
    # This function is kept for backwards compatibility with code that may call it
    botengine.get_logger(f"{__name__}").debug(
        "report_status_updated() is deprecated - report system handles status internally"
    )
    pass


def set_section_config(botengine, location_object, config):
    """
    DEPRECATED: Section configuration is now handled by the EVENT_TYPE_SCHEMA in signals.report.
    
    This function is preserved for backwards compatibility but does nothing.
    Section presentation (title, icon, color, weight) is now determined by the
    event_type prefix in the EVENT_TYPE_SCHEMA.
    
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param config: Section configuration (ignored)
    """
    # The new report system uses EVENT_TYPE_SCHEMA for presentation
    # This function is kept for backwards compatibility
    botengine.get_logger(f"{__name__}").debug(
        "set_section_config() is deprecated - use EVENT_TYPE_SCHEMA in signals.report instead"
    )
    pass
