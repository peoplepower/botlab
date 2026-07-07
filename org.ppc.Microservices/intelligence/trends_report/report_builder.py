"""
Created on March 13, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Deterministic Report Builder
=============================

This module builds COMPLETE trend report structures WITHOUT LLM intervention.
All structure, sections, and data are deterministically generated.

LLM is used to enhance text in Section 1 (Analysis Overview),
Section 2 (Individual Analysis), and Section 3 (Review).
LLM outputs TEXT, not JSON.

Report Sections (Fixed Structure):
1. Analysis Overview - Population statistics with LLM narrative
2. Individual Analysis - Per-location LLM narrative, charts, and trends table
3. Review - Notes and suggestions with LLM narrative
"""

from . import services


def _is_visible(trend_id, metadata):
    """Return True if the trend is not marked hidden in metadata."""
    return not metadata.get(trend_id, {}).get("hidden", False)


def _get_latest_trends(days):
    """
    Collect the most recent data point for each trend across all days.

    Avoids the "sparse latest day" problem where the most recent calendar day
    may only contain a subset of trends.

    :param days: Dict {day_ms: {trend_id: {value, display, avg, std, zscore, ...}}}
    :return: Dict {trend_id: trend_data} with the most recent entry per trend
    """
    latest = {}
    for day_ms in sorted(days.keys(), reverse=True):
        for trend_id, trend_data in days[day_ms].items():
            if trend_id not in latest:
                latest[trend_id] = trend_data
    return latest


def build_report_skeleton(trends_data, metadata, timestamp_ms):
    """
    Build complete report skeleton from raw trends data.
    No LLM involvement - produces skeleton with empty text fields for enhancement.

    trends_data should be pre-sorted by criticality (most critical first).
    The first MAX_DETAILED_LOCATIONS locations receive full individual analysis;
    remaining locations are included as a summary table.

    :param trends_data: Dict {location_id: {day_midnight_ms: {trend_id: {...}}}}
    :param metadata: Dict {trend_id: {parent_id, category, title, units, ...}}
    :param timestamp_ms: Report generation timestamp
    :return: Report skeleton dict with enhancement_tasks list
    """
    # Split into detailed (top N) and summary (remaining)
    all_location_ids = list(trends_data.keys())
    detailed_ids = all_location_ids[:services.MAX_DETAILED_LOCATIONS]
    summary_ids = all_location_ids[services.MAX_DETAILED_LOCATIONS:]

    detailed_data = {lid: trends_data[lid] for lid in detailed_ids}
    summary_data = {lid: trends_data[lid] for lid in summary_ids}

    # Sections 1 and 3 use ALL locations for aggregate stats
    section1 = _build_section1_overview(trends_data, metadata)
    section2 = _build_section2_individuals(detailed_data, metadata)
    section2_summary = _build_section2_summary(summary_data, metadata)
    section3 = _build_section3_review(trends_data, metadata)

    report = {
        "timestamp_ms": timestamp_ms,
        "metadata": metadata,
        "section1_overview": section1,
        "section2_individuals": section2,
        "section2_summary": section2_summary,
        "section3_review": section3,
        "enhancement_tasks": [],
    }

    report["enhancement_tasks"] = get_enhancement_tasks(report)
    return report


