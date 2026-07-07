"""
Created on May 5, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Deterministic Resident Report Builder
=====================================

Builds an organization-wide resident-report skeleton from per-location
``resident_report`` state dicts written by
``intelligence.reports.location_reports_resident_microservice``.

Each per-location resident report has this shape::

    {
        "timestamp_ms": int,
        "resident_name": str,
        "location_name": str,
        "report_date": str,
        "dashboard_header": str,
        "dashboard_status": str,
        "wellness_data": {
            "score": int|None,
            "delta": int|None,
            "categories": {
                "sleep": {"value": int, "delta": int, "display": str, ...},
                "bathroom": {...}, "stability": {...},
                "social": {...}, "mobility": {...},
            },
        },
        "journal_summary": str|None,
        "falls_data": [ {"description": str, ...}, ... ],
        "bathroom_data": {"count": int, "description": str},
        "score_history": [...],
        "highlights_data": ...,
    }

The builder produces a deterministic skeleton with empty ``overview_text``;
the microservice fills that field via a single LLM call when permitted.
"""

import json

from . import services


def latest_report_per_location(content):
    """
    Pick the most recent ``resident_report`` snapshot from each location.

    :param content: Data request payload
        ``{location_id: {"resident_report": {ts_ms: report_dict}}}``
    :return: Dict ``{location_id: report_dict}`` (most recent ts per location)
    """
    latest = {}
    for location_id, state_map in (content or {}).items():
        timeseries = (state_map or {}).get(services.STATE_RESIDENT_REPORT) or {}
        if not timeseries:
            continue
        try:
            most_recent_ts = max(int(ts) for ts in timeseries.keys())
        except (TypeError, ValueError):
            continue
        report = timeseries.get(most_recent_ts) or timeseries.get(str(most_recent_ts))
        if report:
            latest[str(location_id)] = report
    return latest


def _criticality_score(report):
    """
    Returns a tuple suitable for ``sorted()`` so that:
      1. Residents with falls come first
      2. Then residents with low wellness score (<50)
      3. Then by ascending wellness score
      4. Tie-break by location name for stable ordering
    """
    falls = len(report.get("falls_data") or [])
    wellness = (report.get("wellness_data") or {}).get("score")
    has_falls = 1 if falls > 0 else 0
    is_concerning = (
        1 if (wellness is not None and wellness < services.WELLNESS_SCORE_CONCERNING)
        else 0
    )
    score_for_sort = wellness if wellness is not None else 999
    name = report.get("location_name") or ""
    return (-has_falls, -is_concerning, score_for_sort, name)


def sort_by_criticality(reports_by_location):
    """
    Return a list of (location_id, report) tuples sorted with the most
    critical residents first.
    """
    return sorted(
        reports_by_location.items(),
        key=lambda item: _criticality_score(item[1]),
    )


def _population_metadata(sorted_reports):
    """Aggregate counts across the whole population."""
    total = len(sorted_reports)
    with_falls = 0
    total_falls = 0
    with_low_wellness = 0
    wellness_values = []
    with_journal = 0
    night_bathroom_total = 0
    with_critical_events = 0
    total_critical_events = 0

    for _location_id, report in sorted_reports:
        falls = report.get("falls_data") or []
        if falls:
            with_falls += 1
            total_falls += len(falls)
        wellness = (report.get("wellness_data") or {}).get("score")
        if wellness is not None:
            wellness_values.append(wellness)
            if wellness < services.WELLNESS_SCORE_CONCERNING:
                with_low_wellness += 1
        if report.get("journal_summary"):
            with_journal += 1
        bathroom = report.get("bathroom_data") or {}
        if isinstance(bathroom.get("count"), (int, float)):
            night_bathroom_total += int(bathroom["count"])
        narratives = report.get("narratives") or []
        if narratives:
            with_critical_events += 1
            total_critical_events += len(narratives)

    avg_wellness = (
        round(sum(wellness_values) / len(wellness_values), 1)
        if wellness_values else None
    )

    return {
        "total_residents": total,
        "with_falls": with_falls,
        "total_falls": total_falls,
        "with_low_wellness": with_low_wellness,
        "with_journal": with_journal,
        "avg_wellness_score": avg_wellness,
        "night_bathroom_total": night_bathroom_total,
        "with_critical_events": with_critical_events,
        "total_critical_events": total_critical_events,
    }


def build_report_skeleton(reports_by_location, organization_name, timestamp_ms,
                          disable_llm=False):
    """
    Build the deterministic report skeleton.

    :param reports_by_location: Dict {location_id: report_dict} (latest per location)
    :param organization_name: Display name for the title page (or empty string)
    :param timestamp_ms: Generation timestamp
    :param disable_llm: When True, ``enhancement_tasks`` is empty
    :return: Skeleton dict ready for the LLM pipeline / PDF generator
    """
    sorted_pairs = sort_by_criticality(reports_by_location or {})
    metadata = _population_metadata(sorted_pairs)

    section1 = {
        "overview_text": "",
        "stats": metadata,
    }

    section2_residents = [
        {"location_id": location_id, **report}
        for location_id, report in sorted_pairs
    ]

    report = {
        "timestamp_ms": timestamp_ms,
        "organization_name": organization_name or "",
        "metadata": metadata,
        "section1_overview": section1,
        "section2_residents": section2_residents,
        "enhancement_tasks": [],
    }

    if not disable_llm and section2_residents:
        report["enhancement_tasks"] = [
            {
                "task_id": services.TASK_EXECUTIVE_SUMMARY,
                "task_type": services.TASK_EXECUTIVE_SUMMARY,
                "data": _build_summary_payload(metadata, section2_residents,
                                               organization_name),
                "fields_to_fill": ["overview_text"],
            }
        ]

    return report


