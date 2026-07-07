"""
Created on December 29, 2025

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Report Signal Module — functions for adding events and generating reports.

See constants.py for all EVENT_TYPE_*, CATEGORY_*, CRITICALITY_*, SENTIMENT_*,
PRIORITY_*, and REPORT_ADDRESS_* definitions.
See README.md for the full architecture guide.
"""

import uuid

from signals.report.constants import (
    CATEGORY_ALERT,
    CRITICALITY_INFO,
    EVENT_TYPE_SCHEMA,
    PROTECTED_REPORT_ADDRESSES,
    SENTIMENT_CONCERN,
)


def get_event_type_prefix(event_type):
    """
    Extract the prefix from an event type.

    :param event_type: Event type string (e.g., "sleep.wakeup")
    :return: Prefix string (e.g., "sleep")
    """
    if event_type and "." in event_type:
        return event_type.split(".")[0]
    return event_type


def get_schema_for_event_type(event_type):
    """
    Get the schema properties for an event type.

    :param event_type: Event type string (e.g., "sleep.wakeup")
    :return: Schema dict or None if not found
    """
    prefix = get_event_type_prefix(event_type)
    return EVENT_TYPE_SCHEMA.get(prefix)


def add_event(
    botengine,
    location_object,
    event_type=None,
    comment=None,
    event_types=None,
    criticality=None,
    timestamp_override_ms=None,
    identifier=None,
    # Legacy parameters for backward compatibility (ignored but accepted)
    section_id=None,
    include_timestamp=None,
):
    """
    Add an event to the report system.

    This is the primary function for microservices to log events that will appear
    in reports. Events are stored in a local cache and synthesized into coherent
    narratives by an LLM at report generation time.

    :param botengine: BotEngine environment
    :param location_object: Location object
    :param event_type: Event type constant (e.g., EVENT_TYPE_SLEEP_WAKEUP)
    :param comment: Text description of the event (required)
    :param event_types: Optional list of event types (for multi-faceted events that span categories)
    :param criticality: Override default criticality from schema (CRITICALITY_INFO, CRITICALITY_WARNING, CRITICALITY_CRITICAL)
    :param timestamp_override_ms: Override event timestamp (defaults to current time)
    :param identifier: Optional identifier for upsert semantics — if an event with this identifier already exists in the cache, it will be replaced; otherwise a new event is created.
    :param section_id: DEPRECATED - use event_type instead (accepted for backward compatibility)
    :param include_timestamp: DEPRECATED - ignored (timestamps always included)
    """
    # Backward compatibility: section_id is an alias for event_type
    if event_type is None and section_id is not None:
        event_type = section_id

    botengine.get_logger(f"{__name__}").debug(">add_event() event_type={} comment={}".format(event_type, comment))

    # Validate event_type
    if event_type is None:
        botengine.get_logger(f"{__name__}").error("<add_event() Missing event_type")
        return

    # Validate comment
    if comment is None:
        botengine.get_logger(f"{__name__}").error("<add_event() Missing comment")
        return

    # Get schema for this event type
    schema = get_schema_for_event_type(event_type)
    if schema is None:
        botengine.get_logger(f"{__name__}").warning("<add_event() Unknown event_type prefix: {}".format(event_type))
        # Still allow the event to be added, just with default properties
        schema = {
            "category": CATEGORY_ALERT,
            "default_criticality": CRITICALITY_INFO,
            "organizational_visibility": False,
            "presentation": {
                "title": get_event_type_prefix(event_type).title(),
                "icon": "info-circle",
                "color": "787F84",
                "weight": 100,
                "description": ""
            }
        }

    # Determine criticality
    if criticality is None:
        criticality = schema.get("default_criticality", CRITICALITY_INFO)

    # Determine timestamp
    timestamp_ms = timestamp_override_ms if timestamp_override_ms else botengine.get_timestamp()

    # Generate event ID
    event_id = str(uuid.uuid4())[:8]

    # Build event content
    content = {
        "event_id": event_id,
        "event_type": event_type,
        "timestamp_ms": timestamp_ms,
        "comment": comment,
        "criticality": criticality,
        "category": schema.get("category", CATEGORY_ALERT),
    }

    # Add identifier if provided (for upsert semantics)
    if identifier is not None:
        content["identifier"] = identifier

    # Add event_types list if provided (for multi-faceted events)
    if event_types:
        content["event_types"] = event_types
    else:
        content["event_types"] = [event_type]

    # Send datastream message to report microservice
    location_object.distribute_datastream_message(
        botengine,
        "report_add_event",
        content,
        internal=True,
        external=False
    )

    # Check if event should be routed to organizational bots
    if schema.get("organizational_visibility", False):
        # Build a full send_org_report()-compatible payload. The report_to_org
        # handler validates for required fields (priority, report_type, sentiment,
        # report_id, summary) — a lightweight 7-field payload would fail silently.
        org_report_id = f"{get_event_type_prefix(event_type)}_{location_object.location_id}_{timestamp_ms}"
        org_content = {
            # Required fields
            "location_id": str(location_object.location_id),
            "location_name": location_object.get_location_name(botengine),
            "timestamp_ms": timestamp_ms,
            "priority": criticality,          # criticality and priority share string values
            "report_type": get_event_type_prefix(event_type),
            "sentiment": SENTIMENT_CONCERN,
            "report_id": org_report_id,
            "summary": comment,
            # Preserve original event details for downstream context
            "context": {
                "event_type": event_type,
                "category": schema.get("category", CATEGORY_ALERT),
                "criticality": criticality,
            },
        }

        location_object.distribute_datastream_message(
            botengine,
            "report_to_org",
            org_content,
            internal=True,
            external=False
        )

    botengine.get_logger(f"{__name__}").debug("<add_event()")