def _build_section1_overview(trends_data, metadata):
    """
    Build population overview with aggregate statistics by category.

    :param trends_data: Dict {location_id: {day_ms: {trend_id: {...}}}}
    :param metadata: Dict {trend_id: {...}}
    :return: Section 1 overview dict
    """
    category_stats = {}
    all_trend_ids = set()
    location_ids = list(trends_data.keys())

    for location_id, days in trends_data.items():
        if not days:
            continue

        # Collect the most recent data point for each trend across ALL days
        latest_trends = _get_latest_trends(days)
        for trend_id, trend_data in latest_trends.items():
            if not _is_visible(trend_id, metadata):
                continue
            all_trend_ids.add(trend_id)
            meta = metadata.get(trend_id, {})
            category = meta.get("category", "category.other")

            if category not in category_stats:
                category_stats[category] = {
                    "trend_count": 0,
                    "location_count": 0,
                    "locations": set(),
                    "avg_values": {},
                    "trends_detail": {},
                }

            stats = category_stats[category]
            stats["locations"].add(location_id)

            if trend_id not in stats["avg_values"]:
                stats["avg_values"][trend_id] = []
            value = trend_data.get("value")
            if value is not None:
                stats["avg_values"][trend_id].append(value)

            if trend_id not in stats["trends_detail"]:
                stats["trends_detail"][trend_id] = {
                    "title": meta.get("title", trend_id),
                    "units": meta.get("units", ""),
                    "values": [],
                }
            stats["trends_detail"][trend_id]["values"].append(value)

    # Compute averages and finalize
    for category, stats in category_stats.items():
        stats["location_count"] = len(stats["locations"])
        stats["trend_count"] = len(stats["avg_values"])
        del stats["locations"]  # Remove set (not serializable)

        # Compute mean/std per trend
        for trend_id, values in stats["avg_values"].items():
            if values:
                avg = sum(values) / len(values)
                stats["avg_values"][trend_id] = round(avg, 2)
            else:
                stats["avg_values"][trend_id] = 0

        for trend_id, detail in stats["trends_detail"].items():
            values = [v for v in detail["values"] if v is not None]
            if values:
                avg = sum(values) / len(values)
                variance = sum((v - avg) ** 2 for v in values) / (len(values) - 1) if len(values) > 1 else 0
                detail["avg"] = round(avg, 2)
                detail["std"] = round(variance ** 0.5, 2)
            else:
                detail["avg"] = 0
                detail["std"] = 0
            del detail["values"]

    # Find outliers (high absolute z-scores across all locations)
    outliers = []
    for location_id, days in trends_data.items():
        if not days:
            continue
        latest_trends = _get_latest_trends(days)
        for trend_id, trend_data in latest_trends.items():
            if not _is_visible(trend_id, metadata):
                continue
            zscore = trend_data.get("zscore")
            if zscore is not None and abs(zscore) >= services.ZSCORE_CONCERNING:
                outliers.append({
                    "location_id": str(location_id),
                    "trend_id": trend_id,
                    "zscore": round(zscore, 2),
                    "display": trend_data.get("display", ""),
                })

    outliers.sort(key=lambda x: abs(x["zscore"]), reverse=True)

    return {
        "total_locations": len(location_ids),
        "total_trend_types": len(all_trend_ids),
        "category_stats": category_stats,
        "outliers": outliers[:20],
        # LLM-enhanced field
        "overview_text": "",
    }


def _build_section2_individuals(trends_data, metadata):
    """
    Build per-location blocks with current trends, health distribution,
    wellness score timeline, and outlier data for LLM narrative.

    :param trends_data: Dict {location_id: {day_ms: {trend_id: {...}}}}
    :param metadata: Dict {trend_id: {...}}
    :return: Dict {location_id: {current_trends, historical, alerts,
             individual_text, health_distribution, wellness_history}}
    """
    individuals = {}

    for location_id, days in trends_data.items():
        if not days:
            continue

        sorted_days = sorted(days.keys())

        # Current trends snapshot (most recent data point per trend)
        latest_trends = _get_latest_trends(days)
        current_trends = {}
        for trend_id, trend_data in latest_trends.items():
            if not _is_visible(trend_id, metadata):
                continue
            meta = metadata.get(trend_id, {})
            current_trends[trend_id] = {
                "value": trend_data.get("value"),
                "display": trend_data.get("display", ""),
                "avg": trend_data.get("avg"),
                "std": trend_data.get("std"),
                "zscore": trend_data.get("zscore"),
                "category": meta.get("category", "category.other"),
                "title": meta.get("title", trend_id),
                "units": meta.get("units", ""),
            }

        # Historical time series
        historical = {}
        for day_ms in sorted_days:
            for trend_id, trend_data in days[day_ms].items():
                if not _is_visible(trend_id, metadata):
                    continue
                if trend_id not in historical:
                    historical[trend_id] = []
                historical[trend_id].append({
                    "day_ms": day_ms,
                    "value": trend_data.get("value"),
                    "display": trend_data.get("display", ""),
                })

        # Alerts: trends with concerning z-scores
        alerts = []
        for trend_id, trend_info in current_trends.items():
            zscore = trend_info.get("zscore")
            if zscore is not None and abs(zscore) >= services.ZSCORE_CONCERNING:
                alerts.append({
                    "trend_id": trend_id,
                    "zscore": round(zscore, 2),
                    "direction": "high" if zscore > 0 else "low",
                })
        alerts.sort(key=lambda x: abs(x["zscore"]), reverse=True)

        # Health distribution for pie chart (healthy/concerning/critical)
        health_distribution = {"healthy": 0, "concerning": 0, "critical": 0}
        for trend_info in current_trends.values():
            zscore = trend_info.get("zscore")
            if zscore is not None:
                abs_z = abs(zscore)
                if abs_z >= services.ZSCORE_CRITICAL:
                    health_distribution["critical"] += 1
                elif abs_z >= services.ZSCORE_CONCERNING:
                    health_distribution["concerning"] += 1
                else:
                    health_distribution["healthy"] += 1

        # Wellness score timeline
        wellness_history = _extract_wellness_history(days, sorted_days, metadata)

        individuals[str(location_id)] = {
            "current_trends": current_trends,
            "historical": historical,
            "alerts": alerts,
            # LLM-enhanced field
            "individual_text": "",
            # Chart data
            "health_distribution": health_distribution,
            "wellness_history": wellness_history,
        }

    return individuals


