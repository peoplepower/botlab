"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""

# Report Categories (for organizational routing)
CATEGORY_WELLNESS = "wellness"
CATEGORY_IT = "it"
CATEGORY_SAFETY = "safety"
CATEGORY_ENERGY = "energy"

# Priority levels (from location reports)
PRIORITY_CRITICAL = "critical"
PRIORITY_WARNING = "warning"
PRIORITY_INFO = "info"

# Sentiment types (from location reports)
SENTIMENT_CONCERN = "concern"
SENTIMENT_RESOLUTION = "resolution"
SENTIMENT_UPDATE = "update"
SENTIMENT_CELEBRATION = "celebration"
SENTIMENT_SUMMARY = "summary"

# Report type to category mapping (for filtering)
REPORT_TYPE_CATEGORIES = {
    # Wellness reports
    "stability": CATEGORY_WELLNESS,
    "fall_focus": CATEGORY_WELLNESS,  # Threshold-gated fall-risk escalations from _evaluate_fall_focus_for_org()
    "health": CATEGORY_WELLNESS,  # Auto-routed health.* events (e.g. health.fall, health.heart_rate_alert)
    "activity": CATEGORY_WELLNESS,  # Activity/sedentary summaries (e.g. sedentary tracking)
    "bathroom": CATEGORY_WELLNESS,
    "sleep": CATEGORY_WELLNESS,
    "social_isolation": CATEGORY_WELLNESS,
    "medication": CATEGORY_WELLNESS,
    "wellness": CATEGORY_WELLNESS,
    
    # IT reports
    "infrastructure": CATEGORY_IT,
    "device_offline": CATEGORY_IT,
    "device_online": CATEGORY_IT,
    "battery_low": CATEGORY_IT,
    "connectivity": CATEGORY_IT,
    
    # Safety reports
    "safety": CATEGORY_SAFETY,
    "security": CATEGORY_SAFETY,
    "water_leak": CATEGORY_SAFETY,
    "temperature_alert": CATEGORY_SAFETY,
    "smoke": CATEGORY_SAFETY,
    "carbon_monoxide": CATEGORY_SAFETY,
    
    # Energy reports
    "energy": CATEGORY_ENERGY,
    "hvac": CATEGORY_ENERGY,
    "power": CATEGORY_ENERGY,

    # Summary reports
    "daily_summary": CATEGORY_WELLNESS,
    "weekly_summary": CATEGORY_WELLNESS,
}


def get_category(report_type):
    """
    Get the category for a given report type
    
    :param report_type: Report type string
    :return: Category string or None if unknown
    """
    return REPORT_TYPE_CATEGORIES.get(report_type, None)


def filter_reports_by_category(reports, category):
    """
    Filter a list of reports by category
    
    :param reports: List of report dictionaries
    :param category: Category to filter by (e.g., CATEGORY_WELLNESS)
    :return: Filtered list of reports
    """
    filtered = []
    for report in reports:
        report_type = report.get("report_type", "")
        if get_category(report_type) == category:
            filtered.append(report)
    return filtered


def filter_reports_by_priority(reports, priorities):
    """
    Filter a list of reports by priority levels
    
    :param reports: List of report dictionaries
    :param priorities: List of priority levels to include (e.g., [PRIORITY_CRITICAL, PRIORITY_WARNING])
    :return: Filtered list of reports
    """
    if not isinstance(priorities, list):
        priorities = [priorities]
    
    filtered = []
    for report in reports:
        if report.get("priority") in priorities:
            filtered.append(report)
    return filtered


def filter_reports_by_sentiment(reports, sentiments):
    """
    Filter a list of reports by sentiment
    
    :param reports: List of report dictionaries
    :param sentiments: List of sentiments to include (e.g., [SENTIMENT_CONCERN, SENTIMENT_WARNING])
    :return: Filtered list of reports
    """
    if not isinstance(sentiments, list):
        sentiments = [sentiments]
    
    filtered = []
    for report in reports:
        if report.get("sentiment") in sentiments:
            filtered.append(report)
    return filtered


def sort_reports_by_severity(reports, descending=True):
    """
    Sort reports by severity rank
    
    :param reports: List of report dictionaries
    :param descending: True to sort highest severity first (default), False for ascending
    :return: Sorted list of reports
    """
    return sorted(reports, key=lambda r: r.get("severity_rank", 0), reverse=descending)


