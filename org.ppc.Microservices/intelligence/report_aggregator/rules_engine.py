"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Rules-Based Report Pre-Processing Engine
=========================================

WHY:
Efficient filtering and aggregation of 100-1000 reports before LLM processing.
Reduces LLM token costs, prevents hallucination, and provides deterministic sorting.

WHAT:
- Filters out resolved concerns and low-priority info
- Groups reports by location + report_type (consolidates duplicates)
- Calculates severity rank when missing
- Sorts by severity + days_active
- Limits to top N locations per category
- Provides structured input for LLM

HOW:
1. Filter: Remove resolved/info-priority reports (configurable)
2. Deduplicate: Group by location+report_type, keep most recent + most severe
3. Enrich: Calculate missing severity_rank from priority + days_active + sentiment
4. Sort: By severity_rank DESC, days_active DESC
5. Categorize: Group by wellness/it/safety/energy
6. Limit: Top N per category (prevents overwhelming LLM)
"""

import signals.report as org_report


# Severity weights for auto-calculation
PRIORITY_WEIGHTS = {
    org_report.PRIORITY_CRITICAL: 100,
    org_report.PRIORITY_WARNING: 60,
    org_report.PRIORITY_INFO: 20,
}

SENTIMENT_MODIFIERS = {
    org_report.SENTIMENT_CONCERN: 0,      # No modifier (full severity)
    org_report.SENTIMENT_UPDATE: -10,     # Slightly less urgent
    org_report.SENTIMENT_RESOLUTION: -50, # Much less urgent
    org_report.SENTIMENT_CELEBRATION: -60, # Least urgent
    org_report.SENTIMENT_SUMMARY: -20,    # Less urgent
}


def filter_reports(reports, include_resolved=False, include_info=False):
    """
    Filter reports based on rules
    
    :param reports: List of report dicts
    :param include_resolved: Include resolutions? (Default False - exclude resolved)
    :param include_info: Include info-priority? (Default False - focus on problems)
    :return: Filtered list
    """
    filtered = []
    
    for report in reports:
        sentiment = report.get("sentiment")
        priority = report.get("priority")
        
        # Skip resolutions unless requested
        if not include_resolved and sentiment == org_report.SENTIMENT_RESOLUTION:
            continue
        
        # Skip info-priority unless requested
        if not include_info and priority == org_report.PRIORITY_INFO:
            continue
        
        filtered.append(report)
    
    return filtered


def deduplicate_reports(reports):
    """
    Deduplicate reports by location + report_type
    Keep MOST RECENT and MOST SEVERE per location+type
    
    :param reports: List of report dicts
    :return: Deduplicated list
    """
    # Group by location_id + report_type
    grouped = {}
    
    for report in reports:
        location_id = report.get("location_id")
        report_type = report.get("report_type")
        key = f"{location_id}_{report_type}"
        
        if key not in grouped:
            grouped[key] = []
        
        grouped[key].append(report)
    
    # For each group, keep most recent + most severe
    deduplicated = []
    
    for key, group in grouped.items():
        # Sort by timestamp (most recent first) and severity_rank (highest first)
        sorted_group = sorted(
            group,
            key=lambda r: (r.get("timestamp_ms", 0), r.get("severity_rank", 0)),
            reverse=True
        )
        
        # Keep the most recent
        deduplicated.append(sorted_group[0])
    
    return deduplicated


def normalize_days_active(days_active):
    """
    Normalize a days_active value to a usable positive number.

    Producers may omit days_active entirely (send_org_report() drops it when None),
    leaving it absent or None downstream. Left unhandled this surfaced as
    "Days Active: None" in emails, a "0.0 average days active" in trends, and -- worst
    of all -- LLM narratives like "no active days recorded" when the raw None was
    injected into enhancement prompts. A concern that has been reported is active for
    at least one day, so floor it at 1.

    :param days_active: Raw days_active value (may be None, missing, 0, or negative)
    :return: Integer/float days active, floored at 1
    """
    if not isinstance(days_active, (int, float)) or isinstance(days_active, bool) or days_active < 1:
        return 1
    return days_active


def calculate_severity_rank(report):
    """
    Calculate severity_rank (0-100) if missing
    Formula: priority_weight + sentiment_modifier + (days_active * 2) [capped at 100]
    
    :param report: Report dict
    :return: Severity rank (0-100)
    """
    if "severity_rank" in report and report["severity_rank"] is not None:
        return report["severity_rank"]
    
    priority = report.get("priority", org_report.PRIORITY_INFO)
    sentiment = report.get("sentiment", org_report.SENTIMENT_CONCERN)
    # Guard against a present-but-None days_active. dict.get(key, default) only
    # applies the default when the key is ABSENT, so {"days_active": None} would
    # otherwise return None here and crash on `days_active * 2`.
    days_active = normalize_days_active(report.get("days_active"))

    # Base severity from priority
    base = PRIORITY_WEIGHTS.get(priority, 20)
    
    # Sentiment modifier
    modifier = SENTIMENT_MODIFIERS.get(sentiment, 0)
    
    # Days active boost (up to +20)
    days_boost = min(days_active * 2, 20)
    
    # Calculate final rank (capped at 100)
    rank = min(base + modifier + days_boost, 100)
    
    return max(rank, 0)  # Floor at 0


def enrich_reports(reports):
    """
    Enrich reports with calculated fields
    
    :param reports: List of report dicts
    :return: Enriched list
    """
    enriched = []
    
    for report in reports:
        enriched_report = report.copy()

        # Normalize days_active first so every downstream consumer (severity calc,
        # report builder, trends, deep dives, LLM prompts, email rendering) sees a
        # usable positive number instead of a missing/None value.
        enriched_report["days_active"] = normalize_days_active(
            enriched_report.get("days_active")
        )

        # Calculate severity_rank if missing
        if "severity_rank" not in report or report["severity_rank"] is None:
            enriched_report["severity_rank"] = calculate_severity_rank(enriched_report)

        enriched.append(enriched_report)
    
    return enriched


def sort_reports_by_priority(reports):
    """
    Sort reports by severity_rank DESC, then days_active DESC
    
    :param reports: List of report dicts
    :return: Sorted list
    """
    return sorted(
        reports,
        key=lambda r: (r.get("severity_rank", 0), r.get("days_active", 0)),
        reverse=True
    )


def categorize_reports(reports):
    """
    Group reports by category (wellness, it, safety, energy, other)
    
    :param reports: List of report dicts
    :return: Dict of {category: [reports]}
    """
    categorized = {
        org_report.CATEGORY_WELLNESS: [],
        org_report.CATEGORY_IT: [],
        org_report.CATEGORY_SAFETY: [],
        org_report.CATEGORY_ENERGY: [],
        "other": [],
    }
    
    for report in reports:
        report_type = report.get("report_type")
        category = org_report.get_category(report_type)
        
        if category:
            categorized[category].append(report)
        else:
            categorized["other"].append(report)
    
    return categorized


def limit_top_reports(categorized_reports, max_per_category=20):
    """
    Limit to top N reports per category (already sorted by severity)
    
    :param categorized_reports: Dict of {category: [reports]}
    :param max_per_category: Maximum reports per category
    :return: Dict of {category: [top_reports]}
    """
    limited = {}
    
    for category, reports in categorized_reports.items():
        limited[category] = reports[:max_per_category]
    
    return limited


def process_reports_for_llm(
    reports,
    include_resolved=False,
    include_info=False,
    max_per_category=20
):
    """
    Complete rules-based pre-processing pipeline
    
    PIPELINE:
    1. Filter → Remove resolved/info
    2. Deduplicate → Group by location+type
    3. Enrich → Calculate severity_rank
    4. Sort → By severity + days_active
    5. Categorize → Group by wellness/it/safety/energy
    6. Limit → Top N per category
    
    :param reports: Raw list of reports from cache
    :param include_resolved: Include resolutions? (Default False)
    :param include_info: Include info-priority? (Default False)
    :param max_per_category: Maximum reports per category (Default 20)
    :return: Dict with processed data ready for LLM
    """
    # 1. Filter
    filtered = filter_reports(reports, include_resolved, include_info)
    
    # 2. Deduplicate
    deduplicated = deduplicate_reports(filtered)
    
    # 3. Enrich
    enriched = enrich_reports(deduplicated)
    
    # 4. Sort
    sorted_reports = sort_reports_by_priority(enriched)
    
    # 5. Categorize
    categorized = categorize_reports(sorted_reports)
    
    # 6. Limit
    limited = limit_top_reports(categorized, max_per_category)
    
    # Calculate summary stats
    total_filtered = len(filtered)
    total_deduplicated = len(deduplicated)
    total_critical = sum(1 for r in enriched if r.get("priority") == org_report.PRIORITY_CRITICAL)
    total_warning = sum(1 for r in enriched if r.get("priority") == org_report.PRIORITY_WARNING)
    unique_locations = len(set(r.get("location_id") for r in enriched))
    
    # Count per category (after limiting)
    category_counts = {
        category: len(reports) for category, reports in limited.items()
    }
    
    return {
        "filtered_reports": sorted_reports,  # All filtered+sorted reports
        "categorized_reports": limited,      # Top N per category
        "stats": {
            "total_raw": len(reports),
            "total_filtered": total_filtered,
            "total_deduplicated": total_deduplicated,
            "total_critical": total_critical,
            "total_warning": total_warning,
            "unique_locations": unique_locations,
            "category_counts": category_counts,
        }
    }


def get_top_locations(reports, max_locations=10):
    """
    Get top N locations by highest severity
    
    :param reports: List of report dicts (sorted by severity)
    :param max_locations: Maximum locations to return
    :return: List of top location reports
    """
    # Group by location
    locations = {}
    
    for report in reports:
        location_id = report.get("location_id")
        
        if location_id not in locations:
            locations[location_id] = {
                "location_id": location_id,
                "location_name": report.get("location_name"),
                "max_severity": report.get("severity_rank", 0),
                "reports": []
            }
        
        locations[location_id]["reports"].append(report)
    
    # Sort locations by max_severity
    sorted_locations = sorted(
        locations.values(),
        key=lambda l: l["max_severity"],
        reverse=True
    )
    
    return sorted_locations[:max_locations]


