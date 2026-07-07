"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Organization Report Aggregator Microservice
"""

import datetime
import json

import pytz
import signals.analytics as analytics  # type: ignore
import signals.llm as llm  # type: ignore
import signals.report as org_report  # type: ignore
import utilities.utilities as utilities  # type: ignore
from intelligence.intelligence import Intelligence  # type: ignore

from . import report_builder, rules_engine, services
from .personas import tech, wellness

DATA_REQUEST_LOCATION_STATES_REFERENCE_DAILY = "ra_location_states_daily"
DATA_REQUEST_LOCATION_STATES_REFERENCE_WEEKLY = "ra_location_states_weekly"

# Data request timeout/retry constants
DATA_REQUEST_TIMEOUT_S = 10  # 10 seconds between retries
MAX_DATA_REQUEST_RETRIES = 6  # Maximum 6 retries (60 seconds total wait)

class OrganizationReportAggregatorMicroservice(Intelligence):
    """
    Organization Report Aggregator Microservice
    ===========================================

    Phase 1: Core Reporting Pipeline
    --------------------------------
    This microservice aggregates intelligence from location-level AI Ambient Assistants,
    synthesizes comprehensive master reports, and delivers persona-specific executive
    reports to organizational administrators.

    Core Responsibilities:
    1. Pull aggregated reports from all child locations on demand
    2. Generate comprehensive daily master reports at 6 AM
    3. Extract persona-specific reports (wellness, tech) from master reports
    4. Deliver HTML-formatted emails to organization administrators
    5. Weekly synthesis (every Sunday) for trend analysis

    Architecture:
    - Pull-based: reads "aggregated_report" state variable from each child location
    - Location bots cache org-bound reports locally via report_to_org datastream
    - Org bot pulls on schedule (no push/cache at org level)
    Bot Variables:
    - org_report_master: Comprehensive daily master reports (overwritten each run)
    - org_report_wellness: Health & Wellness persona reports (overwritten each run)
    - org_report_tech: IT Infrastructure persona reports (overwritten each run)

    Triggers:
    - Schedule: Daily at 6:00 AM - generate master report + personas
    - Schedule: Weekly (Sunday) at 6:00 AM - enhanced weekly synthesis

    Email Delivery:
    - Phase 1: Send to notification categories [1, 2 (tech emails only), 4] (Manager + Technician + Reports) 
    - Phase 2: Filter by user properties for granular opt-out support
    - Note: Can use userCategories array to specify which org user categories to notify
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
        return

    def destroy(self, botengine):
        """
        Destroy the microservice
        :param botengine: BotEngine environment
        """
        return

    def new_version(self, botengine):
        """
        New bot version detected - initialize new class variables if needed
        :param botengine: BotEngine environment
        """
        # No class variables to migrate - all state stored in state variables
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "new_version() Organization Report Aggregator"
        )

    # ===========================================================================
    # Datastream Message Handlers
    # ===========================================================================
    def datastream_updated(self, botengine, address, content):
        """
        Datastream message received
        :param botengine: BotEngine environment
        :param address: Data stream address
        :param content: Data stream content (dict)
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">datastream_updated() address={address}")

        if address == "generate_master_report":
            self._handle_generate_master_report_request(botengine, content)

        elif address == "clear_report_cache":
            self._handle_clear_cache_request(botengine, content)

        logger.info("<datastream_updated()")

    # ===========================================================================
    # Schedule Handlers
    # ===========================================================================
    def schedule_fired(self, botengine, schedule_id):
        """
        Schedule fired - generate reports
        Runs daily at 6 AM. Checks if today is Sunday for weekly synthesis.
        :param botengine: BotEngine environment
        :param schedule_id: Schedule ID
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">schedule_fired() schedule_id={schedule_id}")

        if schedule_id == services.SCHEDULE_DAILY_MASTER_REPORT:
            # Check if today is Sunday (0 = Monday, 6 = Sunday)
            import datetime

            today = datetime.datetime.fromtimestamp(
                botengine.get_timestamp() / 1000, tz=pytz.utc
            )
            is_sunday = today.weekday() == 6

            if is_sunday:
                logger.info(
                    "|schedule_fired() Sunday detected - generating weekly synthesis"
                )
                self._generate_weekly_reports(botengine)
            else:
                logger.info("|schedule_fired() Generating daily reports")
                self._generate_daily_reports(botengine)

        logger.info("<schedule_fired()")

    def timer_fired(self, botengine, argument):
        """
        The bot's intelligence timer fired
        :param botengine: BotEngine environment
        :param argument: Argument applied when setting the timer
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        if not isinstance(argument, dict):
            return

        timer_type = argument.get("type")

        if timer_type == "data_request_timeout":
            report_type = argument.get("report_type")  # "daily" or "weekly"
            retry_count = argument.get("retry_count", 0)

            # Check if reports arrived via async_data_request_ready()
            variable_name = "daily_reports_in_progress" if report_type == "daily" else "all_reports_in_progress"
            stored_reports = botengine.load_variable(variable_name)

            if stored_reports is not None:
                # Reports arrived - process them in this synchronous context
                logger.info(f"|timer_fired() {report_type} reports ready, processing {len(stored_reports)} reports")
                botengine.delete_variable(variable_name)
                self._generate_master_report_llm(botengine, stored_reports, is_weekly=(report_type == "weekly"))
            else:
                # No response yet
                if retry_count >= MAX_DATA_REQUEST_RETRIES:
                    logger.warning(
                        f"|timer_fired() Max retries ({MAX_DATA_REQUEST_RETRIES}) exceeded waiting for {report_type} data request response. Giving up."
                    )
                    return

                logger.warning(
                    f"|timer_fired() Data request timeout ({report_type}), retry {retry_count + 1}/{MAX_DATA_REQUEST_RETRIES}"
                )
                self.start_timer_s(
                    botengine,
                    DATA_REQUEST_TIMEOUT_S,
                    argument={
                        "type": "data_request_timeout",
                        "report_type": report_type,
                        "retry_count": retry_count + 1,
                    },
                    reference=f"data_request_timeout_{report_type}",
                )

    # ==========================================================================
    # Data Request Handlers
    # ==========================================================================

    def async_data_request_ready(self, botengine, reference, content):
        """
        Data request ready
        
        IMPORTANT: This method executes in an asynchronous environment where you are NOT allowed to:
        - Set timers or alarms
        - Manage class variables that persist across executions
        - Perform other stateful operations

        To return to a synchronous environment where you can use timers and manage state, call:
        botengine.async_execute_again_in_n_seconds(seconds)
        
        :param botengine:
        :param reference:
        :param content:
        :return:
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        if reference == DATA_REQUEST_LOCATION_STATES_REFERENCE_DAILY:
            daily_reports = []
            for location_id in content:
                timestamps = list(content[location_id][services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS].keys())
                logger.info(f"|async_data_request_ready() Location {location_id} returned timestamps: {timestamps}")
                daily_reports.extend(content[location_id][services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS].values())

            if not daily_reports:
                logger.warning(
                    "|_generate_daily_reports() No reports found across locations. Skipping report generation."
                )
                logger.info("<_generate_daily_reports()")
                return

            logger.info(
                f"|_generate_daily_reports() Processing {len(daily_reports)} reports from past 24 hours"
            )

            # Store reports for synchronous processing via timer_fired()
            # (async context cannot set timers or send datastreams)
            botengine.save_variable("daily_reports_in_progress", daily_reports, overwrite=True)

        if reference == DATA_REQUEST_LOCATION_STATES_REFERENCE_WEEKLY:
            all_reports = []
            for location_id in content:
                timestamps = list(content[location_id][services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS].keys())
                logger.info(f"|async_data_request_ready() Location {location_id} returned timestamps: {timestamps}")
                all_reports.extend(content[location_id][services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS].values())

            if not all_reports:
                logger.warning(
                    "|_generate_weekly_reports() No reports found across locations. Skipping weekly report generation."
                )
                logger.info("<_generate_weekly_reports()")
                return

            logger.info(
                f"|_generate_weekly_reports() Processing {len(all_reports)} reports from all locations"
            )

            # Store reports for synchronous processing via timer_fired()
            # (async context cannot set timers or send datastreams)
            botengine.save_variable("all_reports_in_progress", all_reports, overwrite=True)

    # ===========================================================================
    # LLM Response Handler
    # ===========================================================================
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

        # Call parent class to clean up arguments
        Intelligence.llm_response(self, botengine, response, reference, argument)

        if reference == services.LLM_REFERENCE_MASTER_REPORT:
            self._handle_master_report_llm_response(botengine, response, argument)

        logger.info("<llm_response()")

    # ===========================================================================
    # Report Collection from Locations
    # ===========================================================================
    def _pull_reports_from_location(self, botengine, location_id):
        """
        Pull aggregated report data from a child location's state variable.

        Uses direct HTTP GET to read the "aggregated_report" state variable
        from a specific location. The org bot has admin privileges that allow
        cross-location access.

        :param botengine: BotEngine environment
        :param location_id: Child location ID to read from
        :return: List of report dicts, or empty list on failure
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        try:
            r = botengine._http_get(
                "/cloud/json/locations/{}/state".format(location_id),
                params={"name": services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS}
            )

            if r is None:
                return []

            j = json.loads(r.text)

            if "value" in j:
                value = j["value"]
                if isinstance(value, list):
                    return value
                elif isinstance(value, dict):
                    return [value]

            return []

        except Exception as e:
            logger.warning(
                f"|_pull_reports_from_location() Error reading state from "
                f"location {location_id}: {e}"
            )
            return []

    def _pull_all_location_reports(self, botengine, cutoff_ms=None):
        """
        Pull aggregated reports from all child locations in the organization.

        :param botengine: BotEngine environment
        :param cutoff_ms: Optional timestamp cutoff to filter reports (only include reports newer than this)
        :return: List of report dicts from all locations
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        try:
            locations = botengine.get_organization_locations(self.parent.organization_id)
        except Exception as e:
            logger.error(f"|_pull_all_location_reports() Failed to get org locations: {e}")
            return []

        if not locations:
            logger.warning("|_pull_all_location_reports() No locations found in organization")
            return []

        logger.info(f"|_pull_all_location_reports() Found {len(locations)} locations")

        all_reports = []
        for location_info in locations:
            location_id = location_info.get("id")
            if location_id is None:
                continue

            try:
                reports = self._pull_reports_from_location(botengine, location_id)
                if reports:
                    if cutoff_ms is not None:
                        reports = [
                            r for r in reports
                            if r.get("timestamp_ms", 0) >= cutoff_ms
                        ]
                    all_reports.extend(reports)
                    logger.info(
                        f"|_pull_all_location_reports() Location {location_id}: "
                        f"{len(reports)} reports"
                    )
            except Exception as e:
                logger.warning(
                    f"|_pull_all_location_reports() Error pulling from location {location_id}: {e}"
                )
                continue

        logger.info(f"|_pull_all_location_reports() Total reports collected: {len(all_reports)}")
        return all_reports

    def _handle_generate_master_report_request(self, botengine, content):
        """
        Handle request to generate master report (from CLI tool or other trigger)
        :param botengine: BotEngine environment
        :param content: Request content dict
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_handle_generate_master_report_request()")

        include_weekly = content.get("include_weekly_synthesis", False)

        if include_weekly:
            self._generate_weekly_reports(botengine)
        else:
            self._generate_daily_reports(botengine)

        logger.info("<_handle_generate_master_report_request()")

    def _handle_clear_cache_request(self, botengine, content):
        """
        Handle request to clear report cache (from CLI tool)
        :param botengine: BotEngine environment
        :param content: Request content dict
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_handle_clear_cache_request()")

        # Clean up legacy cache variable if it exists
        botengine.save_variable(services.COLLECTION_ORG_REPORT_CACHE, [], overwrite=True)

        # Clear in-progress state variables
        botengine.delete_variable("master_report_in_progress")
        botengine.delete_variable("daily_reports_in_progress")
        botengine.delete_variable("all_reports_in_progress")

        logger.info(
            "|_handle_clear_cache_request() Legacy cache cleared (reports now pulled from locations)"
        )

        # Log the clear event
        analytics.track(
            botengine,
            self.parent,
            "org_report_cache_cleared",
            properties={
                "trigger_source": content.get("trigger_source", "unknown"),
                "timestamp_ms": content.get("timestamp_ms", botengine.get_timestamp()),
            },
        )

        logger.info("<_handle_clear_cache_request()")

    # ===========================================================================
    # Master Report Generation
    # ===========================================================================
    def _generate_daily_reports(self, botengine):
        """
        Generate daily master report by pulling data from all child locations.
        :param botengine: BotEngine environment
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_generate_daily_reports()")

        # Pull reports from all locations, filtered to past 24 hours
        cutoff_ms = botengine.get_timestamp() - utilities.ONE_DAY_MS

        logger.info("|_generate_daily_reports() Requesting location states to trigger report generation")
        botengine.request_data(
            type=botengine.DATA_REQUEST_TYPE_LOCATION_TIME_STATES,
            reference=DATA_REQUEST_LOCATION_STATES_REFERENCE_DAILY,
            oldest_timestamp_ms=cutoff_ms,
            newest_timestamp_ms=botengine.get_timestamp(),
            names=[services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS],
        )

        # Set timeout timer to wait for async data request response
        self.start_timer_s(
            botengine,
            DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": "data_request_timeout",
                "report_type": "daily",
                "retry_count": 0,
            },
            reference="data_request_timeout_daily",
        )
        logger.info("<_generate_daily_reports()")

    def _generate_weekly_reports(self, botengine):
        """
        Generate weekly master report by pulling data from all child locations.
        :param botengine: BotEngine environment
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_generate_weekly_reports()")


        # Pull reports from all locations, filtered to past 7 days
        cutoff_ms = botengine.get_timestamp() - utilities.ONE_DAY_MS * 7

        logger.info("|_generate_weekly_reports() Requesting location states to trigger report generation")
        botengine.request_data(
            type=botengine.DATA_REQUEST_TYPE_LOCATION_TIME_STATES,
            reference=DATA_REQUEST_LOCATION_STATES_REFERENCE_WEEKLY,
            oldest_timestamp_ms=cutoff_ms,
            newest_timestamp_ms=botengine.get_timestamp(),
            names=[services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS],
        )

        # Set timeout timer to wait for async data request response
        self.start_timer_s(
            botengine,
            DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": "data_request_timeout",
                "report_type": "weekly",
                "retry_count": 0,
            },
            reference="data_request_timeout_weekly",
        )
        logger.info("<_generate_weekly_reports()")

    def _generate_master_report_llm(self, botengine, reports, is_weekly=False):
        """
        Generate master report using DETERMINISTIC STRUCTURE + LLM text enhancement

        STAGE 1: Rules-Based Pre-Processing
        - Filter out info-priority reports
        - Include resolutions for celebrations section
        - Deduplicate by location+type
        - Calculate severity_rank
        - Sort by severity + days_active
        - Categorize by wellness/it/safety/energy
        - Limit to top 20 per category

        STAGE 2: Deterministic Report Building
        - Build complete report structure with ALL data
        - NO LLM involved - pure data organization
        - Sections: Executive Summary, Top Concerns, Top Celebrations, Trends, Category Deep Dives

        STAGE 3: LLM Text Enhancement (section-by-section)
        - LLM enhances TEXT ONLY, not structure
        - Output is plain text, not JSON
        - Inject enhanced text into pre-built structure

        :param botengine: BotEngine environment
        :param reports: List of reports to synthesize
        :param is_weekly: True if this is a weekly synthesis
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(
            f">_generate_master_report_llm() is_weekly={is_weekly} report_count={len(reports)}"
        )
        start_time = botengine.get_timestamp()

        # STAGE 1: Rules-Based Pre-Processing
        logger.info("|_generate_master_report_llm() STAGE 1: Rules-based preprocessing")
        processed = rules_engine.process_reports_for_llm(
            reports,
            include_resolved=True,  # Include resolutions for celebrations
            include_info=False,  # Exclude info-priority (focus on problems)
            max_per_category=20,  # Top 20 per category
        )

        stats = processed["stats"]
        logger.info(
            f"|_generate_master_report_llm() Preprocessed: {stats['total_raw']} raw → {stats['total_deduplicated']} deduplicated"
        )
        logger.info(
            f"|_generate_master_report_llm() Categories: {stats['category_counts']}"
        )

        # STAGE 2: Deterministic Report Building
        logger.info(
            "|_generate_master_report_llm() STAGE 2: Building deterministic report structure"
        )

        org_name = getattr(self.parent, "organization_descriptive_name", None) or getattr(self.parent, "organization_domain_name", None) or str(self.parent.organization_id)
        report_type = "weekly" if is_weekly else "daily"
        timestamp_ms = utilities.get_midnight_timestamp_ms(botengine.get_timestamp())

        # Build complete report WITHOUT LLM
        master_report = report_builder.build_master_report(
            processed_data=processed,
            timestamp_ms=timestamp_ms,
            report_type=report_type,
            org_name=org_name,
        )

        logger.info(
            f"|_generate_master_report_llm() Report built with {len(master_report['sections'])} sections"
        )

        # STAGE 3: LLM Text Enhancement (section-by-section)
        logger.info(
            "|_generate_master_report_llm() STAGE 3: Starting LLM text enhancement"
        )

        # Get all tasks that need LLM enhancement
        enhancement_tasks = report_builder.get_llm_enhancement_tasks(master_report)
        logger.info(
            f"|_generate_master_report_llm() {len(enhancement_tasks)} text enhancement tasks queued"
        )

        # Save report skeleton to variable for async processing
        botengine.save_variable(
            "master_report_in_progress",
            {
                "report": master_report,
                "tasks_remaining": len(enhancement_tasks),
                "tasks_completed": 0,
                "start_time": start_time,
            },
            overwrite=True,
        )

        # Start processing first enhancement task
        if enhancement_tasks:
            self._process_next_enhancement_task(botengine, enhancement_tasks[0])
        else:
            # No enhancement needed, save directly
            logger.info(
                "|_generate_master_report_llm() No enhancement tasks, saving report directly"
            )
            self._finalize_master_report(botengine, master_report, start_time)

        logger.info("<_generate_master_report_llm()")

    def _handle_master_report_llm_response(self, botengine, response, argument):
        """
        Handle LLM response for text enhancement tasks
        This is called for EACH enhancement task (not the full report)

        :param botengine: BotEngine environment
        :param response: LLM response dict
        :param argument: Original argument with task info
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_handle_master_report_llm_response()")

        # Load report in progress
        state = botengine.load_variable("master_report_in_progress")
        if not state:
            logger.error(
                "|_handle_master_report_llm_response() No report in progress found"
            )
            logger.info("<_handle_master_report_llm_response()")
            return

        master_report = state["report"]
        task_id = argument.get("task_id")
        fields_to_fill = argument.get("fields_to_fill", [])

        logger.info(f"|_handle_master_report_llm_response() Processing task: {task_id}")

        try:
            # Extract text from LLM response
            # Supports both Responses API and Chat Completions API formats
            content = self._extract_llm_response_text(response)
            if content is None:
                content = ""
                logger.warning(
                    f"|_handle_master_report_llm_response() Could not extract LLM response text. response keys={list(response.keys()) if isinstance(response, dict) else 'N/A'}"
                )

            # Parse the response to extract field values
            # Expecting format like: "summary_text: <text>\ntop_concern_text: <text>"
            enhanced_text_dict = self._parse_llm_text_response(content, fields_to_fill)

            # Apply enhancement to report
            master_report = report_builder.apply_llm_enhancement(
                master_report, task_id, enhanced_text_dict
            )

            # Update progress
            state["report"] = master_report
            state["tasks_completed"] += 1
            tasks_remaining = state["tasks_remaining"] - 1
            state["tasks_remaining"] = tasks_remaining

            logger.info(
                f"|_handle_master_report_llm_response() Task completed. {tasks_remaining} tasks remaining"
            )

            # Save updated variable
            botengine.save_variable("master_report_in_progress", state, overwrite=True)

            # Check if all tasks complete
            if tasks_remaining == 0:
                logger.info(
                    "|_handle_master_report_llm_response() All enhancement tasks complete, finalizing report"
                )
                self._finalize_master_report(
                    botengine, master_report, state["start_time"]
                )
            else:
                # Get next task
                all_tasks = report_builder.get_llm_enhancement_tasks(master_report)
                next_task_index = state["tasks_completed"]
                if next_task_index < len(all_tasks):
                    self._process_next_enhancement_task(
                        botengine, all_tasks[next_task_index]
                    )

        except Exception as e:
            logger.error(
                f"|_handle_master_report_llm_response() Error processing enhancement: {e}"
            )
            import traceback

            logger.error(traceback.format_exc())

        logger.info("<_handle_master_report_llm_response()")

    def _process_next_enhancement_task(self, botengine, task):
        """
        Process next LLM text enhancement task

        :param botengine: BotEngine environment
        :param task: Task dict from report_builder.get_llm_enhancement_tasks()
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">_process_next_enhancement_task() task_id={task['task_id']}")

        # Build prompt based on task type
        prompt = self._build_enhancement_prompt(task)

        kwargs = {
            "messages": [{"role": "user", "content": prompt}],
            "model": "gpt-4o-mini",  # Use mini for text enhancement (cheaper, faster)
            "temperature": 0.3,
        }
        # Send to LLM for text enhancement
        llm.chat(
            botengine,
            self.parent,
            self.intelligence_id,
            reference=services.LLM_REFERENCE_MASTER_REPORT,
            argument={
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "fields_to_fill": task["fields_to_fill"],
            },
            provider_api=llm.PROVIDER_API_OPENAI_CHAT_COMPLETION,
            **kwargs,
        )

        logger.info("<_process_next_enhancement_task()")

    def _extract_llm_response_text(self, response):
        """
        Extract text from LLM response.

        Supports both OpenAI Responses API and Chat Completion API formats:
        - Responses API: output[].content[].text (type="output_text")
        - Responses API: output_text convenience property
        - Chat Completion: choices[].message.content

        :param response: LLM response dict
        :return: Response text string or None
        """
        try:
            if not isinstance(response, dict):
                return None

            # Responses API: output array with message objects
            output = response.get("output")
            if output and isinstance(output, list):
                for item in output:
                    if item.get("type") == "message":
                        for block in item.get("content", []):
                            if block.get("type") == "output_text":
                                return block.get("text")

            # Responses API: output_text convenience property
            output_text = response.get("output_text")
            if output_text:
                return output_text

            # Chat Completion API fallback: choices array
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content")
                if content is not None:
                    return content.strip()

            return None
        except Exception:
            return None

    def _build_enhancement_prompt(self, task):
        """
        Build LLM prompt for text enhancement task

        :param task: Task dict
        :return: Prompt string
        """
        task_type = task["task_type"]
        data = task["data"]
        max_words = task.get("max_words", 50)

        if task_type == "summary":
            # Executive summary enhancement
            return f"""Write a concise executive summary (max {max_words} words) for an organizational report.