def generate_report(
    botengine,
    location_object,
    start_timestamp_ms,
    end_timestamp_ms,
    report_name,
    time_series_address=None,
):
    """
    Request generation of a report for a specific time window.

    This function sends a datastream message to the reports microservice
    to trigger report generation.

    :param botengine: BotEngine environment
    :param location_object: Location object
    :param start_timestamp_ms: Start of time window (required)
    :param end_timestamp_ms: End of time window (required)
    :param report_name: Report name (e.g., "24hour", "12hour", "custom")
    :param time_series_address: Override time-series address (defaults to "report_{report_name}")
    """
    botengine.get_logger(f"{__name__}").debug(">generate_report() report_name={} start={} end={}".format(
        report_name, start_timestamp_ms, end_timestamp_ms
    ))

    content = {
        "start_timestamp_ms": start_timestamp_ms,
        "end_timestamp_ms": end_timestamp_ms,
        "report_name": report_name,
    }

    if time_series_address:
        content["time_series_address"] = time_series_address

    location_object.distribute_datastream_message(
        botengine,
        "report_generate",
        content,
        internal=True,
        external=False
    )

    botengine.get_logger(f"{__name__}").debug("<generate_report()")


def delete_report(
    botengine,
    location_object,
    report_name,
):
    """
    Delete a custom report.

    Cannot delete protected reports (dailyreport, weeklyreport, monthlyreport).

    :param botengine: BotEngine environment
    :param location_object: Location object
    :param report_name: Report name to delete
    """
    botengine.get_logger(f"{__name__}").debug(">delete_report() report_name={}".format(report_name))

    # Check if protected
    address = f"report_{report_name}" if report_name not in PROTECTED_REPORT_ADDRESSES else report_name
    if address in PROTECTED_REPORT_ADDRESSES:
        botengine.get_logger(f"{__name__}").error("<delete_report() Cannot delete protected report: {}".format(report_name))
        return

    content = {
        "report_name": report_name,
    }

    location_object.distribute_datastream_message(
        botengine,
        "report_delete",
        content,
        internal=True,
        external=False
    )

    botengine.get_logger(f"{__name__}").debug("<delete_report()")


