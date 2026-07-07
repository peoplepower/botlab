"""
Created on April 27, 2026

Fall Report Builder - deterministic report generation from fall state records.

Produces:
- CSV string with one row per fall event
- HTML email summary with statistics

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Claude
"""

import csv
import io
from datetime import datetime, timezone

# FallConfirmation enum values (mirrors signals/falls/falls.py)
CONFIRMATION_NAMES = {
    0: "Unconfirmed",
    1: "Confirmed",
    2: "True Positive",
    3: "False Positive",
    4: "True Negative",
    5: "False Negative",
}

# Device type mapping for known fall-detection devices
DEVICE_TYPE_NAMES = {
    10072: "Vayyar Care (Radar)",
    10076: "Pontosense SilverShield (Radar)",
    10078: "Axend Assure (Radar)",
    10080: "Nobi (Radar)",
    4001: "MPER (Wearable)",
    4002: "MPER (Wearable)",
}

# Room/goal_id mapping
ROOM_NAMES = {
    0: "Bedroom",
    1: "Bathroom",
    2: "Living Room",
    3: "Kitchen",
    5: "Office",
}

# CSV column definitions
CSV_COLUMNS = [
    "Location ID",
    "Location Name",
    "Device ID",
    "Device Description",
    "Device Type",
    "Room",
    "Status",
    "Detection Time",
    "Recovery Time",
    "Detection Duration (s)",
    "Alert Created",
    "Notified Residents",
    "Notified Supporters",
    "Notified Admins",
    "Notified ECC",
    "First Response",
    "Alert Resolved",
    "Alert Resolution Reason",
    "Alert Duration (s)",
    "Feedback",
    "Label",
    "Test Only",
]


def _format_timestamp_ms(ts_ms):
    """
    Format a millisecond timestamp to ISO-8601 string, or return empty string if None.
    """
    if ts_ms is None:
        return ""
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OSError, OverflowError):
        return ""


def _get_device_type_name(device_type):
    """
    Map device_type int to a human-readable name.
    """
    if device_type is None:
        return ""
    return DEVICE_TYPE_NAMES.get(device_type, "Device Type {}".format(device_type))


def _is_radar_device(device_type):
    """
    Determine if a device type is a radar device.
    """
    return device_type in (10072, 10076, 10078, 10080)


def _format_duration_s(duration_ms):
    """
    Format a millisecond duration to seconds, or return empty string if None.
    """
    if duration_ms is None:
        return ""
    try:
        return str(round(duration_ms / 1000.0))
    except (ValueError, TypeError):
        return ""


def build_fall_report(fall_records, start_date_ms, end_date_ms, location_names):
    """
    Build a CSV report and summary statistics from fall records.

    :param fall_records: List of fall record dicts, each enriched with 'location_id' and 'start_time_ms'
    :param start_date_ms: Report start date in milliseconds
    :param end_date_ms: Report end date in milliseconds
    :param location_names: Dict mapping location_id (int) -> location name (str)
    :return: Tuple of (csv_string, summary_dict)
    """
    # Sort by start_time_ms descending (most recent first)
    fall_records.sort(key=lambda r: r.get("start_time_ms", 0), reverse=True)

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)

    # Track summary statistics
    total_falls = len(fall_records)
    total_with_alert = 0
    total_radar = 0
    total_mper = 0
    confirmation_counts = {}
    response_times_ms = []
    alert_durations_ms = []

    for record in fall_records:
        location_id = record.get("location_id")
        location_name = location_names.get(int(location_id), "Location {}".format(location_id)) if location_id else ""
        device_id = record.get("device_id", "")
        device_desc = record.get("device_desc", "")
        device_type = record.get("device_type")
        device_type_name = _get_device_type_name(device_type)
        goal_id = record.get("goal_id")
        room_name = ROOM_NAMES.get(goal_id, "") if goal_id is not None else ""

        confirmed = record.get("confirmed")
        status_name = CONFIRMATION_NAMES.get(confirmed, "Unknown") if confirmed is not None else "No Status"

        start_time_ms = record.get("start_time_ms")
        end_time_ms = record.get("end_time_ms")
        duration_ms = record.get("duration_ms")

        alert_start_ms = record.get("alert_start_ms")
        notified_residents_ms = record.get("notified_residents_ms")
        notified_supporters_ms = record.get("notified_supporters_ms")
        notified_admins_ms = record.get("notified_admins_ms")
        notified_ecc_ms = record.get("notified_ecc_ms")
        first_response_ms = record.get("first_response_ms")
        alert_end_ms = record.get("alert_end_ms")
        alert_reason = record.get("alert_reason", "")
        alert_duration_ms = record.get("alert_duration_ms")
        feedback_type = record.get("feedback_type", "")
        label = record.get("label", "")
        test = record.get("test", True)

        # Track statistics
        if alert_start_ms is not None:
            total_with_alert += 1

        if device_type is not None:
            if _is_radar_device(device_type):
                total_radar += 1
            else:
                total_mper += 1

        if confirmed is not None:
            confirmation_counts[status_name] = confirmation_counts.get(status_name, 0) + 1

        # Calculate response time: first notification to first response
        notification_time = notified_residents_ms or notified_supporters_ms or notified_admins_ms
        if notification_time and first_response_ms:
            response_times_ms.append(first_response_ms - notification_time)

        if alert_duration_ms is not None:
            alert_durations_ms.append(alert_duration_ms)

        writer.writerow([
            location_id or "",
            location_name,
            device_id,
            device_desc,
            device_type_name,
            room_name,
            status_name,
            _format_timestamp_ms(start_time_ms),
            _format_timestamp_ms(end_time_ms),
            _format_duration_s(duration_ms),
            _format_timestamp_ms(alert_start_ms),
            _format_timestamp_ms(notified_residents_ms),
            _format_timestamp_ms(notified_supporters_ms),
            _format_timestamp_ms(notified_admins_ms),
            _format_timestamp_ms(notified_ecc_ms),
            _format_timestamp_ms(first_response_ms),
            _format_timestamp_ms(alert_end_ms),
            alert_reason,
            _format_duration_s(alert_duration_ms),
            feedback_type,
            label,
            "Yes" if test else "No",
        ])

    csv_content = output.getvalue()
    output.close()

    # Build summary
    avg_response_s = (
        round(sum(response_times_ms) / len(response_times_ms) / 1000.0)
        if response_times_ms
        else None
    )
    avg_alert_duration_s = (
        round(sum(alert_durations_ms) / len(alert_durations_ms) / 1000.0)
        if alert_durations_ms
        else None
    )

    summary = {
        "total_falls": total_falls,
        "total_with_alert": total_with_alert,
        "total_radar": total_radar,
        "total_mper": total_mper,
        "confirmation_counts": confirmation_counts,
        "avg_response_time_s": avg_response_s,
        "avg_alert_duration_s": avg_alert_duration_s,
        "start_date_ms": start_date_ms,
        "end_date_ms": end_date_ms,
    }

    return csv_content, summary


