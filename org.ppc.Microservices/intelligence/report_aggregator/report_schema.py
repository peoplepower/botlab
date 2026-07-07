"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Unified Report Schema for Organization-Level Reports
====================================================

This schema defines a consistent, future-proof JSON structure that works for
ALL personas (wellness, tech, safety, energy, CEO, CFO, COO, custom, etc.)

CRITICAL: The LLM outputs STRUCTURED DATA, not HTML. Python code handles formatting.

LLM Responsibility:
- Analyze raw reports
- Identify critical issues
- Prioritize locations needing attention
- Extract key metrics and trends
- Provide actionable recommendations

Code Responsibility:
- Format LLM output into HTML for emails
- Apply color coding based on criticality
- Generate email content from structured data
"""

# Report Schema Version
SCHEMA_VERSION = "1.0"


def create_report_from_llm_output(persona, title, subtitle, llm_data, period="daily"):
    """
    Convert LLM structured output into final report format
    
    :param persona: Persona identifier
    :param title: Report title
    :param subtitle: Report subtitle
    :param llm_data: Structured data from LLM (dict)
    :param period: Report period
    :return: Report dict ready for storage/email
    """
    report = {
        "schema_version": SCHEMA_VERSION,
        "persona": persona,
        "title": title,
        "subtitle": subtitle,
        "period": period,
        "llm_data": llm_data,  # Preserve original LLM output
        "sections": _format_sections_for_email(llm_data, persona)
    }
    
    return report


def _format_sections_for_email(llm_data, persona):
    """
    Format LLM structured data into email-ready sections
    
    :param llm_data: Structured data from LLM
    :param persona: Persona type for appropriate formatting
    :return: List of section dicts with formatted content
    """
    sections = []
    
    # Executive Summary Section
    if "executive_summary" in llm_data:
        summary_text = _format_executive_summary(llm_data["executive_summary"])
        sections.append({
            "title": "Executive Summary",
            "icon": "clipboard-list",
            "color": "694fee",
            "content": [summary_text]
        })
    
    # Top Priorities Section
    if "top_priorities" in llm_data:
        priority_items = [
            _format_priority_item(item, persona)
            for item in llm_data["top_priorities"]
        ]
        
        color = "D0021B" if any(p.get("severity") == "critical" for p in llm_data["top_priorities"]) else "F5A623"
        
        sections.append({
            "title": "Top Priorities - Action Needed Today",
            "icon": "exclamation-triangle",
            "color": color,
            "content": priority_items
        })
    
    # Trends Section
    if "trends" in llm_data:
        trend_items = [_format_trend_item(trend) for trend in llm_data["trends"]]
        sections.append({
            "title": "Population Trends" if persona == "wellness" else "Infrastructure Trends",
            "icon": "chart-line",
            "color": "694fee",
            "content": trend_items
        })
    
    # Resolutions Section
    if "resolutions" in llm_data:
        resolution_items = [_format_resolution_item(res) for res in llm_data["resolutions"]]
        sections.append({
            "title": "Resolutions & Wins" if persona == "wellness" else "Resolutions & Improvements",
            "icon": "check-circle",
            "color": "27AE60",
            "content": resolution_items
        })
    
    return sections


def _format_executive_summary(summary_data):
    """Format executive summary into HTML"""
    parts = []
    
    if "locations_needing_attention" in summary_data:
        total = summary_data.get("total_locations", "?")
        needing = summary_data["locations_needing_attention"]
        parts.append(f"<b>{needing} of {total} locations</b> need attention today")
    
    if "critical_count" in summary_data and summary_data["critical_count"] > 0:
        parts.append(f"<b>{summary_data['critical_count']} critical</b> issues requiring immediate action")
    
    if "top_concern" in summary_data:
        parts.append(summary_data["top_concern"])
    
    return ". ".join(parts) + "."


def _format_priority_item(item, persona):
    """Format a priority item into HTML"""
    lines = []
    
    # Location name as header
    location = item.get("location_name", "Unknown Location")
    lines.append(f"<b>{location}</b>")
    
    # Primary concern
    concern = item.get("primary_concern", "")
    if concern:
        lines.append(f"{concern}")
    
    # Context in italics
    context = item.get("context", "")
    if context:
        lines.append(f"<i>{context}</i>")
    
    # Specific data points
    if "specific_data" in item:
        data_points = _format_data_points(item["specific_data"])
        if data_points:
            lines.append(data_points)
    
    # Recommended action
    action = item.get("recommended_action", "")
    if action:
        lines.append(f"<b>Action:</b> {action}")
    
    return "<br>".join(lines)


def _format_data_points(data):
    """Format specific data points"""
    points = []
    for key, value in data.items():
        formatted_key = key.replace("_", " ").title()
        points.append(f"{formatted_key}: {value}")
    
    if points:
        return f"<i>({', '.join(points)})</i>"
    return ""


def _format_trend_item(trend):
    """Format a trend item into HTML"""
    description = trend.get("description", "")
    locations = trend.get("locations_affected", "")
    direction = trend.get("direction", "neutral")
    
    # Add emoji for direction
    emoji = "📈" if direction == "positive" else "📉" if direction == "negative" else "➡️"
    
    text = f"{emoji} {description}"
    if locations:
        text += f" ({locations} locations)"
    
    return text


def _format_resolution_item(resolution):
    """Format a resolution item into HTML"""
    description = resolution.get("description", "")
    location = resolution.get("location_name", "")
    days_to_resolve = resolution.get("days_to_resolve", "")
    
    text = description
    if location:
        text = f"<b>{location}:</b> {text}"
    if days_to_resolve:
        text += f" <i>(resolved after {days_to_resolve} days)</i>"
    
    return text


# Example LLM Output Structure (What LLM Should Return)
EXAMPLE_LLM_OUTPUT_WELLNESS = {
    "executive_summary": {
        "total_locations": 45,
        "locations_needing_attention": 12,
        "critical_count": 3,
        "warning_count": 6,
        "top_concern": "Sleep quality declining across multiple locations"
    },
    "top_priorities": [
        {
            "location_id": "12345",
            "location_name": "Apartment 103",
            "primary_concern": "3-day decline in bathroom visits",
            "severity": "critical",
            "days_active": 3,
            "specific_data": {
                "current_visits_per_day": 2,
                "baseline_visits_per_day": 6,
                "decline_percentage": 67
            },
            "context": "Possible dehydration or UTI risk",
            "recommended_action": "Call resident to assess hydration and schedule wellness check"
        },
        {
            "location_id": "12346",
            "location_name": "Suite 205",
            "primary_concern": "Sleep duration declined significantly",
            "severity": "critical",
            "days_active": 2,
            "specific_data": {
                "current_hours": 4.2,
                "baseline_hours": 7.5,
                "decline_hours": 3.3
            },
            "context": "Significant sleep disruption detected",
            "recommended_action": "Contact family to investigate cause (pain, anxiety, medication change)"
        }
    ],
    "trends": [
        {
            "category": "sleep",
            "description": "Sleep quality improving across population",
            "locations_affected": 8,
            "direction": "positive",
            "specifics": "Average sleep increased from 5 hours to 7-9 hours over past week"
        },
        {
            "category": "social",
            "description": "Social isolation increasing",
            "locations_affected": 5,
            "direction": "negative",
            "specifics": "No departures from home in 7+ days"
        }
    ],
    "resolutions": [
        {
            "location_id": "12340",
            "location_name": "Apartment 101",
            "description": "Bathroom pattern normalized after staff intervention",
            "days_to_resolve": 5,
            "intervention": "Hydration protocol implemented"
        }
    ],
    "metadata": {
        "total_locations_analyzed": 45,
        "reports_processed": 450,
        "time_range_hours": 24
    }
}

EXAMPLE_LLM_OUTPUT_TECH = {
    "executive_summary": {
        "total_locations": 45,
        "locations_with_issues": 8,
        "critical_count": 2,
        "warning_count": 4,
        "devices_offline": 15,
        "top_concern": "Gateway outages affecting multiple buildings"
    },
    "top_priorities": [
        {
            "location_id": "12347",
            "location_name": "Building A",
            "primary_concern": "Gateway offline for 3 days",
            "severity": "critical",
            "days_active": 3,
            "specific_data": {
                "device_type": "Gateway",
                "device_id": "gw_12347_001",
                "devices_affected": 12,
                "last_seen": "2026-01-01 06:00:00"
            },
            "context": "Complete loss of monitoring for entire building",
            "recommended_action": "Dispatch technician to check power and network connectivity immediately"
        }
    ],
    "trends": [
        {
            "category": "connectivity",
            "description": "WiFi connectivity issues affecting multiple gateways",
            "locations_affected": 12,
            "direction": "negative",
            "specifics": "Intermittent disconnects, possible ISP problem"
        }
    ],
    "resolutions": [
        {
            "location_id": "12348",
            "location_name": "Building B",
            "description": "Gateway back online after firmware update",
            "days_to_resolve": 2,
            "intervention": "Remote firmware update applied"
        }
    ],
    "metadata": {
        "total_locations_analyzed": 45,
        "reports_processed": 120,
        "time_range_hours": 24
    }
}


