"""
Created on April 6, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Organization Device Analysis Microservice
==========================================

Receives a 'run_product_analysis' datastream message with device types and
parameters, then compiles a HIPAA-compliant PDF report with statistics and
LLM-generated insights, emailed to specified addresses.

Pipeline:
1. Request device listing for specified device types (async_data_request_ready)
2. Request parameter history for discovered devices (async_data_request_ready)
3. Compile statistics and build report skeleton
4. Enhance with up to 3 sequential LLM calls (overview, insights, recommendations)
5. Generate fpdf2 PDF, email to specified addresses
"""

import json
import re

import properties  # type: ignore
import utilities.utilities as utilities  # type: ignore
from intelligence.intelligence import Intelligence  # type: ignore

from . import report_builder, services


class OrganizationDeviceAnalysisMicroservice(Intelligence):
    """
    Organization-level microservice that analyzes device parameters across all
    child locations and generates a HIPAA-compliant PDF report with LLM-enhanced
    insights.

    Trigger: Manual only via 'run_product_analysis' datastream message.

    Pipeline:
    1. Pull device listing for requested device_types
    2. Pull parameter history for discovered devices
    3. Compile statistics
    4. Enhance via 3 sequential LLM calls (overview, insights, recommendations)
    5. Generate fpdf2 PDF and email to specified addresses
    """

    def __init__(self, botengine, parent):
        """
        :param botengine: BotEngine environment
        :param parent: Parent organization object
        """
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        """
        :param botengine: BotEngine environment
        """
        pass

    def destroy(self, botengine):
        """
        :param botengine: BotEngine environment
        """
        pass

    def new_version(self, botengine):
        """
        :param botengine: BotEngine environment
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(">new_version()")

    # ======================================================================
    # Datastream
    # ======================================================================
    def datastream_updated(self, botengine, address, content):
        """
        :param botengine: BotEngine environment
        :param address: Data stream address
        :param content: Data stream content (dict)
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    def run_product_analysis(self, botengine, content):
        """
        Trigger a new device analysis.

        Expected content:
        {
            "device_types": [10038],
            "parameters": ["motionStatus"],
            "email_addresses": ["admin@example.com"],
            "analysis_name": "Motion Sensor Analysis"
        }

        :param botengine: BotEngine environment
        :param content: Analysis configuration dict
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">run_product_analysis()")

        # Validate required fields
        required = ["device_types", "parameters", "email_addresses"]
        for field in required:
            if field not in content or not content[field]:
                logger.warning(
                    f"|run_product_analysis() Missing required field: {field}"
                )
                return

        # Guard against concurrent execution
        existing = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        if existing is not None:
            if not self.is_timer_running(botengine, "analysis_in_progress_reminder"):
                logger.error(
                    "|run_product_analysis() Analysis already in progress - starting reminder timer"
                )
                phase = existing.get("phase", "unknown")
                retry_count = existing.get("retry_count", 0)
                self.start_timer_s(
                    botengine,
                    10,
                    argument={
                        "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                        "phase": phase,
                        "retry_count": retry_count,
                    },
                    reference=f"data_request_timeout_{phase}",
                )
            else:
                logger.warning(
                    "|run_product_analysis() Analysis already in progress, skipping"
                )
            return

        # Check LLM availability
        llm_allowed = properties.get_property(botengine, "LLM_FEATURES_ALLOWED", False)

        # Save analysis configuration
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS,
            {
                "config": {
                    "device_types": content["device_types"],
                    "parameters": content["parameters"],
                    "email_addresses": content["email_addresses"],
                    "analysis_name": content.get("analysis_name", "Device Analysis"),
                },
                "phase": services.PHASE_DEVICES,
                "start_time": botengine.get_timestamp(),
                "devices_data": None,
                "params_data": None,
                "ready_for_processing": False,
                "disable_llm": not llm_allowed,
            },
            overwrite=True,
        )

        # Request device listing
        botengine.request_data(
            type=botengine.DATA_REQUEST_TYPE_DEVICES,
            reference=services.DATA_REQUEST_REFERENCE_DEVICES,
            device_types=content["device_types"],
        )

        self.start_timer_s(
            botengine,
            services.DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                "phase": services.PHASE_DEVICES,
                "retry_count": 0,
            },
            reference="data_request_timeout_devices",
        )

        logger.info("<run_product_analysis()")

    # ======================================================================
    # Timer
    # ======================================================================
    def timer_fired(self, botengine, argument):
        """
        Timer bridge for async data request phases.
        :param botengine: BotEngine environment
        :param argument: Timer argument dict
        """
        if not isinstance(argument, dict):
            return

        timer_type = argument.get("type")

        if timer_type == services.TIMER_TYPE_DATA_REQUEST_TIMEOUT:
            self._handle_data_request_timeout(botengine, argument)

    def _handle_data_request_timeout(self, botengine, argument):
        """
        Handle data request timeout - bridge async results to sync processing.
        :param botengine: BotEngine environment
        :param argument: Timer argument with phase and retry_count
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        retry_count = argument.get("retry_count", 0)
        phase = argument.get("phase", "")

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        if state is None:
            logger.warning("|_handle_data_request_timeout() No analysis in progress")
            return

        if state.get("ready_for_processing"):
            state["ready_for_processing"] = False
            botengine.save_variable(
                services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
            )

            if state["phase"] == services.PHASE_DEVICES:
                # Devices data is ready - now request parameters
                self._request_parameters(botengine, state)

            elif state["phase"] == services.PHASE_ANALYSIS:
                # Parameters data is ready - compile and analyze
                self._compile_and_analyze(botengine, state)

        elif state.get("phase") == services.PHASE_PARAMETERS:
            # Parameters phase: proceed with whatever data has arrived
            params_data = state.get("params_data", {})
            expected = state.get("expected_param_responses", 0)
            received = len(params_data)

            if received > 0 or retry_count >= services.MAX_DATA_REQUEST_RETRIES:
                logger.info(
                    f"|_handle_data_request_timeout() Params phase: proceeding with {received}/{expected} device responses"
                )
                state["phase"] = services.PHASE_ANALYSIS
                state["ready_for_processing"] = False
                botengine.save_variable(
                    services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
                )
                self._compile_and_analyze(botengine, state)
            else:
                logger.info(
                    f"|_handle_data_request_timeout() Params phase: no data yet, retry {retry_count + 1}/{services.MAX_DATA_REQUEST_RETRIES}"
                )
                self.start_timer_s(
                    botengine,
                    services.DATA_REQUEST_TIMEOUT_S,
                    argument={
                        "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                        "phase": phase,
                        "retry_count": retry_count + 1,
                    },
                    reference=f"data_request_timeout_{phase}",
                )

        else:
            if retry_count >= services.MAX_DATA_REQUEST_RETRIES:
                logger.warning(
                    f"|_handle_data_request_timeout() Max retries exceeded for phase={phase}. Cleaning up."
                )
                self._cleanup(botengine)
                return

            logger.info(
                f"|_handle_data_request_timeout() Retry {retry_count + 1}/{services.MAX_DATA_REQUEST_RETRIES} for phase={phase}"
            )
            self.start_timer_s(
                botengine,
                services.DATA_REQUEST_TIMEOUT_S,
                argument={
                    "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                    "phase": phase,
                    "retry_count": retry_count + 1,
                },
                reference=f"data_request_timeout_{phase}",
            )

    # ======================================================================
    # Data Request
    # ======================================================================
    def async_data_request_ready(self, botengine, reference, content):
        """
        Data request ready (async context - NO timers or class variable changes).
        :param botengine: BotEngine environment
        :param reference: Data request reference
        :param content: Data request content
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">async_data_request_ready() reference={reference}")

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        if state is None:
            logger.warning("|async_data_request_ready() No analysis in progress")
            return

        if reference == services.DATA_REQUEST_REFERENCE_DEVICES:
            self._process_devices_data(botengine, state, content)

        elif reference.startswith(services.DATA_REQUEST_REFERENCE_PARAMS):
            self._process_params_data(botengine, state, reference, content)

        logger.info("<async_data_request_ready()")

    def _process_devices_data(self, botengine, state, content):
        """
        Process device listing response (async context).
        :param botengine: BotEngine environment
        :param state: Current analysis state
        :param content: Device listing data
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_process_devices_data()")

        # Parse device listing from bot.py format:
        #   content[location_id][device_id] = {deviceType, description, ...}
        # Server may return all devices, so filter client-side by requested types
        config = state["config"]
        requested_types = set(str(t) for t in config.get("device_types", []))

        devices_by_location = {}
        device_ids = []

        if isinstance(content, dict):
            for location_id, location_devices in content.items():
                if not isinstance(location_devices, dict):
                    logger.warning(
                        f"|_process_devices_data() Skipping location with non-dict devices: loc={location_id} devices={location_devices}"
                    )
                    continue

                location_id = str(location_id)
                for device_id, device_info in location_devices.items():
                    if not isinstance(device_info, dict):
                        logger.warning(
                            f"|_process_devices_data() Skipping device with non-dict info: loc={location_id} dev={device_id} info={device_info}"
                        )
                        continue
                    device_type = device_info.get(
                        "deviceType", device_info.get("type", 0)
                    )

                    # Filter by requested device types
                    if requested_types and str(device_type) not in requested_types:
                        logger.info(
                            f"|_process_devices_data() Skipping device {device_id} of type {device_type} not in requested types"
                        )
                        continue

                    desc = device_info.get("description", device_info.get("desc", ""))

                    if location_id not in devices_by_location:
                        devices_by_location[location_id] = []

                    logger.info(
                        f"|_process_devices_data() Adding device: loc={location_id} dev={device_id} type={device_type} desc={desc}"
                    )
                    devices_by_location[location_id].append(
                        {
                            "device_id": device_id,
                            "device_type": device_type,
                            "description": desc,
                        }
                    )
                    device_ids.append(device_id)

        if not device_ids:
            # Log content structure for debugging
            if isinstance(content, dict):
                sample_locations = list(content.keys())[:3]
                for loc in sample_locations:
                    loc_devs = content.get(loc, {})
                    if isinstance(loc_devs, dict):
                        sample_devs = list(loc_devs.keys())[:2]
                        for dev in sample_devs:
                            logger.warning(
                                f"|_process_devices_data() Sample: loc={loc} dev={dev} info={loc_devs[dev]}"
                            )
                    else:
                        logger.warning(
                            f"|_process_devices_data() Location {loc} has non-dict value: {type(loc_devs).__name__}"
                        )
            else:
                logger.warning(
                    f"|_process_devices_data() Content is {type(content).__name__}, not dict"
                )
            logger.warning(
                f"|_process_devices_data() No devices found for requested types {requested_types}"
            )

        state["devices_data"] = {
            "devices_by_location": devices_by_location,
            "device_ids": device_ids,
            "total_devices": len(device_ids),
            "total_locations": len(devices_by_location),
        }
        state["phase"] = services.PHASE_DEVICES
        state["ready_for_processing"] = True

        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        logger.info(
            f"|_process_devices_data() Found {len(device_ids)} devices across {len(devices_by_location)} locations"
        )
        logger.info("<_process_devices_data()")

    def _process_params_data(self, botengine, state, reference, content):
        """
        Process a single device's parameter history response (async context).
        Accumulates results into params_data. The timer will proceed with
        whatever data has arrived when it fires.

        :param botengine: BotEngine environment
        :param state: Current analysis state
        :param reference: Data request reference (device_analysis_params_{device_id})
        :param content: Parameter data for one device
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        # Extract device_id from reference
        prefix = services.DATA_REQUEST_REFERENCE_PARAMS + "_"
        device_id = reference[len(prefix) :] if reference.startswith(prefix) else None

        # Initialize params_data dict if needed
        if state.get("params_data") is None:
            state["params_data"] = {}

        # Accumulate this device's data
        if device_id and isinstance(content, dict):
            state["params_data"][device_id] = content
            logger.info(
                f"|_process_params_data() Received params for device {device_id} "
                f"({len(state['params_data'])}/{state.get('expected_param_responses', '?')} devices)"
            )
        elif isinstance(content, dict):
            # Fallback: merge entire content
            state["params_data"].update(content)

        # Check if all devices have responded
        expected = state.get("expected_param_responses", 0)
        received = len(state["params_data"])
        if expected > 0 and received >= expected:
            logger.info(
                f"|_process_params_data() All {received} device responses received"
            )
            state["phase"] = services.PHASE_ANALYSIS
            state["ready_for_processing"] = True

        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

    # ======================================================================
    # Parameter Requests
    # ======================================================================
    def _request_parameters(self, botengine, state):
        """
        Request parameter history for all discovered devices.
        :param botengine: BotEngine environment
        :param state: Current analysis state
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_request_parameters()")

        devices_data = state.get("devices_data", {})
        device_ids = devices_data.get("device_ids", [])
        config = state["config"]
        param_names = config["parameters"]

        if not device_ids:
            logger.warning(
                "|_request_parameters() No devices to request parameters for"
            )
            # Skip to analysis with empty data
            state["params_data"] = {}
            state["phase"] = services.PHASE_ANALYSIS
            botengine.save_variable(
                services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
            )
            self._compile_and_analyze(botengine, state)
            return

        cutoff_ms = botengine.get_timestamp() - (
            services.PARAM_LOOKBACK_DAYS * utilities.ONE_DAY_MS
        )

        # Build device_id -> location_id map for the API
        devices_by_location = devices_data.get("devices_by_location", {})
        device_location_map = {}
        for loc_id, devices in devices_by_location.items():
            for dev in devices:
                device_location_map[dev["device_id"]] = loc_id

        # Track how many responses we expect
        state["params_data"] = {}
        state["expected_param_responses"] = len(device_ids)
        state["phase"] = services.PHASE_PARAMETERS
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        for device_id in device_ids:
            botengine.request_data(
                type=botengine.DATA_REQUEST_TYPE_PARAMETERS,
                device_id=device_id,
                param_name_list=param_names,
                reference=f"{services.DATA_REQUEST_REFERENCE_PARAMS}_{device_id}",
                oldest_timestamp_ms=cutoff_ms,
                newest_timestamp_ms=botengine.get_timestamp(),
            )

        # Start timeout timer for parameter requests
        self.start_timer_s(
            botengine,
            services.DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                "phase": services.PHASE_PARAMETERS,
                "retry_count": 0,
            },
            reference="data_request_timeout_params",
        )

        logger.info(
            f"|_request_parameters() Requested params for {len(device_ids)} devices"
        )
        logger.info("<_request_parameters()")

    # ======================================================================
    # Analysis
    # ======================================================================
    def _compile_and_analyze(self, botengine, state):
        """
        Compile statistics and start LLM enhancement pipeline.
        :param botengine: BotEngine environment
        :param state: Current analysis state
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_compile_and_analyze()")

        config = state["config"]
        devices_data = state.get("devices_data", {})
        params_data = state.get("params_data", {})

        # Compile statistics
        stats = report_builder.compile_statistics(devices_data, params_data, config)

        # Build enhancement tasks
        enhancement_tasks = self._build_enhancement_tasks(stats, config)

        report = {
            "config": config,
            "stats": stats,
            "enhancement_tasks": enhancement_tasks,
            "llm_results": {},
        }

        state["report"] = report
        state["tasks_remaining"] = len(enhancement_tasks)
        state["tasks_completed"] = 0

        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        if state.get("disable_llm") or not enhancement_tasks:
            logger.info("|_compile_and_analyze() LLM disabled or no tasks, finalizing")
            self._finalize_report(botengine, report, state["start_time"])
        else:
            self._process_next_enhancement_task(botengine, enhancement_tasks[0])

        logger.info("<_compile_and_analyze()")

    def _build_enhancement_tasks(self, stats, config):
        """
        Build up to 3 LLM enhancement tasks.
        :param stats: Compiled statistics dict
        :param config: Analysis configuration
        :return: List of enhancement task dicts
        """
        tasks = []
        summary = stats.get("summary", {})

        # Task 1: Device fleet overview
        tasks.append(
            {
                "task_id": "task_device_overview",
                "task_type": services.TASK_DEVICE_OVERVIEW,
                "fields_to_fill": ["overview_text"],
                "data": {
                    "total_devices": summary.get("total_devices", 0),
                    "total_locations": summary.get("total_locations", 0),
                    "device_type_counts": stats.get("device_stats", {}).get(
                        "by_type", {}
                    ),
                    "analysis_name": config.get("analysis_name", "Device Analysis"),
                },
            }
        )

        # Task 2: Parameter insights
        if stats.get("parameter_stats"):
            tasks.append(
                {
                    "task_id": "task_parameter_insights",
                    "task_type": services.TASK_PARAMETER_INSIGHTS,
                    "fields_to_fill": ["insights_text"],
                    "data": {
                        "parameter_stats": stats["parameter_stats"],
                        "total_devices": summary.get("total_devices", 0),
                    },
                }
            )

        # Task 3: Recommendations
        tasks.append(
            {
                "task_id": "task_recommendations",
                "task_type": services.TASK_RECOMMENDATIONS,
                "fields_to_fill": ["recommendations_text"],
                "data": {
                    "total_devices": summary.get("total_devices", 0),
                    "total_locations": summary.get("total_locations", 0),
                    "device_type_counts": stats.get("device_stats", {}).get(
                        "by_type", {}
                    ),
                    "parameter_summary": {
                        k: {
                            "mean": v.get("mean"),
                            "stddev": v.get("stddev"),
                            "sample_count": v.get("sample_count"),
                        }
                        for k, v in stats.get("parameter_stats", {}).items()
                    },
                },
            }
        )

        return tasks

    # ======================================================================
    # LLM Enhancement
    # ======================================================================
    def llm_response(self, botengine, response, reference, argument):
        """
        :param botengine: BotEngine environment
        :param response: LLM response content
        :param reference: Reference ID
        :param argument: Original argument
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">llm_response() reference={reference}")

        Intelligence.llm_response(self, botengine, response, reference, argument)

        if reference == services.LLM_REFERENCE_DEVICE_ANALYSIS:
            self._handle_llm_response(botengine, response, argument)

        logger.info("<llm_response()")

    def _handle_llm_response(self, botengine, response, argument):
        """
        Handle LLM enhancement response and advance the pipeline.
        :param botengine: BotEngine environment
        :param response: LLM response dict
        :param argument: Task argument
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_handle_llm_response()")

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        if not state:
            logger.error("|_handle_llm_response() No analysis in progress")
            return

        report = state["report"]
        task_id = argument.get("task_id")
        fields_to_fill = argument.get("fields_to_fill", [])

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
                    f"|_handle_llm_response() Fallback content extraction, length={len(content)}"
                )

            # Parse fields from LLM response
            enhanced_text = self._parse_llm_text_response(content, fields_to_fill)
            report["llm_results"][task_id] = enhanced_text

            # Advance pipeline
            state["report"] = report
            state["tasks_completed"] += 1
            tasks_remaining = state["tasks_remaining"] - 1
            state["tasks_remaining"] = tasks_remaining

            botengine.save_variable(
                services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
            )

            if tasks_remaining <= 0:
                self._finalize_report(botengine, report, state["start_time"])
            else:
                all_tasks = report["enhancement_tasks"]
                next_index = state["tasks_completed"]
                if next_index < len(all_tasks):
                    self._process_next_enhancement_task(
                        botengine, all_tasks[next_index]
                    )

        except Exception as e:
            import traceback

            logger.error(
                f"|_handle_llm_response() Error: {e}\n{traceback.format_exc()}"
            )

            # Advance pipeline despite error
            state["tasks_completed"] += 1
            tasks_remaining = state["tasks_remaining"] - 1
            state["tasks_remaining"] = tasks_remaining
            botengine.save_variable(
                services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
            )

            if tasks_remaining <= 0:
                self._finalize_report(botengine, report, state["start_time"])
            else:
                all_tasks = report["enhancement_tasks"]
                next_index = state["tasks_completed"]
                if next_index < len(all_tasks):
                    self._process_next_enhancement_task(
                        botengine, all_tasks[next_index]
                    )

        logger.info("<_handle_llm_response()")

    def _process_next_enhancement_task(self, botengine, task):
        """
        Send the next LLM enhancement request.
        :param botengine: BotEngine environment
        :param task: Enhancement task dict
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">_process_next_enhancement_task() task_id={task['task_id']}")

        messages, max_tokens = self._build_enhancement_messages(task)
        if not messages:
            logger.warning(
                f"|_process_next_enhancement_task() Empty messages for {task['task_id']}, skipping"
            )
            return

        self.llm_chat(
            botengine,
            reference=services.LLM_REFERENCE_DEVICE_ANALYSIS,
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

    def _build_enhancement_messages(self, task):
        """
        Build LLM message list for a given enhancement task.
        :param task: Enhancement task dict
        :return: Tuple of (messages list, max_tokens int)
        """
        task_type = task["task_type"]
        data = task["data"]

        if task_type == services.TASK_DEVICE_OVERVIEW:
            return self._build_overview_messages(data)
        elif task_type == services.TASK_PARAMETER_INSIGHTS:
            return self._build_insights_messages(data)
        elif task_type == services.TASK_RECOMMENDATIONS:
            return self._build_recommendations_messages(data)

        return [], 0

    def _build_overview_messages(self, data):
        """
        Build messages for fleet overview LLM task.
        :param data: Task data dict
        :return: Tuple of (messages list, max_tokens)
        """
        system_content = (
            services.SYSTEM_PROMPT + "\n\n"
            "YOUR TASK: Write a fleet overview paragraph summarizing the device "
            "deployment across all locations.\n\n"
            "REQUIREMENTS:\n"
            "- 3-4 sentences, maximum 150 words\n"
            "- Professional language appropriate for administrators\n"
            "- Be specific with numbers from the data\n"
            "- Highlight deployment coverage and any notable distribution patterns\n"
            "- Use location IDs only, never names or addresses\n\n"
            "OUTPUT FORMAT:\n"
            "overview_text: <your paragraph here>"
        )

        user_content = (
            "DATA:\n"
            f"- Analysis: {data.get('analysis_name', 'Device Analysis')}\n"
            f"- Total devices: {data.get('total_devices', 0)}\n"
            f"- Total locations: {data.get('total_locations', 0)}\n"
            f"- Devices by type: {json.dumps(data.get('device_type_counts', {}))}\n"
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        return messages, services.LLM_MAX_TOKENS_OVERVIEW

    def _build_insights_messages(self, data):
        """
        Build messages for parameter insights LLM task.
        :param data: Task data dict
        :return: Tuple of (messages list, max_tokens)
        """
        # Summarize parameter stats for prompt (exclude raw values for HIPAA)
        param_summary = {}
        for param_name, stats in data.get("parameter_stats", {}).items():
            mean = stats.get("mean")
            stddev = stats.get("stddev")
            param_summary[param_name] = {
                "min": stats.get("min"),
                "max": stats.get("max"),
                "mean": round(mean, 2) if mean is not None else "N/A",
                "median": stats.get("median"),
                "stddev": round(stddev, 2) if stddev is not None else "N/A",
                "sample_count": stats.get("sample_count", 0),
                "unique_values": stats.get("unique_values", 0),
            }

        system_content = (
            services.SYSTEM_PROMPT + "\n\n"
            "YOUR TASK: Analyze parameter statistics and identify notable "
            "patterns, outliers, or concerning values.\n\n"
            "REQUIREMENTS:\n"
            "- 3-5 sentences, maximum 200 words\n"
            "- Reference parameters by name\n"
            "- Highlight any unusual distributions or high variability\n"
            "- Do not reference any personally identifiable information\n\n"
            "OUTPUT FORMAT:\n"
            "insights_text: <your analysis paragraph here>"
        )

        user_content = (
            "PARAMETER STATISTICS:\n"
            f"- Total devices sampled: {data.get('total_devices', 0)}\n"
            f"- Parameters: {json.dumps(param_summary, indent=2)}\n"
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        return messages, services.LLM_MAX_TOKENS_INSIGHTS

    def _build_recommendations_messages(self, data):
        """
        Build messages for recommendations LLM task.
        :param data: Task data dict
        :return: Tuple of (messages list, max_tokens)
        """
        system_content = (
            services.SYSTEM_PROMPT + "\n\n"
            "YOUR TASK: Provide 3-5 actionable recommendations for device fleet "
            "management based on the analysis data.\n\n"
            "REQUIREMENTS:\n"
            "- Numbered list of 3-5 concise recommendations\n"
            "- Each recommendation should be 1-2 sentences\n"
            "- Focus on operational improvements\n"
            "- Do not reference any personally identifiable information\n\n"
            "OUTPUT FORMAT:\n"
            "recommendations_text: <your numbered recommendations here>"
        )

        user_content = (
            "FLEET DATA:\n"
            f"- Total devices: {data.get('total_devices', 0)}\n"
            f"- Total locations: {data.get('total_locations', 0)}\n"
            f"- Devices by type: {json.dumps(data.get('device_type_counts', {}))}\n"
            f"- Parameter summary: {json.dumps(data.get('parameter_summary', {}))}\n"
        )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        return messages, services.LLM_MAX_TOKENS_RECOMMENDATIONS

    def _parse_llm_text_response(self, content, expected_fields):
        """
        Parse "field_name: value" format from LLM response.
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
            elif len(expected_fields) == 1:
                result[field] = content.strip()
            else:
                result[field] = ""
        return result

    # ======================================================================
    # Finalization
    # ======================================================================
    def _finalize_report(self, botengine, report, start_time):
        """
        Generate PDF and email the report.
        :param botengine: BotEngine environment
        :param report: Complete report dict
        :param start_time: Pipeline start timestamp
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_finalize_report()")

        config = report["config"]

        try:
            import base64

            # Generate PDF
            pdf_bytes = report_builder.generate_pdf(
                report,
                config.get("analysis_name", "Device Analysis"),
                botengine.get_timestamp(),
            )

            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Generate HTML email summary
            html_summary = report_builder.generate_html_summary(
                report, config.get("analysis_name", "Device Analysis")
            )

            # Build email with PDF attachment
            attachments = []
            botengine.add_email_attachment(
                destination_attachment_array=attachments,
                filename="Device_Analysis_Report.pdf",
                content=pdf_base64,
                content_type="application/pdf",
                content_id="device_analysis_pdf",
            )

            botengine.email_admins(
                email_subject="{} - Device Analysis Report".format(
                    config.get("analysis_name", "Device Analysis")
                ),
                email_content=html_summary,
                email_html=True,
                email_attachments=attachments,
                email_addresses=config.get("email_addresses"),
                brand=properties.get_property(
                    botengine,
                    "ORGANIZATION_BRAND",
                    complain_if_missing=False,
                ),
            )

            logger.info("|_finalize_report() PDF generated and emailed")

        except ImportError as e:
            logger.warning(f"|_finalize_report() Missing dependency: {e}")
        except Exception as e:
            import traceback

            logger.error(f"|_finalize_report() Error: {e}\n{traceback.format_exc()}")

        self._cleanup(botengine)

        duration_ms = botengine.get_timestamp() - start_time
        logger.info(f"|_finalize_report() Completed in {duration_ms}ms")
        logger.info("<_finalize_report()")

    def _cleanup(self, botengine):
        """
        Clear analysis state.
        :param botengine: BotEngine environment
        """
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, None, overwrite=True
        )