def _build_section2_summary(trends_data, metadata):
    """
    Build lightweight summary rows for locations beyond MAX_DETAILED_LOCATIONS.
    No LLM text, no historical data, no charts - just category-level scores.

    :param trends_data: Dict {location_id: {day_ms: {trend_id: {...}}}}
    :param metadata: Dict {trend_id: {...}}
    :return: Dict {location_id: {category_scores, total_trends, critical_count,
             concerning_count}}
    """
    summary = {}

    for location_id, days in trends_data.items():
        if not days:
            continue

        latest_trends = _get_latest_trends(days)

        # Aggregate z-scores by category
        category_zscores = {}
        critical_count = 0
        concerning_count = 0
        total_trends = 0

        for trend_id, trend_data in latest_trends.items():
            if not _is_visible(trend_id, metadata):
                continue
            total_trends += 1
            meta = metadata.get(trend_id, {})
            category = meta.get("category", "category.other")
            zscore = trend_data.get("zscore")

            if zscore is not None:
                abs_z = abs(zscore)
                if abs_z >= services.ZSCORE_CRITICAL:
                    critical_count += 1
                elif abs_z >= services.ZSCORE_CONCERNING:
                    concerning_count += 1

                if category not in category_zscores:
                    category_zscores[category] = []
                category_zscores[category].append(abs_z)

        # Average absolute z-score per category
        category_scores = {}
        for category, zscores in category_zscores.items():
            category_scores[category] = round(
                sum(zscores) / len(zscores), 2
            )

        summary[str(location_id)] = {
            "category_scores": category_scores,
            "total_trends": total_trends,
            "critical_count": critical_count,
            "concerning_count": concerning_count,
        }

    return summary


def _extract_wellness_history(days, sorted_days, metadata):
    """
    Extract a wellness score timeline for one location.

    Strategy:
    1. Look for a trend with "wellness" in the title (case-insensitive)
    2. Fall back to trends in category.summary
    3. Fall back to computing a synthetic wellness proxy from average z-scores

    :param days: Dict {day_ms: {trend_id: {...}}}
    :param sorted_days: Sorted list of day_ms keys
    :param metadata: Dict {trend_id: {...}}
    :return: List of {day_ms, value} dicts
    """
    # Strategy 1 & 2: find a dedicated wellness/summary trend
    wellness_trend_id = None
    for trend_id, meta in metadata.items():
        title = meta.get("title", "").lower()
        if "wellness" in title:
            wellness_trend_id = trend_id
            break

    if wellness_trend_id is None:
        for trend_id, meta in metadata.items():
            if meta.get("category") == "category.summary":
                wellness_trend_id = trend_id
                break

    if wellness_trend_id is not None:
        history = []
        for day_ms in sorted_days:
            trend_data = days[day_ms].get(wellness_trend_id)
            if trend_data and trend_data.get("value") is not None:
                history.append({
                    "day_ms": day_ms,
                    "value": trend_data["value"],
                })
        if history:
            return history

    # Strategy 3: synthetic wellness from average z-scores
    # Wellness = 100 - (avg |z-score| * 20), clamped to [0, 100]
    history = []
    for day_ms in sorted_days:
        zscores = []
        for trend_data in days[day_ms].values():
            z = trend_data.get("zscore")
            if z is not None:
                zscores.append(abs(z))
        if zscores:
            avg_abs_z = sum(zscores) / len(zscores)
            wellness = max(0, min(100, 100 - avg_abs_z * 20))
            history.append({
                "day_ms": day_ms,
                "value": round(wellness, 1),
            })
    return history


def _build_section3_review(trends_data, metadata):
    """
    Build review section data for LLM summarization.

    :param trends_data: Dict {location_id: {day_ms: {trend_id: {...}}}}
    :param metadata: Dict {trend_id: {...}}
    :return: Section 3 review dict
    """
    # Cross-location patterns: trends that are concerning across multiple locations
    trend_zscores = {}  # {trend_id: [zscore, ...]}
    for location_id, days in trends_data.items():
        if not days:
            continue
        latest_trends = _get_latest_trends(days)
        for trend_id, trend_data in latest_trends.items():
            if not _is_visible(trend_id, metadata):
                continue
            zscore = trend_data.get("zscore")
            if zscore is not None:
                if trend_id not in trend_zscores:
                    trend_zscores[trend_id] = []
                trend_zscores[trend_id].append(zscore)

    cross_location_patterns = []
    for trend_id, zscores in trend_zscores.items():
        concerning_count = sum(1 for z in zscores if abs(z) >= services.ZSCORE_CONCERNING)
        if concerning_count > 0:
            avg_zscore = sum(zscores) / len(zscores) if zscores else 0
            meta = metadata.get(trend_id, {})
            cross_location_patterns.append({
                "trend_id": trend_id,
                "title": meta.get("title", trend_id),
                "category": meta.get("category", "category.other"),
                "affected_locations": concerning_count,
                "total_locations": len(zscores),
                "avg_zscore": round(avg_zscore, 2),
            })
    cross_location_patterns.sort(key=lambda x: x["affected_locations"], reverse=True)

    # Category health classification
    category_health = {}
    for trend_id, zscores in trend_zscores.items():
        meta = metadata.get(trend_id, {})
        category = meta.get("category", "category.other")
        if category not in category_health:
            category_health[category] = {"healthy": 0, "concerning": 0, "critical": 0}

        for z in zscores:
            abs_z = abs(z)
            if abs_z >= services.ZSCORE_CRITICAL:
                category_health[category]["critical"] += 1
            elif abs_z >= services.ZSCORE_CONCERNING:
                category_health[category]["concerning"] += 1
            else:
                category_health[category]["healthy"] += 1

    return {
        "cross_location_patterns": cross_location_patterns[:15],
        "category_health": category_health,
        # LLM-enhanced field
        "review_text": "",
    }