def report_generated(
    botengine,
    location_object,
    report_name,
    report_content,
    time_series_address,
    timestamp_ms,
):
    """
    Notify other microservices that a report has been generated.

    This signal is sent when a report is completed and stored. Other microservices
    (e.g., email, SMS) can listen for this signal to deliver the report to users.

    :param botengine: BotEngine environment
    :param location_object: Location object
    :param report_name: Report name (daily, weekly, monthly, 24hour, 12hour, custom)
    :param report_content: Full report JSON content
    :param time_series_address: Time-series address where report is stored
    :param timestamp_ms: Report timestamp in milliseconds
    """
    botengine.get_logger(f"{__name__}").debug(">report_generated() report_name={} timestamp_ms={}".format(report_name, timestamp_ms))

    content = {
        "report_name": report_name,
        "report_content": report_content,
        "time_series_address": time_series_address,
        "timestamp_ms": timestamp_ms,
    }

    location_object.distribute_datastream_message(
        botengine,
        "report_generated",
        content,
        internal=True,
        external=False
    )

    botengine.get_logger(f"{__name__}").debug("<report_generated()")


def send_org_report(
    botengine,
    location_object,
    priority,
    report_type,
    sentiment,
    summary,
    short_description=None,
    long_description=None,
    concerns=None,
    context=None,
    recommended_action=None,
    report_id=None,
    previous_report_id=None,
    severity_rank=None,
    days_active=None,
    scores=None
):
    """
    Send a report to the organizational bot for AI Chief of Staff processing.
    See README.md for full schema, examples, and routing architecture.

    :param botengine: BotEngine environment
    :param location_object: Location object
    :param priority: PRIORITY_CRITICAL | PRIORITY_WARNING | PRIORITY_INFO
    :param report_type: Category string for org routing (e.g., "stability", "infrastructure")
    :param sentiment: SENTIMENT_CONCERN | SENTIMENT_RESOLUTION | SENTIMENT_UPDATE | SENTIMENT_CELEBRATION | SENTIMENT_SUMMARY
    :param summary: One-sentence executive summary (required for LLM processing)
    :param short_description: One-sentence short description
    :param long_description: Detailed narrative
    :param concerns: list[str] of specific issues in natural language
    :param context: dict of supporting data for LLM interpretation
    :param recommended_action: Suggested next steps for caregiving staff
    :param report_id: Unique ID for lifecycle tracking (auto-generated if omitted)
    :param previous_report_id: Reference to original concern report (for resolutions)
    :param severity_rank: float 0-100 for sorting without LLM
    :param days_active: How many days this concern has been active
    :param scores: dict of relevant numerical scores (wellness, stability, etc.)
    """
    botengine.get_logger(f"{__name__}").info(
        f">send_org_report() location={location_object.location_id} "
        f"type={report_type} priority={priority} sentiment={sentiment}"
    )

    # Generate report_id if not provided
    if report_id is None:
        report_id = f"{report_type}_{sentiment}_{location_object.location_id}_{botengine.get_timestamp()}"

    # Build report content
    content = {
        # REQUIRED FIELDS (for routing at org level)
        "location_id": location_object.location_id,
        "location_name": location_object.get_location_name(botengine),
        "timestamp_ms": botengine.get_timestamp(),
        "priority": priority,
        "report_type": report_type,
        "sentiment": sentiment,
        "report_id": report_id,
        "summary": summary,
    }

    # Add optional natural language fields
    if short_description is not None:
        content["short_description"] = short_description

    if long_description is not None:
        content["long_description"] = long_description

    if concerns is not None:
        content["concerns"] = concerns if isinstance(concerns, list) else [concerns]

    if context is not None:
        content["context"] = context

    if recommended_action is not None:
        content["recommended_action"] = recommended_action

    # Add optional programmatic fields
    if previous_report_id is not None:
        content["previous_report_id"] = previous_report_id

    if severity_rank is not None:
        content["severity_rank"] = severity_rank

    if days_active is not None:
        content["days_active"] = days_active

    if scores is not None:
        content["scores"] = scores

    # Send internally for location-level caching (org bot pulls on demand)
    location_object.distribute_datastream_message(
        botengine,
        "report_to_org",
        content,
        internal=True,
        external=False
    )

    botengine.get_logger(f"{__name__}").info(
        f"<send_org_report() Sent {report_type} report (priority={priority})"
    )