def group_reports_by_location(reports):
    """
    Group reports by location
    
    :param reports: List of report dictionaries
    :return: Dictionary of {location_id: [reports]}
    """
    grouped = {}
    for report in reports:
        location_id = report.get("location_id")
        if location_id not in grouped:
            grouped[location_id] = []
        grouped[location_id].append(report)
    return grouped


def get_report_summary_stats(reports):
    """
    Get summary statistics for a list of reports
    
    :param reports: List of report dictionaries
    :return: Dictionary with summary stats
    """
    stats = {
        "total": len(reports),
        "by_priority": {},
        "by_sentiment": {},
        "by_category": {},
        "unique_locations": len(set(r.get("location_id") for r in reports)),
    }
    
    for report in reports:
        # Count by priority
        priority = report.get("priority", "unknown")
        stats["by_priority"][priority] = stats["by_priority"].get(priority, 0) + 1
        
        # Count by sentiment
        sentiment = report.get("sentiment", "unknown")
        stats["by_sentiment"][sentiment] = stats["by_sentiment"].get(sentiment, 0) + 1
        
        # Count by category
        category = get_category(report.get("report_type", ""))
        if category:
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
    
    return stats


def format_reports_for_llm(reports, max_reports=None):
    """
    Format reports for LLM consumption with appropriate truncation
    
    :param reports: List of report dictionaries
    :param max_reports: Maximum number of reports to include (None for all)
    :return: Formatted string for LLM prompt
    """
    if max_reports:
        reports = reports[:max_reports]
    
    lines = []
    for i, report in enumerate(reports, 1):
        lines.append(f"[Report {i}]")
        lines.append(f"Location: {report.get('location_name', 'Unknown')} (ID: {report.get('location_id', 'Unknown')})")
        lines.append(f"Priority: {report.get('priority', 'unknown').upper()}")
        lines.append(f"Type: {report.get('report_type', 'unknown')}")
        lines.append(f"Sentiment: {report.get('sentiment', 'unknown')}")
        lines.append(f"Short Description: {report.get('short_description', 'No short description provided')}")
        lines.append(f"Long Description: {report.get('long_description', 'No long description provided')}")
        
        if report.get("concerns"):
            lines.append("Concerns:")
            for concern in report["concerns"]:
                lines.append(f"  - {concern}")
        
        if report.get("context"):
            lines.append(f"Context: {report['context']}")
        
        if report.get("recommended_action"):
            lines.append(f"Recommended Action: {report['recommended_action']}")
        
        if report.get("severity_rank"):
            lines.append(f"Severity Rank: {report['severity_rank']}/100")
        
        if report.get("days_active"):
            lines.append(f"Days Active: {report['days_active']}")
        
        lines.append("")  # Blank line between reports
    
    return "\n".join(lines)


def validate_org_report(report):
    """
    Validate that an organizational report has all required fields
    
    :param report: Report dictionary to validate
    :return: Tuple of (is_valid, error_message)
    """
    required_fields = [
        "location_id",
        "location_name",
        "timestamp_ms",
        "priority",
        "report_type",
        "sentiment",
        "report_id",
        "short_description",
    ]
    
    for field in required_fields:
        if field not in report:
            return False, f"Missing required field: {field}"
        
        # Check that field is not None or empty string
        if report[field] is None or (isinstance(report[field], str) and report[field] == ""):
            return False, f"Required field '{field}' is empty"
    
    # Validate priority
    valid_priorities = [PRIORITY_CRITICAL, PRIORITY_WARNING, PRIORITY_INFO]
    if report["priority"] not in valid_priorities:
        return False, f"Invalid priority: {report['priority']}. Must be one of: {valid_priorities}"
    
    # Validate sentiment
    valid_sentiments = [SENTIMENT_CONCERN, SENTIMENT_RESOLUTION, SENTIMENT_UPDATE, SENTIMENT_CELEBRATION, SENTIMENT_SUMMARY]
    if report["sentiment"] not in valid_sentiments:
        return False, f"Invalid sentiment: {report['sentiment']}. Must be one of: {valid_sentiments}"
    
    return True, None