def get_enhancement_tasks(report):
    """
    Extract list of LLM enhancement tasks from the report skeleton.

    :param report: Report skeleton dict
    :return: List of enhancement task dicts
    """
    tasks = []

    # Task 1: Analysis Overview (Section 1)
    section1 = report["section1_overview"]
    tasks.append({
        "task_id": services.TASK_ANALYSIS_OVERVIEW,
        "task_type": services.TASK_ANALYSIS_OVERVIEW,
        "data": {
            "total_locations": section1["total_locations"],
            "total_trend_types": section1["total_trend_types"],
            "category_stats": {
                cat: {
                    "trend_count": stats["trend_count"],
                    "location_count": stats["location_count"],
                    "avg_values": stats["avg_values"],
                    "trend_names": [
                        d.get("title", tid)
                        for tid, d in stats.get("trends_detail", {}).items()
                    ],
                }
                for cat, stats in section1["category_stats"].items()
            },
            "outlier_count": len(section1["outliers"]),
        },
        "fields_to_fill": ["overview_text"],
    })

    # Tasks 2..N: Individual Analysis (Section 2, one per location)
    section2 = report["section2_individuals"]
    for location_id, loc_data in section2.items():
        outlier_trends = []
        for alert in loc_data.get("alerts", []):
            trend_info = loc_data.get("current_trends", {}).get(alert["trend_id"], {})
            outlier_trends.append({
                "title": trend_info.get("title", alert["trend_id"]),
                "category": services.TREND_CATEGORY_LABELS.get(
                    trend_info.get("category", ""), trend_info.get("category", "")
                ),
                "display": trend_info.get("display", ""),
                "units": trend_info.get("units", ""),
                "zscore": alert.get("zscore", 0),
                "direction": alert.get("direction", ""),
            })

        tasks.append({
            "task_id": f"{services.TASK_INDIVIDUAL_ANALYSIS}_{location_id}",
            "task_type": services.TASK_INDIVIDUAL_ANALYSIS,
            "data": {
                "location_id": location_id,
                "total_trends": len(loc_data.get("current_trends", {})),
                "health_distribution": loc_data.get("health_distribution", {}),
                "outlier_trends": outlier_trends,
            },
            "fields_to_fill": ["individual_text"],
        })

    # Last task: Review Summary (Section 3)
    section3 = report["section3_review"]
    tasks.append({
        "task_id": services.TASK_REVIEW_SUMMARY,
        "task_type": services.TASK_REVIEW_SUMMARY,
        "data": {
            "total_locations": section1["total_locations"],
            "cross_location_patterns": section3["cross_location_patterns"][:10],
            "category_health": section3["category_health"],
        },
        "fields_to_fill": ["review_text"],
    })

    return tasks


def apply_llm_enhancement(report, task_id, enhanced_text_dict):
    """
    Inject LLM-generated text into the report skeleton.

    :param report: Report skeleton dict
    :param task_id: Task identifier
    :param enhanced_text_dict: Dict of {field_name: text}
    """
    if task_id == services.TASK_ANALYSIS_OVERVIEW:
        for field, text in enhanced_text_dict.items():
            report["section1_overview"][field] = text

    elif task_id.startswith(services.TASK_INDIVIDUAL_ANALYSIS):
        # Extract location_id from task_id: "individual_analysis_{location_id}"
        location_id = task_id[len(services.TASK_INDIVIDUAL_ANALYSIS) + 1:]
        if location_id in report["section2_individuals"]:
            for field, text in enhanced_text_dict.items():
                report["section2_individuals"][location_id][field] = text

    elif task_id == services.TASK_REVIEW_SUMMARY:
        for field, text in enhanced_text_dict.items():
            report["section3_review"][field] = text
