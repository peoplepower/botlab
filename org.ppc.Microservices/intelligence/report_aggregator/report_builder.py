"""
Created on January 3, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Deterministic Report Builder
=============================

This module builds COMPLETE reports WITHOUT LLM intervention.
All structure, sections, and data are deterministically generated.

LLM is ONLY used section-by-section to enhance readability of TEXT.
LLM outputs TEXT, not JSON. We inject text into our tightly-controlled structure.

Report Sections (Fixed Structure):
1. Executive Summary
2. Top Concerns (by category: wellness, tech, safety, energy)
3. Top Celebrations (resolutions and wins)
4. Trends & Patterns (by category)
5. Category Deep Dives (one per category with concerns)
"""

import signals.report as org_report
from . import rules_engine


def build_master_report(processed_data, timestamp_ms, report_type, org_name="Organization"):
    """
    Build complete master report structure deterministically
    NO LLM INVOLVED - Pure data-driven report generation
    
    :param processed_data: Output from rules_engine.process_reports_for_llm()
    :param timestamp_ms: Report timestamp
    :param report_type: "daily" or "weekly"
    :param org_name: Organization name
    :return: Complete report dict with all sections
    """
    stats = processed_data["stats"]
    categorized_reports = processed_data["categorized_reports"]
    all_reports = processed_data["filtered_reports"]
    
    report = {
        "timestamp_ms": timestamp_ms,
        "report_type": report_type,
        "org_name": org_name,
        "schema_version": "2.0",
        "stats": stats,
        
        # Fixed report sections (deterministic)
        "sections": {
            "executive_summary": _build_executive_summary(stats, all_reports),
            "top_concerns": _build_top_concerns(categorized_reports),
            "top_celebrations": _build_top_celebrations(all_reports),
            "trends": _build_trends(categorized_reports, stats),
            "category_deep_dives": _build_category_deep_dives(categorized_reports),
        }
    }
    
    return report


def _build_executive_summary(stats, all_reports):
    """
    Build executive summary section with key metrics
    
    :param stats: Statistics dict from rules_engine
    :param all_reports: All filtered reports
    :return: Executive summary dict
    """
    # Get top 3 most severe concerns
    top_3_concerns = all_reports[:3]
    
    summary = {
        "total_locations": stats["unique_locations"],
        "total_reports": stats["total_deduplicated"],
        "critical_count": stats["total_critical"],
        "warning_count": stats["total_warning"],
        "info_count": 0,  # Filtered out in processing
        
        # Top concerns list (raw data)
        "top_concerns_list": [
            {
                "location_id": r.get("location_id"),
                "location_name": r.get("location_name"),
                "report_type": r.get("report_type"),
                "priority": r.get("priority"),
                "severity_rank": r.get("severity_rank"),
                "days_active": r.get("days_active"),
                "short_description": r.get("short_description", ""),
            }
            for r in top_3_concerns
        ],
        
        # Category breakdown
        "category_breakdown": stats["category_counts"],
        
        # Text fields (to be enhanced by LLM)
        "summary_text": None,  # Will be filled by LLM
        "top_concern_text": None,  # Will be filled by LLM
    }
    
    return summary


def _build_top_concerns(categorized_reports):
    """
    Build top concerns section organized by category
    
    :param categorized_reports: Dict of {category: [reports]} from rules_engine
    :return: Top concerns dict by category
    """
    concerns = {}
    
    for category in [org_report.CATEGORY_WELLNESS, org_report.CATEGORY_IT, 
                     org_report.CATEGORY_SAFETY, org_report.CATEGORY_ENERGY]:
        reports = categorized_reports.get(category, [])
        
        # Filter only concerns (not resolutions/celebrations)
        concern_reports = [
            r for r in reports 
            if r.get("sentiment") in [org_report.SENTIMENT_CONCERN, org_report.SENTIMENT_UPDATE]
        ]
        
        if concern_reports:
            concerns[category] = {
                "category": category,
                "count": len(concern_reports),
                "items": [
                    {
                        "location_id": r.get("location_id"),
                        "location_name": r.get("location_name"),
                        "report_type": r.get("report_type"),
                        "priority": r.get("priority"),
                        "severity_rank": r.get("severity_rank"),
                        "days_active": r.get("days_active"),
                        "short_description": r.get("short_description", ""),
                        "long_description": r.get("long_description", ""),
                        "resident_name": r.get("resident_name", ""),
                        "recommended_actions": r.get("recommended_actions", []),
                        
                        # Text enhancement fields (to be filled by LLM)
                        "enhanced_description": None,  # LLM enhancement
                        "context_explanation": None,  # LLM context
                    }
                    for r in concern_reports[:10]  # Top 10 per category
                ]
            }
    
    return concerns