def _build_summary_payload(metadata, residents, organization_name):
    """
    Project the most useful executive-summary inputs out of the population.
    Top-N most-critical residents are summarized without identifying names.
    """
    top_n = []
    for resident in residents[:5]:
        wellness = (resident.get("wellness_data") or {}).get("score")
        falls = len(resident.get("falls_data") or [])
        top_n.append({
            "wellness_score": wellness,
            "falls_today": falls,
            "journal": (resident.get("journal_summary") or "")[:240],
        })
    return {
        "organization_name": organization_name or "",
        "metadata": metadata,
        "most_critical": top_n,
    }


def build_executive_summary_messages(task_data):
    """
    Build the [system, user_example, assistant_example, user_data] message
    list for the executive-summary LLM call.

    :param task_data: ``task["data"]`` produced by ``_build_summary_payload``
    :return: (messages, max_tokens)
    """
    system_content = (
        services.SYSTEM_PROMPT_BASE + "\n\n"
        "YOUR TASK: Write a population-level executive-summary paragraph "
        "for the 'Executive Overview' section of a daily resident report "
        "PDF.\n\n"
        "REQUIREMENTS:\n"
        "- 3-5 sentences, maximum 180 words\n"
        "- Warm, professional healthcare language for administrators\n"
        "- Be specific with the numbers provided (residents, falls, "
        "average wellness)\n"
        "- Highlight community strengths and areas needing attention\n"
        "- Do not name or otherwise identify individual residents\n\n"
        "OUTPUT FORMAT:\n"
        "overview_text: <your 3-5 sentence paragraph here>"
    )

    example_input = (
        "DATA:\n"
        "- Organization: Maple Grove\n"
        "- Total residents reported on today: 24\n"
        "- Residents with detected falls today: 1 (1 fall total)\n"
        "- Residents with wellness score below 50: 3\n"
        "- Average wellness score across reported residents: 71.4\n"
        "- Residents with journal narrative: 22\n"
        "- Top concerns (no names): "
        '[{"wellness_score": 38, "falls_today": 1, '
        '"journal": "Resident reported feeling unsteady this morning."}, '
        '{"wellness_score": 44, "falls_today": 0, '
        '"journal": "Quiet day, fewer bathroom visits than usual."}]'
    )

    example_output = (
        "overview_text: Across 24 residents reported on today at Maple "
        "Grove, the community averaged a wellness score of 71.4 and "
        "produced 22 journal narratives, indicating broad sensor coverage "
        "and engagement. One resident experienced a single fall event and "
        "warrants a same-day check-in, while three additional residents "
        "scored below the 50-point wellness threshold and may benefit "
        "from follow-up. Reduced bathroom activity and reports of "
        "unsteadiness in the most concerning cases suggest mobility and "
        "hydration as appropriate focus areas for today's care huddle."
    )

    metadata = task_data.get("metadata") or {}
    org_line = (
        f"- Organization: {task_data.get('organization_name')}\n"
        if task_data.get("organization_name") else ""
    )
    user_content = (
        "DATA:\n"
        f"{org_line}"
        f"- Total residents reported on today: {metadata.get('total_residents', 0)}\n"
        f"- Residents with detected falls today: {metadata.get('with_falls', 0)} "
        f"({metadata.get('total_falls', 0)} fall total)\n"
        f"- Residents with wellness score below "
        f"{services.WELLNESS_SCORE_CONCERNING}: {metadata.get('with_low_wellness', 0)}\n"
        f"- Average wellness score across reported residents: "
        f"{metadata.get('avg_wellness_score') if metadata.get('avg_wellness_score') is not None else 'n/a'}\n"
        f"- Residents with journal narrative: {metadata.get('with_journal', 0)}\n"
        f"- Top concerns (no names): "
        f"{json.dumps(task_data.get('most_critical') or [], indent=2)}"
    )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": example_input},
        {"role": "assistant", "content": example_output},
        {"role": "user", "content": user_content},
    ]
    return messages, services.LLM_MAX_TOKENS_SUMMARY


def apply_llm_enhancement(report, task_id, enhanced_text_dict):
    """
    Inject LLM-generated text into the report skeleton.

    :param report: Report skeleton dict
    :param task_id: Task identifier
    :param enhanced_text_dict: Dict of {field_name: text}
    """
    if task_id == services.TASK_EXECUTIVE_SUMMARY:
        for field, text in (enhanced_text_dict or {}).items():
            report["section1_overview"][field] = text