**DATA**:
- Total locations: {data["total_locations"]}
- Critical concerns: {data["critical_count"]}
- Warning concerns: {data["warning_count"]}
- Top 3 concerns: {json.dumps(data["top_concerns"], indent=2)}

**OUTPUT FORMAT**:
summary_text: <2-3 sentences summarizing the overall situation>
top_concern_text: <1 sentence describing the single most critical concern>

**RULES**:
- Be specific and actionable
- Use data provided (don't invent)
- Professional tone
- Max {max_words} words total"""

        elif task_type == "enhance_concern":
            # Enhance individual concern description
            return f"""Enhance this concern description to be more readable and actionable (max {max_words} words).

**RAW DATA**:
- Location: {data.get("location_name")}
- Report Type: {data.get("report_type")}
- Priority: {data.get("priority")}
- Days Active: {data.get("days_active")}
- Description: {data.get("short_description", "")}
- Long Description: {data.get("long_description", "")}
- Recommended Actions: {json.dumps(data.get("recommended_actions", []))}

**OUTPUT FORMAT**:
enhanced_description: <Clear, concise description of the concern>
context_explanation: <Why this matters clinically/technically>

**RULES**:
- Professional healthcare/technical tone
- Explain WHY this matters
- Be specific
- Max {max_words} words total"""

        elif task_type == "enhance_celebration":
            # Enhance celebration/resolution description
            return f"""Enhance this positive outcome description (max {max_words} words).

**RAW DATA**:
- Location: {data.get("location_name")}
- Report Type: {data.get("report_type")}
- Sentiment: {data.get("sentiment")}
- Days to Resolve: {data.get("days_to_resolve")}
- Description: {data.get("short_description", "")}

**OUTPUT FORMAT**:
enhanced_description: <Positive, encouraging description of the resolution>

**RULES**:
- Celebrate the win
- Be specific about what improved
- Professional tone
- Max {max_words} words"""

        elif task_type == "enhance_trend":
            # Enhance trend description
            return f"""Describe this trend pattern concisely (max {max_words} words).

**RAW DATA**:
- Report Type: {data.get("report_type")}
- Locations Affected: {data.get("locations_affected")}
- Total Occurrences: {data.get("total_occurrences")}
- Critical Count: {data.get("critical_count")}
- Average Days Active: {data.get("average_days_active")}

**OUTPUT FORMAT**:
trend_description: <Clear description of the trend and its significance>

**RULES**:
- Explain what the trend means
- Include specific numbers
- Professional tone
- Max {max_words} words"""

        elif task_type == "category_summary":
            # Category deep dive summary
            return f"""Write a summary for this category section (max {max_words} words).

**RAW DATA**:
- Category: {data.get("category")}
- Total Reports: {data.get("total_reports")}
- Critical: {data.get("critical_count")}
- Warning: {data.get("warning_count")}
- Unique Locations: {data.get("unique_locations")}
- Average Days Active: {data.get("average_days_active")}
- Top Locations: {json.dumps(data.get("top_locations", [])[:3], indent=2)}

**OUTPUT FORMAT**:
summary_text: <Overview of this category's status and key takeaways>

**RULES**:
- Synthesize the key points
- Use specific numbers
- Professional tone
- Max {max_words} words"""

        return ""

    def _parse_llm_text_response(self, content, expected_fields):
        """
        Parse LLM text response into field dict
        Expected format: "field_name: value\nfield_name2: value2"

        :param content: LLM response text
        :param expected_fields: List of field names to extract
        :return: Dict of {field_name: text}
        """
        result = {}

        for field in expected_fields:
            # Look for pattern "field_name: <text>"
            import re

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

    def _finalize_master_report(self, botengine, master_report, start_time):
        """
        Finalize and save completed master report

        :param botengine: BotEngine environment
        :param master_report: Complete enhanced report
        :param start_time: Start time for duration calculation
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_finalize_master_report()")

        # Calculate processing duration
        processing_duration_ms = botengine.get_timestamp() - start_time

        # Add metadata
        master_report["processing_metadata"] = {
            "generation_timestamp_ms": botengine.get_timestamp(),
            "processing_duration_ms": processing_duration_ms,
            "enhancement_completed": True,
        }

        # Save master report
        botengine.save_variable(
            services.COLLECTION_ORG_REPORT_MASTER, master_report, overwrite=True
        )

        logger.info(
            "|_finalize_master_report() Master report saved"
        )
        logger.info(
            f"|_finalize_master_report() Processing took {processing_duration_ms}ms"
        )

        # Clean up in-progress variable
        botengine.delete_variable("master_report_in_progress")

        # Now extract persona reports
        self._extract_wellness_report_from_master(
            botengine, master_report, botengine.get_timestamp()
        )
        self._extract_tech_report_from_master(botengine, master_report, botengine.get_timestamp())

        logger.info("<_finalize_master_report()")

    # ===========================================================================
    # Persona Extraction
    # ===========================================================================
    def _extract_wellness_report_from_master(
        self, botengine, master_report, timestamp_ms
    ):
        """
        Extract Health & Wellness persona report from deterministic master report
        Filter to wellness-relevant sections only

        :param botengine: BotEngine environment
        :param master_report: Master report dict (from report_builder)
        :param timestamp_ms: Report timestamp
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_extract_wellness_report_from_master()")

        # Extract wellness-specific data from master report
        sections = master_report["sections"]

        # Concerns already filtered to the wellness category by the report builder
        wellness_concerns = sections["top_concerns"].get(
            org_report.CATEGORY_WELLNESS, {"items": []}
        )["items"]

        wellness_report = {
            "timestamp_ms": timestamp_ms,
            "report_type": master_report["report_type"],
            "org_name": master_report["org_name"],
            "persona": "wellness",
            "schema_version": "2.0",
            # Filter executive summary to wellness concerns
            "executive_summary": self._filter_executive_summary_for_persona(
                sections["executive_summary"], "wellness", wellness_concerns
            ),
            # Only wellness category concerns
            "top_concerns": wellness_concerns,
            # Only wellness celebrations
            "top_celebrations": [
                c
                for c in sections["top_celebrations"]["items"]
                if c.get("category") == org_report.CATEGORY_WELLNESS
            ],
            # Only wellness trends
            "trends": sections["trends"].get(
                org_report.CATEGORY_WELLNESS, {"items": []}
            )["items"],
            # Wellness deep dive
            "category_summary": sections["category_deep_dives"].get(
                org_report.CATEGORY_WELLNESS, {}
            ),
        }

        # Save wellness report
        botengine.save_variable(
            services.COLLECTION_ORG_REPORT_WELLNESS, wellness_report, overwrite=True
        )

        logger.info(
            "|_extract_wellness_report_from_master() Wellness report saved"
        )

        # Email wellness report
        self._email_wellness_report(botengine, wellness_report, timestamp_ms)

        logger.info("<_extract_wellness_report_from_master()")

    def _extract_tech_report_from_master(self, botengine, master_report, timestamp_ms):
        """
        Extract IT Infrastructure persona report from deterministic master report
        Filter to tech-relevant sections only

        :param botengine: BotEngine environment
        :param master_report: Master report dict (from report_builder)
        :param timestamp_ms: Report timestamp
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_extract_tech_report_from_master()")

        # Extract tech-specific data from master report
        sections = master_report["sections"]

        # Concerns already filtered to the IT category by the report builder
        tech_concerns = sections["top_concerns"].get(
            org_report.CATEGORY_IT, {"items": []}
        )["items"]

        tech_report = {
            "timestamp_ms": timestamp_ms,
            "report_type": master_report["report_type"],
            "org_name": master_report["org_name"],
            "persona": "tech",
            "schema_version": "2.0",
            # Filter executive summary to tech concerns
            "executive_summary": self._filter_executive_summary_for_persona(
                sections["executive_summary"], "tech", tech_concerns
            ),
            # Only IT category concerns
            "top_concerns": tech_concerns,
            # Only IT celebrations
            "top_celebrations": [
                c
                for c in sections["top_celebrations"]["items"]
                if c.get("category") == org_report.CATEGORY_IT
            ],
            # Only IT trends
            "trends": sections["trends"].get(org_report.CATEGORY_IT, {"items": []})[
                "items"
            ],
            # IT deep dive
            "category_summary": sections["category_deep_dives"].get(
                org_report.CATEGORY_IT, {}
            ),
        }

        # Save tech report
        botengine.save_variable(
            services.COLLECTION_ORG_REPORT_TECH, tech_report, overwrite=True
        )

        logger.info(
            "|_extract_tech_report_from_master() Tech report saved"
        )

        # Email tech report
        self._email_tech_report(botengine, tech_report, timestamp_ms)

        logger.info("<_extract_tech_report_from_master()")

    def _filter_executive_summary_for_persona(self, exec_summary, persona, persona_concerns):
        """
        Build a persona-specific executive summary.

        Counts and summary text are derived from THIS persona's own category
        concerns (passed in via persona_concerns), not from the org-wide master
        summary. The master summary_text/top_concern_text describe the single
        highest-severity category across the whole organization (typically
        wellness); reusing it here would leak unrelated concerns into this
        report and contradict the persona-filtered counts.

        :param exec_summary: Master executive summary dict (for org-wide totals)
        :param persona: "wellness" or "tech"
        :param persona_concerns: List of concern items already filtered to this
            persona's category (from sections["top_concerns"][category]["items"])
        :return: Filtered executive summary dict
        """
        category_label = "wellness" if persona == "wellness" else "infrastructure"
        total_locations = exec_summary["total_locations"]

        persona_critical = sum(
            1
            for c in persona_concerns
            if c.get("priority") == org_report.PRIORITY_CRITICAL
        )
        persona_warning = sum(
            1
            for c in persona_concerns
            if c.get("priority") == org_report.PRIORITY_WARNING
        )

        # Deterministic, persona-scoped summary text (no cross-persona leak).
        if not persona_concerns:
            summary_text = (
                f"No {category_label} concerns were detected across "
                f"{total_locations} locations."
            )
            top_concern_text = None
        else:
            unique_locations = len(
                {c.get("location_id") for c in persona_concerns}
            )
            summary_text = (
                f"{persona_critical} critical and {persona_warning} warning "
                f"{category_label} concern(s) identified across "
                f"{unique_locations} location(s)."
            )
            top = persona_concerns[0]
            top_desc = (
                top.get("enhanced_description")
                or top.get("short_description")
                or top.get("long_description")
                or ""
            )
            top_concern_text = (
                f"{top.get('location_name', 'Unknown')}: {top_desc}"
                if top_desc
                else None
            )

        return {
            "total_locations": total_locations,
            "persona_critical_count": persona_critical,
            "persona_warning_count": persona_warning,
            "top_concerns_list": persona_concerns[:3],
            "summary_text": summary_text,
            "top_concern_text": top_concern_text,
        }

    # ===========================================================================
    # Email Delivery
    # ===========================================================================
    def _location_link_html(self, botengine, location_id, location_name):
        """
        Render a location name as a bold command center link when a location ID is
        available, otherwise fall back to bold plain text.

        :param botengine: BotEngine environment
        :param location_id: Location ID to link to (may be None)
        :param location_name: Display name for the location
        :return: HTML string for the location name
        """
        if location_id:
            url = utilities.get_admin_url_for_location(botengine, location_id)
            if url:
                return f'<b><a href="{url}">{location_name}</a></b>'
        return f"<b>{location_name}</b>"

    def _email_wellness_report(self, botengine, wellness_report, timestamp_ms):
        """
        Email wellness report to administrators using server-side template
        Convert deterministic report data to HTML sections for email

        :param botengine: BotEngine environment
        :param wellness_report: Wellness report dict (from report_builder filtered for wellness)
        :param timestamp_ms: Report timestamp
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_email_wellness_report()")

        # Build contentArray for email template from structured data
        content_array = []

        # Section 1: Executive Summary
        exec_summary = wellness_report.get("executive_summary", {})
        summary_html = []
        summary_html.append(
            f"<b>Total Locations:</b> {exec_summary.get('total_locations', 0)}"
        )
        summary_html.append(
            f"<b>Critical:</b> {exec_summary.get('persona_critical_count', 0)} | <b>Warning:</b> {exec_summary.get('persona_warning_count', 0)}"
        )
        if exec_summary.get("summary_text"):
            summary_html.append(f"<br>{exec_summary.get('summary_text')}")
        if exec_summary.get("top_concern_text"):
            summary_html.append(
                f"<br><b>Top Concern:</b> {exec_summary.get('top_concern_text')}"
            )

        content_array.append(
            {
                "title": "Executive Summary",
                "icon": "info-circle",
                "color": "694fee",
                "content": ["<br>".join(summary_html)],
            }
        )

        # Section 2: Top Concerns
        top_concerns = wellness_report.get("top_concerns", [])
        if top_concerns:
            priority_html = []
            for concern in top_concerns[:10]:  # Top 10
                location_html = self._location_link_html(
                    botengine,
                    concern.get("location_id"),
                    concern.get("location_name", "Unknown"),
                )

                # Use enhanced description if available, otherwise short_description
                description = concern.get("enhanced_description") or concern.get(
                    "short_description", ""
                )

                # Context explanation (from LLM enhancement)
                context_html = (
                    f"<i>{concern.get('context_explanation', '')}</i>"
                    if concern.get("context_explanation")
                    else ""
                )

                # Recommended actions
                actions = concern.get("recommended_actions", [])
                actions_html = (
                    "<br>• ".join([f"<b>Action:</b> {a}" for a in actions])
                    if actions
                    else ""
                )

                days_html = f"<b>Days Active:</b> {concern.get('days_active') or 1}"
                priority_html_str = f"<span style='color: {'#D0021B' if concern.get('priority') == org_report.PRIORITY_CRITICAL else '#F5A623'}'><b>{concern.get('priority', 'warning').upper()}</b></span>"

                item = f"{location_html} {priority_html_str}<br>{description}"
                if context_html:
                    item += f"<br>{context_html}"
                if actions_html:
                    item += f"<br>{actions_html}"
                item += f"<br>{days_html}"

                priority_html.append(item)

            content_array.append(
                {
                    "title": f"Top Wellness Concerns ({len(top_concerns)} locations)",
                    "icon": "heartbeat",
                    "color": "e74c3c",
                    "content": priority_html,
                }
            )

        # Section 3: Top Celebrations
        celebrations = wellness_report.get("top_celebrations", [])
        if celebrations:
            celebration_html = []
            for cel in celebrations[:10]:  # Top 10
                location_html = self._location_link_html(
                    botengine,
                    cel.get("location_id"),
                    cel.get("location_name", "Unknown"),
                )
                description = cel.get("enhanced_description") or cel.get(
                    "short_description", ""
                )
                days_html = f"<i>(resolved in {cel.get('days_to_resolve', 0)} days)</i>"

                item = f"✓ {location_html}: {description} {days_html}"
                celebration_html.append(item)

            content_array.append(
                {
                    "title": f"Resolutions & Wins ({len(celebrations)} locations)",
                    "icon": "check-circle",
                    "color": "27ae60",
                    "content": celebration_html,
                }
            )

        # Section 4: Trends
        trends = wellness_report.get("trends", [])
        if trends:
            trend_html = []
            for trend in trends:
                # Use enhanced trend description if available
                description = (
                    trend.get("trend_description")
                    or f"{trend.get('report_type', 'Issue')} affecting multiple locations"
                )
                locations_count = trend.get("locations_affected", 0)

                item = f"→ <b>{description}</b> ({locations_count} locations)"
                trend_html.append(item)

            content_array.append(
                {
                    "title": "Wellness Trends & Patterns",
                    "icon": "chart-line",
                    "color": "3498db",
                    "content": trend_html,
                }
            )

        # Section 5: Category Summary
        category_summary = wellness_report.get("category_summary", {})
        if category_summary:
            summary_html = []
            if category_summary.get("summary_text"):
                summary_html.append(category_summary.get("summary_text"))
            else:
                # Fallback summary
                summary_html.append(
                    f"<b>{category_summary.get('total_reports', 0)} wellness reports</b> from <b>{category_summary.get('unique_locations', 0)} locations</b>"
                )
                summary_html.append(
                    f"Critical: {category_summary.get('critical_count', 0)}, Warning: {category_summary.get('warning_count', 0)}"
                )
                summary_html.append(
                    f"Average duration: {category_summary.get('average_days_active', 0)} days"
                )

            content_array.append(
                {
                    "title": "Wellness Category Overview",
                    "icon": "clipboard-list",
                    "color": "9b59b6",
                    "content": summary_html,
                }
            )

        if len(content_array) == 0:
            logger.warning("|_email_wellness_report() No content to send")
            logger.info("<_email_wellness_report()")
            return

        # Format report date

        report_date = datetime.datetime.fromtimestamp(
            timestamp_ms / 1000, tz=pytz.utc
        ).strftime("%B %d, %Y")
        report_type = wellness_report.get("report_type", "daily").capitalize()

        # Send email using server-side template
        logger.info(
            "|_email_wellness_report() Sending email to admins (categories [1, 2])"
        )
        org_name = wellness_report.get("org_name", "")
        org_prefix = f"{org_name} - " if org_name else ""
        botengine.email_admins(
            email_subject=f"🏥 {org_prefix}{wellness.REPORT_TITLE} - {report_type} Report - {report_date}",
            email_html=True,
            email_template_filename=wellness.EMAIL_TEMPLATE_FILENAME,
            email_template_model={
                "title": wellness.REPORT_TITLE,
                "subtitle": f"{report_type} Report - {report_date}",
                "icon": wellness.REPORT_ICON,
                "contentArray": content_array,
                "metadata": {
                    "org_name": wellness_report.get("org_name", ""),
                    "report_type": report_type,
                    "timestamp_ms": timestamp_ms,
                },
            },
            categories=[
                utilities.ORGANIZATION_USER_NOTIFICATION_CATEGORY_MANAGER, 
                utilities.ORGANIZATION_USER_NOTIFICATION_CATEGORY_REPORTS
            ],  # Phase 1: Manager + Reports
        )

        logger.info("|_email_wellness_report() Email sent successfully")
        logger.info("<_email_wellness_report()")

    def _email_tech_report(self, botengine, tech_report, timestamp_ms):
        """
        Email tech report to administrators using server-side template
        Convert deterministic report data to HTML sections for email

        :param botengine: BotEngine environment
        :param tech_report: Tech report dict (from report_builder filtered for tech)
        :param timestamp_ms: Report timestamp
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_email_tech_report()")

        # Build contentArray for email template from structured data
        content_array = []

        # Section 1: Executive Summary
        exec_summary = tech_report.get("executive_summary", {})
        summary_html = []
        summary_html.append(
            f"<b>Total Locations:</b> {exec_summary.get('total_locations', 0)}"
        )
        summary_html.append(
            f"<b>Critical:</b> {exec_summary.get('persona_critical_count', 0)} | <b>Warning:</b> {exec_summary.get('persona_warning_count', 0)}"
        )
        if exec_summary.get("summary_text"):
            summary_html.append(f"<br>{exec_summary.get('summary_text')}")
        if exec_summary.get("top_concern_text"):
            summary_html.append(
                f"<br><b>Top Issue:</b> {exec_summary.get('top_concern_text')}"
            )

        content_array.append(
            {
                "title": "Executive Summary",
                "icon": "info-circle",
                "color": "2C3E50",
                "content": ["<br>".join(summary_html)],
            }
        )

        # Section 2: Top Infrastructure Issues
        top_concerns = tech_report.get("top_concerns", [])
        if top_concerns:
            priority_html = []
            for concern in top_concerns[:10]:  # Top 10
                location_html = self._location_link_html(
                    botengine,
                    concern.get("location_id"),
                    concern.get("location_name", "Unknown"),
                )

                # Use enhanced description if available, otherwise short_description
                description = concern.get("enhanced_description") or concern.get(
                    "short_description", ""
                )

                # Context explanation (from LLM enhancement)
                context_html = (
                    f"<i>{concern.get('context_explanation', '')}</i>"
                    if concern.get("context_explanation")
                    else ""
                )

                # Recommended actions
                actions = concern.get("recommended_actions", [])
                actions_html = (
                    "<br>• ".join([f"<b>Action:</b> {a}" for a in actions])
                    if actions
                    else ""
                )

                days_html = f"<b>Days Active:</b> {concern.get('days_active') or 1}"
                priority_html_str = f"<span style='color: {'#D0021B' if concern.get('priority') == org_report.PRIORITY_CRITICAL else '#F5A623'}'><b>{concern.get('priority', 'warning').upper()}</b></span>"

                item = f"{location_html} {priority_html_str}<br>{description}"
                if context_html:
                    item += f"<br>{context_html}"
                if actions_html:
                    item += f"<br>{actions_html}"
                item += f"<br>{days_html}"

                priority_html.append(item)

            content_array.append(
                {
                    "title": f"Top Infrastructure Issues ({len(top_concerns)} locations)",
                    "icon": "server",
                    "color": "e67e22",
                    "content": priority_html,
                }
            )

        # Section 3: Top Celebrations (Resolutions)
        celebrations = tech_report.get("top_celebrations", [])
        if celebrations:
            celebration_html = []
            for cel in celebrations[:10]:  # Top 10
                location_html = self._location_link_html(
                    botengine,
                    cel.get("location_id"),
                    cel.get("location_name", "Unknown"),
                )
                description = cel.get("enhanced_description") or cel.get(
                    "short_description", ""
                )
                days_html = f"<i>(resolved in {cel.get('days_to_resolve', 0)} days)</i>"

                item = f"✓ {location_html}: {description} {days_html}"
                celebration_html.append(item)

            content_array.append(
                {
                    "title": f"Resolutions & Improvements ({len(celebrations)} locations)",
                    "icon": "check-circle",
                    "color": "27ae60",
                    "content": celebration_html,
                }
            )

        # Section 4: Trends
        trends = tech_report.get("trends", [])
        if trends:
            trend_html = []
            for trend in trends:
                # Use enhanced trend description if available
                description = (
                    trend.get("trend_description")
                    or f"{trend.get('report_type', 'Issue')} affecting multiple locations"
                )
                locations_count = trend.get("locations_affected", 0)

                item = f"→ <b>{description}</b> ({locations_count} locations)"
                trend_html.append(item)

            content_array.append(
                {
                    "title": "Infrastructure Trends & Patterns",
                    "icon": "chart-line",
                    "color": "3498db",
                    "content": trend_html,
                }
            )

        # Section 5: Category Summary
        category_summary = tech_report.get("category_summary", {})
        if category_summary:
            summary_html = []
            if category_summary.get("summary_text"):
                summary_html.append(category_summary.get("summary_text"))
            else:
                # Fallback summary
                summary_html.append(
                    f"<b>{category_summary.get('total_reports', 0)} IT reports</b> from <b>{category_summary.get('unique_locations', 0)} locations</b>"
                )
                summary_html.append(
                    f"Critical: {category_summary.get('critical_count', 0)}, Warning: {category_summary.get('warning_count', 0)}"
                )
                summary_html.append(
                    f"Average duration: {category_summary.get('average_days_active', 0)} days"
                )

            content_array.append(
                {
                    "title": "IT Infrastructure Overview",
                    "icon": "clipboard-list",
                    "color": "95a5a6",
                    "content": summary_html,
                }
            )

        if len(content_array) == 0:
            logger.warning("|_email_tech_report() No content to send")
            logger.info("<_email_tech_report()")
            return

        # Format report date

        report_date = datetime.datetime.fromtimestamp(
            timestamp_ms / 1000, tz=pytz.utc
        ).strftime("%B %d, %Y")
        report_type = tech_report.get("report_type", "daily").capitalize()

        # Send email using server-side template
        logger.info(
            "|_email_tech_report() Sending email to admins (categories [1, 2])"
        )

        org_name = tech_report.get("org_name", "")
        org_prefix = f"{org_name} - " if org_name else ""
        botengine.email_admins(
            email_subject=f"🔧 {org_prefix}{tech.REPORT_TITLE} - {report_type} Report - {report_date}",
            email_html=True,
            email_template_filename=tech.EMAIL_TEMPLATE_FILENAME,
            email_template_model={
                "title": tech.REPORT_TITLE,
                "subtitle": f"{report_type} Report - {report_date}",
                "icon": tech.REPORT_ICON,
                "contentArray": content_array,
                "metadata": {
                    "org_name": tech_report.get("org_name", ""),
                    "report_type": report_type,
                    "timestamp_ms": timestamp_ms,
                },
            },
            categories=[
                utilities.ORGANIZATION_USER_NOTIFICATION_CATEGORY_MANAGER, 
                utilities.ORGANIZATION_USER_NOTIFICATION_CATEGORY_TECHNICIAN, 
                utilities.ORGANIZATION_USER_NOTIFICATION_CATEGORY_REPORTS
            ],  # Phase 1: Manager + Technician + Reports
        )

        logger.info("|_email_tech_report() Email sent successfully")
        logger.info("<_email_tech_report()")