def _build_top_celebrations(all_reports):
    """
    Build top celebrations section (resolutions and positive updates)
    
    :param all_reports: All filtered reports
    :return: Celebrations dict
    """
    # Find all resolutions and celebrations
    celebrations = [
        r for r in all_reports
        if r.get("sentiment") in [org_report.SENTIMENT_RESOLUTION, org_report.SENTIMENT_CELEBRATION]
    ]
    
    if not celebrations:
        return {
            "count": 0,
            "items": []
        }
    
    # Sort by severity_rank (most impactful resolutions first)
    celebrations_sorted = sorted(
        celebrations,
        key=lambda r: r.get("severity_rank", 0),
        reverse=True
    )
    
    return {
        "count": len(celebrations_sorted),
        "items": [
            {
                "location_id": r.get("location_id"),
                "location_name": r.get("location_name"),
                "report_type": r.get("report_type"),
                "sentiment": r.get("sentiment"),
                "days_to_resolve": r.get("days_active", 0),  # How long until resolved
                "short_description": r.get("short_description", ""),
                "long_description": r.get("long_description", ""),
                "category": org_report.get_category(r.get("report_type")),
                
                # Text enhancement fields
                "enhanced_description": None,  # LLM enhancement
            }
            for r in celebrations_sorted[:15]  # Top 15 celebrations
        ]
    }


def _build_trends(categorized_reports, stats):
    """
    Build trends section by analyzing patterns across locations
    
    :param categorized_reports: Dict of {category: [reports]}
    :param stats: Statistics dict
    :return: Trends dict by category
    """
    trends = {}
    
    for category in [org_report.CATEGORY_WELLNESS, org_report.CATEGORY_IT,
                     org_report.CATEGORY_SAFETY, org_report.CATEGORY_ENERGY]:
        reports = categorized_reports.get(category, [])
        
        if not reports:
            continue
        
        # Analyze patterns
        report_type_counts = {}
        for r in reports:
            report_type = r.get("report_type")
            if report_type not in report_type_counts:
                report_type_counts[report_type] = {
                    "count": 0,
                    "critical_count": 0,
                    "total_days_active": 0,
                    "locations": set()
                }
            
            report_type_counts[report_type]["count"] += 1
            report_type_counts[report_type]["locations"].add(r.get("location_id"))
            report_type_counts[report_type]["total_days_active"] += r.get("days_active", 0)
            
            if r.get("priority") == org_report.PRIORITY_CRITICAL:
                report_type_counts[report_type]["critical_count"] += 1
        
        # Convert to list and sort by count
        trend_items = []
        for report_type, data in report_type_counts.items():
            if data["count"] >= 2:  # Only trends affecting 2+ locations
                avg_days_active = data["total_days_active"] / data["count"]
                
                trend_items.append({
                    "report_type": report_type,
                    "locations_affected": len(data["locations"]),
                    "total_occurrences": data["count"],
                    "critical_count": data["critical_count"],
                    "average_days_active": round(avg_days_active, 1),
                    "severity_score": data["count"] * (1 + data["critical_count"]),
                    
                    # Text enhancement fields
                    "trend_description": None,  # LLM enhancement
                    "direction": "stable",  # Could be enhanced with historical data
                })
        
        # Sort by severity_score
        trend_items.sort(key=lambda t: t["severity_score"], reverse=True)
        
        if trend_items:
            trends[category] = {
                "category": category,
                "count": len(trend_items),
                "items": trend_items[:5]  # Top 5 trends per category
            }
    
    return trends


def _build_category_deep_dives(categorized_reports):
    """
    Build detailed category analysis sections
    
    :param categorized_reports: Dict of {category: [reports]}
    :return: Deep dive dict by category
    """
    deep_dives = {}
    
    for category in [org_report.CATEGORY_WELLNESS, org_report.CATEGORY_IT,
                     org_report.CATEGORY_SAFETY, org_report.CATEGORY_ENERGY]:
        reports = categorized_reports.get(category, [])
        
        if not reports:
            continue
        
        # Calculate category statistics
        critical_count = sum(1 for r in reports if r.get("priority") == org_report.PRIORITY_CRITICAL)
        warning_count = sum(1 for r in reports if r.get("priority") == org_report.PRIORITY_WARNING)
        avg_days_active = sum(r.get("days_active", 0) for r in reports) / len(reports)
        unique_locations = len(set(r.get("location_id") for r in reports))
        
        deep_dives[category] = {
            "category": category,
            "total_reports": len(reports),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "unique_locations": unique_locations,
            "average_days_active": round(avg_days_active, 1),
            
            # Top 5 locations in this category
            "top_locations": [
                {
                    "location_id": r.get("location_id"),
                    "location_name": r.get("location_name"),
                    "report_type": r.get("report_type"),
                    "priority": r.get("priority"),
                    "severity_rank": r.get("severity_rank"),
                    "days_active": r.get("days_active"),
                    "short_description": r.get("short_description", ""),
                }
                for r in reports[:5]
            ],
            
            # Text enhancement field
            "summary_text": None,  # LLM enhancement
        }
    
    return deep_dives


