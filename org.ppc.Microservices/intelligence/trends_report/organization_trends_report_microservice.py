"""
Created on March 13, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Organization Trends Report Microservice
========================================

Aggregates TRENDS_NOW and TRENDS_METADATA location states from all child
locations and produces a PDF report with matplotlib plots and LLM-enhanced text.

Pipeline:
1. Pull trends data from all locations (async_data_request_ready)
2. Build deterministic report skeleton (report_builder)
3. Enhance Section 1, Section 2 (per-location), and Section 3 text via sequential LLM calls
4. Generate matplotlib plots and fpdf2 PDF, email to admins
"""

import datetime
import json
import re

import utilities.utilities as utilities  # type: ignore
import properties  # type: ignore
from intelligence.intelligence import Intelligence  # type: ignore

from . import report_builder, services

# Notification category
NOTIFICATION_CATEGORY = (
    utilities.ORGANIZATION_USER_NOTIFICATION_CATEGORY_REPORTS
)


class OrganizationTrendsReportMicroservice(Intelligence):
    """
    Organization-level microservice that aggregates trend data from all child
    locations and generates a PDF report with matplotlib statistical plots,
    enhanced with LLM-generated natural language summaries.

    Trigger: Manual only via 'generate_trends_report' datastream message.

    Pipeline:
    1. Pull TRENDS_NOW + TRENDS_METADATA from all locations
    2. Build deterministic report skeleton
    3. Enhance Section 1, Section 2 (per-location), and Section 3 via LLM
    4. Generate matplotlib plots + fpdf2 PDF and email to admins
    """

    def __init__(self, botengine, parent):
        """
        Initialize the microservice
        :param botengine: BotEngine environment
        :param parent: Parent organization object
        """
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        """
        Initialize the microservice when it is first created or instantiated
        :param botengine: BotEngine environment
        """
        pass

    def destroy(self, botengine):
        """
        Destroy the microservice
        :param botengine: BotEngine environment
        """
        pass

    def new_version(self, botengine):
        """
        New bot version detected
        :param botengine: BotEngine environment
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(">new_version()")

    # ==========================================================================
    # Datastream Message Handlers
    # ==========================================================================
    def datastream_updated(self, botengine, address, content):
        """
        Datastream message received
        :param botengine: BotEngine environment
        :param address: Data stream address
        :param content: Data stream content (dict)
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    def trends_report_run_test(self, botengine, content):
        """
        Manual trigger to generate the trends report.
        :param botengine: BotEngine environment
        :param content: Data stream content (dict)
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">trends_report_run_test()")
        test_case = content.get("test_case", "unknown")
        if test_case == "generate_report":
            self._request_trends_data(
                botengine,
                disable_llm=content.get("disable_llm", False),
            )
        logger.info("<trends_report_run_test()")

    # ==========================================================================
    # Timer Handler
    # ==========================================================================
    def timer_fired(self, botengine, argument):
        """
        Timer fired - bridges async data request to synchronous processing.
        :param botengine: BotEngine environment
        :param argument: Argument applied when setting the timer
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        if not isinstance(argument, dict):
            return

        timer_type = argument.get("type")

        if timer_type == "data_request_timeout":
            retry_count = argument.get("retry_count", 0)

            state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)

            if state is not None and state.get("ready_for_processing"):
                logger.info("|timer_fired() Report skeleton ready, starting LLM pipeline")
                state["ready_for_processing"] = False
                botengine.save_variable(
                    services.STATE_VAR_REPORT_IN_PROGRESS, state, overwrite=True
                )

                report = state["report"]
                if state.get("disable_llm"):
                    logger.info("|timer_fired() LLM disabled, skipping enhancement tasks")
                    self._finalize_report(
                        botengine, report, state["start_time"]
                    )
                elif report.get("enhancement_tasks"):
                    self._process_next_enhancement_task(
                        botengine, report["enhancement_tasks"][0]
                    )
                else:
                    self._finalize_report(
                        botengine, report, state["start_time"]
                    )
            else:
                if retry_count >= services.MAX_DATA_REQUEST_RETRIES:
                    logger.warning(
                        f"|timer_fired() Max retries ({services.MAX_DATA_REQUEST_RETRIES}) exceeded. Giving up."
                    )
                    return

                logger.warning(
                    f"|timer_fired() Data request timeout, retry {retry_count + 1}/{services.MAX_DATA_REQUEST_RETRIES}"
                )
                self.start_timer_s(
                    botengine,
                    services.DATA_REQUEST_TIMEOUT_S,
                    argument={
                        "type": "data_request_timeout",
                        "retry_count": retry_count + 1,
                    },
                    reference="data_request_timeout_trends",
                )

    # ==========================================================================
    # Data Request Handlers
    # ==========================================================================
    def async_data_request_ready(self, botengine, reference, content):
        """
        Data request ready.

        IMPORTANT: This method executes in an asynchronous environment where you
        are NOT allowed to set timers, manage class variables, or perform stateful
        operations. Data is saved to a variable for the timer bridge to pick up.

        :param botengine: BotEngine environment
        :param reference: Data request reference
        :param content: Data request content
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">async_data_request_ready() reference={reference}")

        if reference == services.DATA_REQUEST_REFERENCE_TRENDS:
            self._process_trends_data(botengine, content)

        logger.info("<async_data_request_ready()")

    # ==========================================================================
    # LLM Response Handler
    # ==========================================================================
    def llm_response(self, botengine, response, reference, argument):
        """
        LLM response received
        :param botengine: BotEngine environment
        :param response: LLM response content
        :param reference: Reference ID for tracking
        :param argument: Original argument passed to llm_chat()
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">llm_response() reference={reference}")

        Intelligence.llm_response(self, botengine, response, reference, argument)

        if reference == services.LLM_REFERENCE_TRENDS_REPORT:
            self._handle_report_llm_response(botengine, response, argument)

        logger.info("<llm_response()")

    # ==========================================================================
    # Pipeline Methods
    # ==========================================================================
    def _request_trends_data(self, botengine, disable_llm=False):
        """
        Request TRENDS_NOW and TRENDS_METADATA from all child locations.
        :param botengine: BotEngine environment
        :param disable_llm: True to skip LLM enhancement and generate PDF with deterministic text only
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">_request_trends_data() disable_llm={disable_llm}")

        # Check if we should use LLM synthesis        
        llm_allowed = properties.get_property(botengine, "LLM_FEATURES_ALLOWED", False)
        if not llm_allowed:
            disable_llm = True

        self.disable_llm = disable_llm

        # Guard against concurrent report generation
        existing = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        if existing is not None:
            logger.warning(
                "|_request_trends_data() Report already in progress, skipping"
            )
            return

        cutoff_ms = botengine.get_timestamp() - utilities.ONE_MONTH_MS

        botengine.request_data(
            type=botengine.DATA_REQUEST_TYPE_LOCATION_TIME_STATES,
            reference=services.DATA_REQUEST_REFERENCE_TRENDS,
            oldest_timestamp_ms=cutoff_ms,
            newest_timestamp_ms=botengine.get_timestamp() - utilities.ONE_DAY_MS, # Ingore current day
            names=[services.TRENDS_NOW_NAME],
        )

        self.start_timer_s(
            botengine,
            services.DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": "data_request_timeout",
                "retry_count": 0,
            },
            reference="data_request_timeout_trends",
        )

        logger.info("<_request_trends_data()")

    def _process_trends_data(self, botengine, content):
        """
        Process raw data request response into report skeleton.
        Called from async_data_request_ready (async context).

        :param botengine: BotEngine environment
        :param content: Data request content {location_id: {state_name: {ts: data}}}
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_process_trends_data()")

        # Extract TRENDS_METADATA from the first location that has it
        metadata = {}
        for location_id in content:
            state = botengine.get_state(services.TRENDS_METADATA_NAME, location_id=location_id)
            if state:
                metadata.update(state)
        # Extract TRENDS_NOW time-series data for all locations
        trends_data = {}
        for location_id in content:
            location_trends = content[location_id].get(services.TRENDS_NOW_NAME, {})
            if location_trends:
                trends_data[str(location_id)] = location_trends

        if not trends_data:
            logger.warning(
                "|_process_trends_data() No trends data found across locations. Skipping."
            )
            logger.info("<_process_trends_data()")
            return

        # Sort locations by criticality (most critical first)
        trends_data = self._sort_by_criticality(trends_data)

        logger.info(
            f"|_process_trends_data() Processing trends from {len(trends_data)} locations"
        )

        # Build deterministic report skeleton
        report_skeleton = report_builder.build_report_skeleton(
            trends_data, metadata, botengine.get_timestamp()
        )

        # Check if LLM is disabled (stored on instance by _request_trends_data)
        disable_llm = getattr(self, "disable_llm", False)

        # Save skeleton for timer bridge to pick up
        botengine.save_variable(
            services.STATE_VAR_REPORT_IN_PROGRESS,
            {
                "report": report_skeleton,
                "tasks_remaining": len(report_skeleton["enhancement_tasks"]),
                "tasks_completed": 0,
                "start_time": botengine.get_timestamp(),
                "ready_for_processing": True,
                "disable_llm": disable_llm,
            },
            overwrite=True,
        )

        logger.info(
            f"|_process_trends_data() Skeleton saved with {len(report_skeleton['enhancement_tasks'])} enhancement tasks"
        )
        logger.info("<_process_trends_data()")

    @staticmethod
    def _sort_by_criticality(trends_data):
        """
        Sort trends_data dict by location criticality (most critical first).

        Scoring per location from latest trends:
        - Primary: count of critical trends (|z| >= 2.5)
        - Secondary: count of concerning trends (|z| >= 1.5)
        - Tertiary: average absolute z-score

        :param trends_data: Dict {location_id: {day_ms: {trend_id: {...}}}}
        :return: New dict with same data, ordered most-critical-first
        """
        def _criticality_key(location_id):
            days = trends_data[location_id]
            latest = report_builder._get_latest_trends(days)
            critical = 0
            concerning = 0
            abs_zscores = []
            for trend_data in latest.values():
                z = trend_data.get("zscore")
                if z is not None:
                    abs_z = abs(z)
                    abs_zscores.append(abs_z)
                    if abs_z >= services.ZSCORE_CRITICAL:
                        critical += 1
                    elif abs_z >= services.ZSCORE_CONCERNING:
                        concerning += 1
            avg_abs_z = sum(abs_zscores) / len(abs_zscores) if abs_zscores else 0
            return (-critical, -concerning, -avg_abs_z)

        sorted_ids = sorted(trends_data.keys(), key=_criticality_key)
        return {lid: trends_data[lid] for lid in sorted_ids}

    # ==========================================================================
    # LLM Enhancement Pipeline
    # ==========================================================================
    def _process_next_enhancement_task(self, botengine, task):
        """
        Send the next LLM enhancement task.
        :param botengine: BotEngine environment
        :param task: Enhancement task dict
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">_process_next_enhancement_task() task_id={task['task_id']}")

        org_name = botengine.get_organization_name()
        messages, max_tokens = self._build_enhancement_messages(task, org_name)
        if not messages:
            logger.warning(
                f"|_process_next_enhancement_task() Empty messages for task {task['task_id']}, skipping"
            )
            return

        self.llm_chat(
            botengine,
            reference=services.LLM_REFERENCE_TRENDS_REPORT,
            argument={
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "fields_to_fill": task["fields_to_fill"],
            },
            messages=messages,
            model=services.LLM_MODEL,
            max_tokens=max_tokens,
            temperature=services.LLM_TEMPERATURE,
        )

        logger.info("<_process_next_enhancement_task()")

    def _build_enhancement_messages(self, task, org_name=""):
        """
        Build LLM message list for a given enhancement task.

        Returns a tuple of (messages, max_tokens) where messages follows the
        system + few-shot + user data pattern.

        :param task: Enhancement task dict
        :param org_name: Organization name for context
        :return: Tuple of (messages list, max_tokens int) or ([], 0)
        """
        task_type = task["task_type"]
        data = task["data"]

        if task_type == services.TASK_ANALYSIS_OVERVIEW:
            return self._build_overview_messages(data, org_name)
        elif task_type == services.TASK_INDIVIDUAL_ANALYSIS:
            return self._build_individual_messages(data)
        elif task_type == services.TASK_REVIEW_SUMMARY:
            return self._build_review_messages(data, org_name)

        return [], 0

    def _build_overview_messages(self, data, org_name=""):
        """
        Build messages for ANALYSIS_OVERVIEW task.
        :param data: Task data dict
        :param org_name: Organization name for context
        :return: Tuple of (messages list, max_tokens)
        """
        cat_display = {}
        for cat, stats in data.get("category_stats", {}).items():
            label = services.TREND_CATEGORY_LABELS.get(cat, cat)
            cat_display[label] = {
                "trend_types": stats.get("trend_count", 0),
                "locations": stats.get("location_count", 0),
                "trend_names": stats.get("trend_names", []),
            }

        system_content = (
            services.SYSTEM_PROMPT_BASE + "\n\n"
            "YOUR TASK: Write a population-level health overview paragraph for "
            "the 'Analysis Overview' section of a trends report PDF.\n\n"
            "REQUIREMENTS:\n"
            "- 3-4 sentences, maximum 150 words\n"
            "- Warm, professional healthcare language appropriate for administrators\n"
            "- Be specific with numbers from the data provided\n"
            "- Highlight community strengths and areas needing attention\n"
            "- Mention the monitoring coverage (location count, trend categories)\n\n"
            "OUTPUT FORMAT:\n"
            "overview_text: <your 3-4 sentence paragraph here>"
        )

        example_input = (
            "DATA:\n"
            "- Total locations monitored: 12\n"
            "- Total trend types tracked: 8\n"
            "- Reporting period: past 30 days\n"
            '- Category statistics: {"Sleep": {"trend_types": 3, "locations": 12}, '
            '"Bathroom": {"trend_types": 2, "locations": 12}, '
            '"Activity": {"trend_types": 2, "locations": 10}, '
            '"Social": {"trend_types": 1, "locations": 8}}\n'
            "- Notable outliers (high z-scores): 5"
        )

        example_output = (
            "overview_text: Across 12 monitored locations over the past 30 days, "
            "the community shows strong engagement in Sleep and Bathroom monitoring "
            "with all locations actively tracked across 8 trend types. Activity trends "
            "are healthy in 10 of 12 locations, while Social engagement is tracked at "
            "8 locations. Five notable outliers were identified, primarily in the Sleep "
            "and Activity categories, suggesting targeted follow-up may be warranted "
            "for those residents."
        )

        org_line = f"- Organization: {org_name}\n" if org_name else ""
        user_content = (
            "DATA:\n"
            f"{org_line}"
            f"- Total locations monitored: {data.get('total_locations', 0)}\n"
            f"- Total trend types tracked: {data.get('total_trend_types', 0)}\n"
            f"- Reporting period: past 30 days\n"
            f"- Category statistics: {json.dumps(cat_display, indent=2)}\n"
            f"- Notable outliers (high z-scores): {data.get('outlier_count', 0)}"
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": example_input},
            {"role": "assistant", "content": example_output},
            {"role": "user", "content": user_content},
        ]

        return messages, services.LLM_MAX_TOKENS_OVERVIEW

    def _build_individual_messages(self, data):
        """
        Build messages for INDIVIDUAL_ANALYSIS task.
        :param data: Task data dict
        :return: Tuple of (messages list, max_tokens)
        """
        outlier_display = []
        for o in data.get("outlier_trends", []):
            direction_label = "above" if o.get("direction") == "high" else "below"
            outlier_display.append({
                "trend": o.get("title", ""),
                "category": o.get("category", ""),
                "current_value": f"{o.get('display', '')} {o.get('units', '')}".strip(),
                "z_score": o.get("zscore", 0),
                "direction": f"{direction_label} average",
            })

        health = data.get("health_distribution", {})
        total = sum(health.values())
        health_summary = (
            f"{health.get('healthy', 0)} healthy, "
            f"{health.get('concerning', 0)} concerning, "
            f"{health.get('critical', 0)} critical "
            f"out of {total} total trends"
        )

        system_content = (
            services.SYSTEM_PROMPT_BASE + "\n\n"
            "YOUR TASK: Write a brief individual wellness summary for a single "
            "resident's page in the trends report PDF. Focus on any outlying "
            "trends and what they may indicate.\n\n"
            "REQUIREMENTS:\n"
            "- 2-3 sentences, maximum 100 words\n"
            "- Warm, professional healthcare language\n"
            "- Focus on outlying values and what they might mean for the resident\n"
            "- Be specific with trend names and values provided\n"
            "- If no outliers exist, provide a brief positive summary\n"
            "- Do not name or identify the resident\n\n"
            "OUTPUT FORMAT:\n"
            "individual_text: <your 2-3 sentence paragraph here>"
        )

        example_input = (
            "RESIDENT DATA:\n"
            "- Total trends tracked: 6\n"
            "- Health distribution: 4 healthy, 1 concerning, 1 critical out of 6 total trends\n"
            "- Outlying trends (z-score >= 1.5):\n"
            '  [{"trend": "Bedtime", "category": "Sleep", "current_value": "11:45 PM", '
            '"z_score": 2.1, "direction": "above average"}, '
            '{"trend": "Bathroom Visits", "category": "Bathroom", "current_value": "8 Visits", '
            '"z_score": -1.8, "direction": "below average"}]'
        )

        example_output = (
            "individual_text: This resident's Bedtime has shifted notably later "
            "to 11:45 PM (z-score 2.1), which is well above their 30-day average "
            "and may warrant attention to sleep hygiene. Additionally, Bathroom "
            "Visits have decreased to 8 per day (z-score -1.8), which could "
            "indicate changes in hydration or mobility patterns."
        )

        user_content = (
            "RESIDENT DATA:\n"
            f"- Location ID: {data.get('location_id', 'Unknown')}\n"
            f"- Total trends tracked: {data.get('total_trends', 0)}\n"
            f"- Health distribution: {health_summary}\n"
            f"- Outlying trends (z-score >= {services.ZSCORE_CONCERNING}):\n"
            f"  {json.dumps(outlier_display, indent=2) if outlier_display else 'None - all trends within normal range'}"
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": example_input},
            {"role": "assistant", "content": example_output},
            {"role": "user", "content": user_content},
        ]

        return messages, services.LLM_MAX_TOKENS_INDIVIDUAL

    def _build_review_messages(self, data, org_name=""):
        """
        Build messages for REVIEW_SUMMARY task.
        :param data: Task data dict
        :param org_name: Organization name for context
        :return: Tuple of (messages list, max_tokens)
        """
        patterns_display = []
        for p in data.get("cross_location_patterns", [])[:5]:
            label = services.TREND_CATEGORY_LABELS.get(
                p.get("category", ""), p.get("category", "")
            )
            patterns_display.append({
                "trend": p.get("title", ""),
                "category": label,
                "affected_locations": p.get("affected_locations", 0),
                "avg_zscore": p.get("avg_zscore", 0),
            })

        health_display = {}
        for cat, counts in data.get("category_health", {}).items():
            label = services.TREND_CATEGORY_LABELS.get(cat, cat)
            health_display[label] = counts

        system_content = (
            services.SYSTEM_PROMPT_BASE + "\n\n"
            "YOUR TASK: Write a cross-location review and recommendations "
            "paragraph for the 'Review' section of a trends report PDF. This "
            "section is for administrators who need actionable next steps.\n\n"
            "REQUIREMENTS:\n"
            "- 4-6 sentences, maximum 200 words\n"
            "- Professional healthcare administration tone\n"
            "- Focus on trends that affect multiple locations (systemic patterns)\n"
            "- Provide specific, actionable recommendations\n"
            "- Reference actual categories and data values\n"
            "- Highlight opportunities for programmatic improvement\n\n"
            "OUTPUT FORMAT:\n"
            "review_text: <your 4-6 sentence paragraph here>"
        )

        example_input = (
            "COMMUNITY DATA:\n"
            "- Total locations monitored: 10\n"
            '- Cross-location patterns: [{"trend": "Bedtime", "category": "Sleep", '
            '"affected_locations": 4, "avg_zscore": 1.9}, '
            '{"trend": "Activity Score", "category": "Activity", '
            '"affected_locations": 3, "avg_zscore": -1.6}]\n'
            '- Category health distribution: {"Sleep": {"healthy": 14, "concerning": 5, '
            '"critical": 1}, "Activity": {"healthy": 8, "concerning": 4, "critical": 0}, '
            '"Bathroom": {"healthy": 18, "concerning": 2, "critical": 0}}'
        )

        example_output = (
            "review_text: The most widespread concern across the community is later "
            "bedtimes, affecting 4 of 10 locations with an average z-score of 1.9 in "
            "the Sleep category. This pattern suggests a potential community-wide shift "
            "in evening routines that may benefit from programmatic review of evening "
            "activity schedules. Activity scores are also trending below average at 3 "
            "locations, which could indicate reduced engagement opportunities. Bathroom "
            "patterns remain largely healthy with only 2 concerning readings across 10 "
            "locations. We recommend prioritizing sleep hygiene outreach for the 4 "
            "affected locations and reviewing daytime activity programming to improve "
            "engagement levels."
        )

        org_line = f"- Organization: {org_name}\n" if org_name else ""
        user_content = (
            "COMMUNITY DATA:\n"
            f"{org_line}"
            f"- Total locations monitored: {data.get('total_locations', 0)}\n"
            f"- Cross-location patterns: {json.dumps(patterns_display, indent=2)}\n"
            f"- Category health distribution: {json.dumps(health_display, indent=2)}"
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": example_input},
            {"role": "assistant", "content": example_output},
            {"role": "user", "content": user_content},
        ]

        return messages, services.LLM_MAX_TOKENS_REVIEW

    def _handle_report_llm_response(self, botengine, response, argument):
        """
        Handle LLM response for text enhancement tasks.
        :param botengine: BotEngine environment
        :param response: LLM response dict
        :param argument: Original argument with task info
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_handle_report_llm_response()")

        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        if not state:
            logger.error("|_handle_report_llm_response() No report in progress found")
            return

        report = state["report"]
        task_id = argument.get("task_id")
        fields_to_fill = argument.get("fields_to_fill", [])

        logger.info(f"|_handle_report_llm_response() Processing task: {task_id}")

        try:
            # Extract text from OpenAI response format
            try:
                content = response["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError, AttributeError):
                if response is None:
                    content = ""
                else:
                    content = response.get("content", "")
                    if isinstance(content, str):
                        content = content.strip()
                    else:
                        content = ""
                logger.warning(
                    f"|_handle_report_llm_response() Fallback content extraction, length={len(content)}"
                )

            logger.info(
                f"|_handle_report_llm_response() Extracted LLM content ({len(content)} chars)"
            )

            # Parse and apply enhancement
            enhanced_text = self._parse_llm_text_response(content, fields_to_fill)
            report_builder.apply_llm_enhancement(report, task_id, enhanced_text)

            # Update progress
            state["report"] = report
            state["tasks_completed"] += 1
            tasks_remaining = state["tasks_remaining"] - 1
            state["tasks_remaining"] = tasks_remaining

            logger.info(
                f"|_handle_report_llm_response() Task completed. {tasks_remaining} tasks remaining"
            )

            botengine.save_variable(
                services.STATE_VAR_REPORT_IN_PROGRESS, state, overwrite=True
            )

            if tasks_remaining <= 0:
                logger.info(
                    "|_handle_report_llm_response() All tasks complete, finalizing report"
                )
                self._finalize_report(botengine, report, state["start_time"])
            else:
                all_tasks = report["enhancement_tasks"]
                next_task_index = state["tasks_completed"]
                if next_task_index < len(all_tasks):
                    self._process_next_enhancement_task(
                        botengine, all_tasks[next_task_index]
                    )

        except Exception as e:
            import traceback

            logger.error(
                f"|_handle_report_llm_response() Error processing enhancement: {e}"
            )
            logger.error(traceback.format_exc())

            # Advance pipeline despite error — skip this task
            state["tasks_completed"] += 1
            tasks_remaining = state["tasks_remaining"] - 1
            state["tasks_remaining"] = tasks_remaining
            botengine.save_variable(
                services.STATE_VAR_REPORT_IN_PROGRESS, state, overwrite=True
            )

            if tasks_remaining <= 0:
                self._finalize_report(botengine, report, state["start_time"])
            else:
                all_tasks = report["enhancement_tasks"]
                next_task_index = state["tasks_completed"]
                if next_task_index < len(all_tasks):
                    self._process_next_enhancement_task(
                        botengine, all_tasks[next_task_index]
                    )

        logger.info("<_handle_report_llm_response()")

    def _parse_llm_text_response(self, content, expected_fields):
        """
        Parse LLM text response into field dict.
        Expected format: "field_name: value"

        :param content: LLM response text
        :param expected_fields: List of field names to extract
        :return: Dict of {field_name: text}
        """
        result = {}
        for field in expected_fields:
            pattern = rf"{field}:\s*(.+?)(?=\n\w+:|$)"
            match = re.search(pattern, content, re.DOTALL)

            if match:
                result[field] = match.group(1).strip()
            else:
                # Fallback: use entire content if only one field expected
                if len(expected_fields) == 1:
                    result[field] = content.strip()
                else:
                    result[field] = ""

        return result

    def _finalize_report(self, botengine, report, start_time):
        """
        Generate PDF from completed report and email to admins.
        :param botengine: BotEngine environment
        :param report: Complete enhanced report dict
        :param start_time: Pipeline start timestamp
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_finalize_report()")

        self._generate_and_email_pdf(botengine, report)

        # Clean up in-progress state
        botengine.save_variable(
            services.STATE_VAR_REPORT_IN_PROGRESS, None, overwrite=True
        )

        duration_ms = botengine.get_timestamp() - start_time
        logger.info(f"|_finalize_report() Report completed in {duration_ms}ms")
        logger.info("<_finalize_report()")

    # ==========================================================================
    # PDF Generation
    # ==========================================================================
    def _generate_and_email_pdf(self, botengine, report):
        """
        Generate a trends organization PDF report and email to admins.
        Uses fpdf2 and matplotlib for charts.

        :param botengine: BotEngine environment
        :param report: Complete report dict with LLM-enhanced text
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_generate_and_email_pdf()")

        try:
            from fpdf import FPDF
            from fpdf.fonts import FontFace
            import base64
            from . import plot_builder

            HEADING_COLOR = (44, 62, 80)
            ACCENT_COLOR = (41, 128, 185)
            ALT_ROW_FILL = 230
            CONCERNING_FILL = (255, 243, 224)  # Light orange
            CRITICAL_FILL = (255, 224, 224)    # Light red

            _UNICODE_TO_LATIN = str.maketrans(
                {
                    "\u2013": "-",
                    "\u2014": "-",
                    "\u2015": "-",
                    "\u2018": "'",
                    "\u2019": "'",
                    "\u201a": "'",
                    "\u201c": '"',
                    "\u201d": '"',
                    "\u201e": '"',
                    "\u2022": "*",
                    "\u2026": "...",
                    "\u00a0": " ",
                    "\u200b": "",
                    "\u2011": "-",
                    "\u2010": "-",
                }
            )

            def sanitize(text):
                if not isinstance(text, str):
                    text = str(text) if text is not None else ""
                text = text.translate(_UNICODE_TO_LATIN)
                return text.encode("latin-1", errors="replace").decode("latin-1")

            class TrendsPDF(FPDF):
                def footer(self):
                    self.set_y(-15)
                    self.set_font("helvetica", "I", 8)
                    self.set_text_color(150)
                    self.cell(
                        0, 10, f"Page {self.page_no()}/{{nb}}",
                        align="C",
                    )

            pdf = TrendsPDF()
            pdf.alias_nb_pages()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_title("Trends Analysis - Organization Report")
            pdf.set_author("CareDaily")
            pdf.add_page()

            def section_heading(title):
                pdf.set_font("helvetica", "B", 13)
                pdf.set_text_color(*HEADING_COLOR)
                pdf.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")
                pdf.set_draw_color(*ACCENT_COLOR)
                pdf.set_line_width(0.5)
                pdf.line(
                    pdf.l_margin, pdf.get_y(),
                    pdf.l_margin + pdf.epw, pdf.get_y(),
                )
                pdf.ln(3)
                pdf.set_text_color(0)
                pdf.set_draw_color(0)
                pdf.set_line_width(0.2)

            headings_style = FontFace(
                emphasis="BOLD",
                color=255,
                fill_color=ACCENT_COLOR,
            )

            section1 = report.get("section1_overview", {})
            section2 = report.get("section2_individuals", {})
            section2_summary = report.get("section2_summary", {})
            section3 = report.get("section3_review", {})
            metadata = report.get("metadata", {})

            # ══════════════════════════════════════════════
            # TITLE PAGE
            # ══════════════════════════════════════════════
            org_name = botengine.get_organization_name()

            pdf.set_font("helvetica", "B", 20)
            pdf.set_text_color(*ACCENT_COLOR)
            pdf.cell(
                0, 14, "Trends Analysis",
                new_x="LMARGIN", new_y="NEXT", align="C",
            )
            pdf.set_text_color(100)
            pdf.set_font("helvetica", "", 11)
            report_date = datetime.datetime.fromtimestamp(
                report.get("timestamp_ms", 0) / 1000
            ).strftime("%B %d, %Y")
            subtitle = f"{org_name} - {report_date}" if org_name else f"Organization Report - {report_date}"
            pdf.cell(
                0, 7, sanitize(subtitle),
                new_x="LMARGIN", new_y="NEXT", align="C",
            )
            pdf.set_text_color(0)
            pdf.ln(6)

            # ══════════════════════════════════════════════
            # SECTION 1: ANALYSIS OVERVIEW
            # ══════════════════════════════════════════════
            overview_text = section1.get("overview_text", "")
            if overview_text:
                section_heading("Analysis Overview")
                pdf.set_font("helvetica", "", 10)
                pdf.multi_cell(0, 5, sanitize(overview_text))
                pdf.ln(5)

            # Population statistics table
            section_heading("Population Statistics")
            pdf.set_font("helvetica", "", 10)
            with pdf.table(
                col_widths=(2, 1),
                borders_layout="SINGLE_TOP_LINE",
                first_row_as_headings=False,
                line_height=6,
                padding=2,
            ) as table:
                row = table.row()
                row.cell("Total Locations Monitored", style=FontFace(emphasis="BOLD"))
                row.cell(str(section1.get("total_locations", 0)))
                row = table.row()
                row.cell("Total Trend Types Tracked", style=FontFace(emphasis="BOLD"))
                row.cell(str(section1.get("total_trend_types", 0)))
                row = table.row()
                row.cell("Notable Outliers", style=FontFace(emphasis="BOLD"))
                row.cell(str(len(section1.get("outliers", []))))
            pdf.ln(5)

            # Category overview chart
            category_stats = section1.get("category_stats", {})
            if category_stats:
                try:
                    buf = plot_builder.generate_category_overview_chart(
                        category_stats, metadata
                    )
                    pdf.image(buf, x=pdf.l_margin, w=pdf.epw)
                    buf.close()
                    pdf.ln(5)
                except Exception as e:
                    logger.warning(f"|_generate_and_email_pdf() Chart error: {e}")

            # Z-score heatmap (paginated)
            if section2:
                try:
                    heatmap_pages = plot_builder.generate_zscore_heatmap(section2, metadata)
                    for buf in heatmap_pages:
                        pdf.image(buf, x=pdf.l_margin, w=pdf.epw)
                        buf.close()
                        pdf.ln(5)
                except Exception as e:
                    logger.warning(f"|_generate_and_email_pdf() Heatmap error: {e}")

            # ══════════════════════════════════════════════
            # SECTION 2: INDIVIDUAL ANALYSIS
            # ══════════════════════════════════════════════
            for loc_idx, (location_id, loc_data) in enumerate(section2.items()):
                pdf.add_page()
                section_heading(f"Location Analysis (#{loc_idx + 1} - {location_id})")

                # Part 1: LLM narrative about outlying trends
                individual_text = loc_data.get("individual_text", "")
                if individual_text:
                    pdf.set_font("helvetica", "", 10)
                    pdf.multi_cell(0, 5, sanitize(individual_text))
                    pdf.ln(5)

                # Part 2: Side-by-side pie chart + wellness timeline
                health_dist = loc_data.get("health_distribution", {})
                wellness_hist = loc_data.get("wellness_history", [])
                if health_dist or wellness_hist:
                    try:
                        buf = plot_builder.generate_individual_overview_charts(
                            health_dist, wellness_hist
                        )
                        pdf.image(buf, x=pdf.l_margin, w=pdf.epw)
                        buf.close()
                        pdf.ln(5)
                    except Exception as e:
                        logger.warning(
                            f"|_generate_and_email_pdf() Individual charts error for location {location_id}: {e}"
                        )

                # Part 3: Trends table with severity highlighting
                current = loc_data.get("current_trends", {})
                if current:
                    pdf.set_font("helvetica", "", 10)
                    with pdf.table(
                        col_widths=(3, 1, 1, 1, 1),
                        headings_style=headings_style,
                        line_height=6,
                        padding=2,
                    ) as table:
                        header = table.row()
                        header.cell("Trend")
                        header.cell("Value")
                        header.cell("Avg")
                        header.cell("Std Dev")
                        header.cell("Z-Score")
                        for trend_id, trend_info in current.items():
                            zscore = trend_info.get("zscore")
                            abs_z = abs(zscore) if zscore is not None else 0
                            if abs_z >= services.ZSCORE_CRITICAL:
                                row_style = FontFace(fill_color=CRITICAL_FILL)
                            elif abs_z >= services.ZSCORE_CONCERNING:
                                row_style = FontFace(fill_color=CONCERNING_FILL)
                            else:
                                row_style = None
                            row = table.row()
                            row.cell(sanitize(trend_info.get("title", trend_id)), style=row_style)
                            row.cell(sanitize(trend_info.get("display", str(trend_info.get("value", "--")))), style=row_style)
                            row.cell(str(trend_info.get("avg", "--")), style=row_style)
                            row.cell(str(trend_info.get("std", "--")), style=row_style)
                            row.cell(str(round(zscore, 2)) if zscore is not None else "--", style=row_style)
                    pdf.ln(5)

            # ══════════════════════════════════════════════
            # SECTION 2B: ADDITIONAL LOCATIONS SUMMARY
            # ══════════════════════════════════════════════
            if section2_summary:
                pdf.add_page()
                section_heading("Additional Locations Summary")
                pdf.set_font("helvetica", "", 9)
                pdf.multi_cell(
                    0, 5,
                    sanitize(
                        f"{len(section2_summary)} additional location(s) "
                        "included below with category-level scores. "
                        "Values represent average |z-score| per category."
                    ),
                )
                pdf.ln(3)

                # Collect all categories across summary locations
                all_cats = set()
                for loc_data in section2_summary.values():
                    all_cats.update(loc_data.get("category_scores", {}).keys())
                sorted_cats = sorted(all_cats)
                cat_labels = [
                    services.TREND_CATEGORY_LABELS.get(c, c) for c in sorted_cats
                ]

                # Fixed columns + one per category
                col_widths = [1.5, 1, 1, 1] + [1] * len(sorted_cats)
                pdf.set_font("helvetica", "", 8)
                with pdf.table(
                    col_widths=col_widths,
                    headings_style=headings_style,
                    cell_fill_color=ALT_ROW_FILL,
                    cell_fill_mode="ROWS",
                    line_height=5,
                    padding=1,
                ) as table:
                    header = table.row()
                    header.cell("Location")
                    header.cell("Trends")
                    header.cell("Critical")
                    header.cell("Concern.")
                    for label in cat_labels:
                        header.cell(label)

                    loc_offset = len(section2)
                    for idx, (location_id, loc_data) in enumerate(
                        section2_summary.items()
                    ):
                        row = table.row()
                        row.cell(f"#{loc_offset + idx + 1} - {location_id}")
                        row.cell(str(loc_data.get("total_trends", 0)))
                        row.cell(str(loc_data.get("critical_count", 0)))
                        row.cell(str(loc_data.get("concerning_count", 0)))
                        scores = loc_data.get("category_scores", {})
                        for cat in sorted_cats:
                            val = scores.get(cat)
                            row.cell(
                                str(round(val, 1)) if val is not None else "--"
                            )
                pdf.ln(5)

            # ══════════════════════════════════════════════
            # SECTION 3: REVIEW
            # ══════════════════════════════════════════════
            pdf.add_page()
            review_text = section3.get("review_text", "")
            if review_text:
                section_heading("Review & Recommendations")
                pdf.set_font("helvetica", "", 10)
                pdf.multi_cell(0, 5, sanitize(review_text))
                pdf.ln(5)

            # Category health chart
            category_health = section3.get("category_health", {})
            if category_health:
                section_heading("Category Health Distribution")
                try:
                    buf = plot_builder.generate_category_health_chart(category_health)
                    pdf.image(buf, x=pdf.l_margin, w=pdf.epw)
                    buf.close()
                    pdf.ln(5)
                except Exception as e:
                    logger.warning(f"|_generate_and_email_pdf() Health chart error: {e}")

            # Cross-location patterns table
            patterns = section3.get("cross_location_patterns", [])
            if patterns:
                section_heading("Cross-Location Patterns")
                pdf.set_font("helvetica", "", 10)
                with pdf.table(
                    col_widths=(3, 2, 1, 1),
                    headings_style=headings_style,
                    cell_fill_color=ALT_ROW_FILL,
                    cell_fill_mode="ROWS",
                    line_height=6,
                    padding=2,
                ) as table:
                    header = table.row()
                    header.cell("Trend")
                    header.cell("Category")
                    header.cell("Affected")
                    header.cell("Avg Z")
                    for p in patterns:
                        row = table.row()
                        row.cell(sanitize(p.get("title", "")))
                        cat_label = services.TREND_CATEGORY_LABELS.get(
                            p.get("category", ""), p.get("category", "")
                        )
                        row.cell(sanitize(cat_label))
                        row.cell(
                            f"{p.get('affected_locations', 0)}/{p.get('total_locations', 0)}"
                        )
                        row.cell(str(p.get("avg_zscore", "--")))
                pdf.ln(5)

            # ── Generate PDF bytes and email ──
            pdf_bytes = pdf.output()
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            attachments = []
            botengine.add_email_attachment(
                destination_attachment_array=attachments,
                filename="Trends_Analysis_Organization_Report.pdf",
                content=pdf_base64,
                content_type="application/pdf",
                content_id="trends_org_pdf",
            )

            botengine.email_admins(
                email_subject=_("Trends Analysis - Organization Report"),  # noqa: F821 # type: ignore
                email_content=_(  # noqa: F821 # type: ignore
                    "Please find attached the trends analysis organization report."
                ),
                email_html=False,
                email_attachments=attachments,
                brand=properties.get_property(
                    botengine, "ORGANIZATION_BRAND", complain_if_missing=False
                ),
                categories=[NOTIFICATION_CATEGORY],
            )
            logger.info("|_generate_and_email_pdf() PDF generated and emailed to admins")

        except ImportError as e:
            logger.warning(
                f"|_generate_and_email_pdf() Missing dependency, skipping PDF generation: {e}"
            )
        except Exception as e:
            import traceback

            logger.error(
                "|_generate_and_email_pdf() Error generating PDF: {} trace={}".format(
                    e, traceback.format_exc()
                )
            )

        logger.info("<_generate_and_email_pdf()")