def build_email_html(summary, start_date_ms, end_date_ms):
    """
    Build an HTML email body summarizing the fall report.

    :param summary: Summary dict from build_fall_report()
    :param start_date_ms: Report start date
    :param end_date_ms: Report end date
    :return: HTML string
    """
    start_str = _format_timestamp_ms(start_date_ms)
    end_str = _format_timestamp_ms(end_date_ms)

    total = summary.get("total_falls", 0)
    total_alert = summary.get("total_with_alert", 0)
    total_radar = summary.get("total_radar", 0)
    total_mper = summary.get("total_mper", 0)
    confirmation_counts = summary.get("confirmation_counts", {})
    avg_response = summary.get("avg_response_time_s")
    avg_duration = summary.get("avg_alert_duration_s")

    # Build confirmation breakdown rows
    confirmation_rows = ""
    for status, count in sorted(confirmation_counts.items()):
        confirmation_rows += "<tr><td style='padding: 4px 12px;'>{}</td><td style='padding: 4px 12px; text-align: right;'>{}</td></tr>\n".format(
            status, count
        )

    html = """
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <h2 style="color: #333;">Fall Report</h2>
    <p style="color: #666;">{start} &mdash; {end}</p>

    <h3 style="color: #333; border-bottom: 1px solid #ddd; padding-bottom: 8px;">Summary</h3>
    <table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
        <tr><td style="padding: 4px 12px; font-weight: bold;">Total Fall Events</td><td style="padding: 4px 12px; text-align: right;">{total}</td></tr>
        <tr><td style="padding: 4px 12px; font-weight: bold;">Falls with Alert Created</td><td style="padding: 4px 12px; text-align: right;">{total_alert}</td></tr>
        <tr><td style="padding: 4px 12px; font-weight: bold;">Radar Device Falls</td><td style="padding: 4px 12px; text-align: right;">{total_radar}</td></tr>
        <tr><td style="padding: 4px 12px; font-weight: bold;">MPER (Wearable) Falls</td><td style="padding: 4px 12px; text-align: right;">{total_mper}</td></tr>
    </table>

    <h3 style="color: #333; border-bottom: 1px solid #ddd; padding-bottom: 8px;">Confirmation Status Breakdown</h3>
    <table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
        {confirmation_rows}
    </table>

    <h3 style="color: #333; border-bottom: 1px solid #ddd; padding-bottom: 8px;">Response Metrics</h3>
    <table style="border-collapse: collapse; width: 100%; margin-bottom: 16px;">
        <tr><td style="padding: 4px 12px; font-weight: bold;">Avg. Response Time</td><td style="padding: 4px 12px; text-align: right;">{avg_response}</td></tr>
        <tr><td style="padding: 4px 12px; font-weight: bold;">Avg. Alert Duration</td><td style="padding: 4px 12px; text-align: right;">{avg_duration}</td></tr>
    </table>

    <p style="color: #999; font-size: 12px;">Full details are attached as a CSV file.</p>
</div>
""".format(
        start=start_str,
        end=end_str,
        total=total,
        total_alert=total_alert,
        total_radar=total_radar,
        total_mper=total_mper,
        confirmation_rows=confirmation_rows if confirmation_rows else "<tr><td style='padding: 4px 12px; color: #999;'>No confirmation data available</td></tr>",
        avg_response="{} seconds".format(avg_response) if avg_response is not None else "N/A",
        avg_duration="{} seconds".format(avg_duration) if avg_duration is not None else "N/A",
    )

    return html