def get_llm_enhancement_tasks(report):
    """
    Extract all fields that need LLM enhancement
    Returns list of tasks for LLM to process
    
    :param report: Complete report dict from build_master_report()
    :return: List of enhancement task dicts
    """
    tasks = []
    
    # Task 1: Executive Summary Text
    exec_summary = report["sections"]["executive_summary"]
    tasks.append({
        "task_id": "executive_summary",
        "task_type": "summary",
        "section": "executive_summary",
        "data": {
            "total_locations": exec_summary["total_locations"],
            "critical_count": exec_summary["critical_count"],
            "warning_count": exec_summary["warning_count"],
            "top_concerns": exec_summary["top_concerns_list"],
            "category_breakdown": exec_summary["category_breakdown"],
        },
        "fields_to_fill": ["summary_text", "top_concern_text"],
        "max_words": 100,
    })
    
    # Task 2: Enhance Top Concern Descriptions (per category)
    top_concerns = report["sections"]["top_concerns"]
    for category, concerns_data in top_concerns.items():
        for idx, item in enumerate(concerns_data["items"]):
            tasks.append({
                "task_id": f"concern_{category}_{idx}",
                "task_type": "enhance_concern",
                "section": "top_concerns",
                "category": category,
                "item_index": idx,
                "data": item,
                "fields_to_fill": ["enhanced_description", "context_explanation"],
                "max_words": 50,
            })
    
    # Task 3: Enhance Celebration Descriptions
    celebrations = report["sections"]["top_celebrations"]
    for idx, item in enumerate(celebrations["items"]):
        tasks.append({
            "task_id": f"celebration_{idx}",
            "task_type": "enhance_celebration",
            "section": "top_celebrations",
            "item_index": idx,
            "data": item,
            "fields_to_fill": ["enhanced_description"],
            "max_words": 40,
        })
    
    # Task 4: Enhance Trend Descriptions
    trends = report["sections"]["trends"]
    for category, trends_data in trends.items():
        for idx, item in enumerate(trends_data["items"]):
            tasks.append({
                "task_id": f"trend_{category}_{idx}",
                "task_type": "enhance_trend",
                "section": "trends",
                "category": category,
                "item_index": idx,
                "data": item,
                "fields_to_fill": ["trend_description"],
                "max_words": 30,
            })
    
    # Task 5: Category Deep Dive Summaries
    deep_dives = report["sections"]["category_deep_dives"]
    for category, dive_data in deep_dives.items():
        tasks.append({
            "task_id": f"deep_dive_{category}",
            "task_type": "category_summary",
            "section": "category_deep_dives",
            "category": category,
            "data": dive_data,
            "fields_to_fill": ["summary_text"],
            "max_words": 60,
        })
    
    return tasks


def apply_llm_enhancement(report, task_id, enhanced_text_dict):
    """
    Apply LLM-enhanced text back into report structure
    
    :param report: Complete report dict
    :param task_id: Task ID from get_llm_enhancement_tasks()
    :param enhanced_text_dict: Dict of {field_name: enhanced_text}
    :return: Updated report
    """
    # Parse task_id to determine location
    if task_id == "executive_summary":
        for field, text in enhanced_text_dict.items():
            report["sections"]["executive_summary"][field] = text
    
    elif task_id.startswith("concern_"):
        parts = task_id.split("_")
        category = parts[1]
        idx = int(parts[2])
        for field, text in enhanced_text_dict.items():
            report["sections"]["top_concerns"][category]["items"][idx][field] = text
    
    elif task_id.startswith("celebration_"):
        idx = int(task_id.split("_")[1])
        for field, text in enhanced_text_dict.items():
            report["sections"]["top_celebrations"]["items"][idx][field] = text
    
    elif task_id.startswith("trend_"):
        parts = task_id.split("_")
        category = parts[1]
        idx = int(parts[2])
        for field, text in enhanced_text_dict.items():
            report["sections"]["trends"][category]["items"][idx][field] = text
    
    elif task_id.startswith("deep_dive_"):
        category = task_id.split("_", 2)[2]
        for field, text in enhanced_text_dict.items():
            report["sections"]["category_deep_dives"][category][field] = text
    
    return report


