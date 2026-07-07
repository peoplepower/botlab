from unittest.mock import patch

from intelligence.device_analysis import report_builder, services
from organization.organization import Organization  # type: ignore

from botengine_pytest import BotEnginePyTest


# ===========================================================================
# Sample Data Helpers
# ===========================================================================
def _sample_config():
    return {
        "device_types": [10038, 10036],
        "parameters": ["motionStatus", "state"],
        "email_addresses": ["admin@example.com"],
        "analysis_name": "Test Analysis",
    }


def _sample_devices_content():
    """Simulate DATA_REQUEST_TYPE_DEVICES response from bot.py:
    content[location_id][device_id] = {deviceType, description, ...}
    """
    return {
        "100": {
            "dev_001": {
                "deviceType": 10038,
                "description": "Motion Sensor A",
            },
            "dev_002": {
                "deviceType": 10036,
                "description": "Light Switch A",
            },
        },
        "200": {
            "dev_003": {
                "deviceType": 10038,
                "description": "Motion Sensor B",
            },
        },
        "300": {
            "dev_004": {
                "deviceType": 10038,
                "description": "Motion Sensor C",
            },
        },
    }


def _sample_params_content():
    """Simulate DATA_REQUEST_TYPE_PARAMETERS response."""
    return {
        "dev_001": {
            "motionStatus": [
                {"value": "1", "time": 1000},
                {"value": "0", "time": 2000},
                {"value": "1", "time": 3000},
            ],
            "state": [],
        },
        "dev_002": {
            "motionStatus": [],
            "state": [
                {"value": "1", "time": 1000},
                {"value": "0", "time": 2000},
            ],
        },
        "dev_003": {
            "motionStatus": [
                {"value": "1", "time": 1000},
                {"value": "1", "time": 2000},
                {"value": "0", "time": 3000},
                {"value": "1", "time": 4000},
            ],
        },
        "dev_004": {
            "motionStatus": [
                {"value": "0", "time": 1000},
            ],
        },
    }


def _sample_devices_data():
    """Pre-processed devices_data structure."""
    return {
        "devices_by_location": {
            "100": [
                {
                    "device_id": "dev_001",
                    "device_type": 10038,
                    "description": "Motion A",
                },
                {
                    "device_id": "dev_002",
                    "device_type": 10036,
                    "description": "Light A",
                },
            ],
            "200": [
                {
                    "device_id": "dev_003",
                    "device_type": 10038,
                    "description": "Motion B",
                },
            ],
            "300": [
                {
                    "device_id": "dev_004",
                    "device_type": 10038,
                    "description": "Motion C",
                },
            ],
        },
        "device_ids": ["dev_001", "dev_002", "dev_003", "dev_004"],
        "total_devices": 4,
        "total_locations": 3,
    }


def _build_analysis_state(phase=services.PHASE_DEVICES, ready=False):
    """Build a minimal analysis state dict."""
    return {
        "config": _sample_config(),
        "phase": phase,
        "start_time": 1773550800000,
        "devices_data": _sample_devices_data(),
        "params_data": None,
        "ready_for_processing": ready,
        "disable_llm": False,
    }


def _build_report_with_stats():
    """Build a complete report dict with compiled stats."""
    config = _sample_config()
    devices_data = _sample_devices_data()
    params_data = _sample_params_content()
    stats = report_builder.compile_statistics(devices_data, params_data, config)
    return {
        "config": config,
        "stats": stats,
        "enhancement_tasks": [],
        "llm_results": {},
    }


# ===========================================================================
# Microservice Tests
# ===========================================================================
class TestDeviceAnalysisMicroservice:
    def _setup(self):
        botengine = BotEnginePyTest({})
        botengine.reset()
        organization = Organization(botengine, 0)
        organization.new_version(botengine)
        organization.initialize(botengine)
        mut = organization.intelligence_modules[
            "intelligence.device_analysis.organization_device_analysis_microservice"
        ]
        return botengine, organization, mut

    def test_initialization(self):
        """Module should initialize without errors."""
        botengine, organization, mut = self._setup()
        assert mut is not None
        mut.new_version(botengine)

    def test_datastream_routing(self):
        """Datastream should dispatch to run_product_analysis."""
        botengine, organization, mut = self._setup()

        with patch.object(mut, "run_product_analysis") as mock_rpa:
            mut.datastream_updated(botengine, "run_product_analysis", {"test": True})
            mock_rpa.assert_called_once_with(botengine, {"test": True})

        # Unknown address should not crash
        mut.datastream_updated(botengine, "unknown_address", {})

    def test_run_product_analysis_validates_input(self):
        """Missing required fields should cause early return."""
        botengine, organization, mut = self._setup()

        # Missing device_types
        mut.run_product_analysis(
            botengine, {"parameters": ["x"], "email_addresses": ["a@b.com"]}
        )
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

        # Missing parameters
        mut.run_product_analysis(
            botengine, {"device_types": [10038], "email_addresses": ["a@b.com"]}
        )
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

        # Missing email_addresses
        mut.run_product_analysis(
            botengine, {"device_types": [10038], "parameters": ["x"]}
        )
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

        # Empty lists should also fail
        mut.run_product_analysis(
            botengine,
            {"device_types": [], "parameters": ["x"], "email_addresses": ["a@b.com"]},
        )
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

    def test_run_product_analysis_starts_pipeline(self):
        """Valid input should save state and request data."""
        botengine, organization, mut = self._setup()
        config = _sample_config()

        with patch.object(botengine, "request_data") as mock_rd:
            mut.run_product_analysis(botengine, config)
            mock_rd.assert_called_once()
            assert (
                mock_rd.call_args[1]["reference"]
                == services.DATA_REQUEST_REFERENCE_DEVICES
            )
            assert mock_rd.call_args[1]["device_types"] == config["device_types"]

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state is not None
        assert state["phase"] == services.PHASE_DEVICES
        assert state["config"]["device_types"] == config["device_types"]

    def test_concurrent_execution_guard(self):
        """Should reject new analysis when one is already in progress."""
        botengine, organization, mut = self._setup()

        # Start first analysis
        with patch.object(botengine, "request_data"):
            mut.run_product_analysis(botengine, _sample_config())

        # Second attempt should be rejected
        with patch.object(botengine, "request_data") as mock_rd:
            mut.run_product_analysis(botengine, _sample_config())
            mock_rd.assert_not_called()

    def test_async_data_request_devices(self):
        """Devices data request should parse and save device listing."""
        botengine, organization, mut = self._setup()

        # Set up initial state
        state = _build_analysis_state()
        state["devices_data"] = None
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        # Process device listing
        mut.async_data_request_ready(
            botengine,
            services.DATA_REQUEST_REFERENCE_DEVICES,
            _sample_devices_content(),
        )

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state["ready_for_processing"] is True
        devices = state["devices_data"]
        assert devices["total_devices"] == 4
        assert devices["total_locations"] == 3
        assert len(devices["device_ids"]) == 4
        assert "100" in devices["devices_by_location"]
        assert len(devices["devices_by_location"]["100"]) == 2

    def test_async_data_request_params(self):
        """Parameter data request should save and mark ready."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state(phase=services.PHASE_PARAMETERS)
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        params = _sample_params_content()
        mut.async_data_request_ready(
            botengine, services.DATA_REQUEST_REFERENCE_PARAMS, params
        )

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state["phase"] == services.PHASE_ANALYSIS
        assert state["ready_for_processing"] is True
        assert state["params_data"] is not None

    def test_async_data_request_unknown_reference(self):
        """Unknown reference should be ignored."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state()
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        mut.async_data_request_ready(botengine, "unknown_reference", {})
        # State should be unchanged
        state2 = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state2["ready_for_processing"] is False

    def test_async_data_request_no_state(self):
        """No analysis in progress should not crash."""
        botengine, organization, mut = self._setup()
        mut.async_data_request_ready(
            botengine, services.DATA_REQUEST_REFERENCE_DEVICES, {}
        )

    def test_timer_bridge_devices_ready(self):
        """Timer should bridge devices phase to parameter requests."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state(phase=services.PHASE_DEVICES, ready=True)
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        with patch.object(mut, "_request_parameters") as mock_rp:
            mut.timer_fired(
                botengine,
                {
                    "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                    "phase": services.PHASE_DEVICES,
                    "retry_count": 0,
                },
            )
            mock_rp.assert_called_once()

    def test_timer_bridge_analysis_ready(self):
        """Timer should bridge analysis phase to compile_and_analyze."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state(phase=services.PHASE_ANALYSIS, ready=True)
        state["params_data"] = _sample_params_content()
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        with patch.object(mut, "_compile_and_analyze") as mock_ca:
            mut.timer_fired(
                botengine,
                {
                    "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                    "phase": services.PHASE_PARAMETERS,
                    "retry_count": 0,
                },
            )
            mock_ca.assert_called_once()

    def test_timer_retry_and_max(self):
        """Timer should retry up to max, then give up."""
        botengine, organization, mut = self._setup()

        # Not ready yet -> should retry
        state = _build_analysis_state(phase=services.PHASE_DEVICES, ready=False)
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        with patch.object(mut, "start_timer_s") as mock_timer:
            mut.timer_fired(
                botengine,
                {
                    "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                    "phase": services.PHASE_DEVICES,
                    "retry_count": 0,
                },
            )
            mock_timer.assert_called_once()
            assert mock_timer.call_args[1]["argument"]["retry_count"] == 1

        # Max retries -> should give up and clean up
        with patch.object(mut, "start_timer_s") as mock_timer:
            mut.timer_fired(
                botengine,
                {
                    "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                    "phase": services.PHASE_DEVICES,
                    "retry_count": services.MAX_DATA_REQUEST_RETRIES,
                },
            )
            mock_timer.assert_not_called()

    def test_timer_non_dict_argument(self):
        """Non-dict timer argument should be ignored."""
        botengine, organization, mut = self._setup()
        mut.timer_fired(botengine, "not_a_dict")
        mut.timer_fired(botengine, 42)
        mut.timer_fired(botengine, None)

    def test_request_parameters_issues_requests(self):
        """Should issue one request_data per device."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state()
        with patch.object(botengine, "request_data") as mock_rd:
            mut._request_parameters(botengine, state)
            assert mock_rd.call_count == 4  # 4 devices
            for call in mock_rd.call_args_list:
                assert call[1]["reference"] == services.DATA_REQUEST_REFERENCE_PARAMS
                assert call[1]["param_name_list"] == ["motionStatus", "state"]

    def test_request_parameters_no_devices(self):
        """Empty device list should skip to analysis."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state()
        state["devices_data"]["device_ids"] = []

        with patch.object(mut, "_compile_and_analyze") as mock_ca:
            mut._request_parameters(botengine, state)
            mock_ca.assert_called_once()

    def test_compile_and_analyze_with_llm(self):
        """Should build tasks and start LLM pipeline."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state(phase=services.PHASE_ANALYSIS)
        state["params_data"] = _sample_params_content()

        with patch.object(mut, "_process_next_enhancement_task") as mock_next:
            mut._compile_and_analyze(botengine, state)
            mock_next.assert_called_once()

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        report = state["report"]
        assert "stats" in report
        assert len(report["enhancement_tasks"]) == 3
        assert (
            report["enhancement_tasks"][0]["task_type"] == services.TASK_DEVICE_OVERVIEW
        )
        assert (
            report["enhancement_tasks"][1]["task_type"]
            == services.TASK_PARAMETER_INSIGHTS
        )
        assert (
            report["enhancement_tasks"][2]["task_type"] == services.TASK_RECOMMENDATIONS
        )

    def test_compile_and_analyze_llm_disabled(self):
        """LLM disabled should skip straight to finalize."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state(phase=services.PHASE_ANALYSIS)
        state["params_data"] = _sample_params_content()
        state["disable_llm"] = True

        with patch.object(mut, "_finalize_report") as mock_fin:
            mut._compile_and_analyze(botengine, state)
            mock_fin.assert_called_once()

    def test_llm_response_routing(self):
        """LLM response should route to handler on correct reference."""
        botengine, organization, mut = self._setup()

        with patch.object(mut, "_handle_llm_response") as mock_h:
            mut.llm_response(
                botengine,
                {"choices": [{"message": {"content": "text"}}]},
                services.LLM_REFERENCE_DEVICE_ANALYSIS,
                {"task_id": "t"},
            )
            mock_h.assert_called_once()

        # Unknown reference should not route
        with patch.object(mut, "_handle_llm_response") as mock_h:
            mut.llm_response(botengine, {}, "unknown_reference", {})
            mock_h.assert_not_called()

    def test_llm_pipeline_chaining(self):
        """LLM responses should chain to next task, then finalize on last."""
        botengine, organization, mut = self._setup()

        # Set up state with 3 tasks
        state = _build_analysis_state(phase=services.PHASE_ANALYSIS)
        state["params_data"] = _sample_params_content()
        # Build the report to get real enhancement tasks
        mut._compile_and_analyze(botengine, state)
        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        total_tasks = state["tasks_remaining"]
        assert total_tasks == 3

        # Task 1 -> should chain to task 2
        with patch.object(mut, "_process_next_enhancement_task") as mock_next:
            mut._handle_llm_response(
                botengine,
                {
                    "choices": [
                        {"message": {"content": "overview_text: Fleet overview."}}
                    ]
                },
                {
                    "task_id": "task_device_overview",
                    "task_type": services.TASK_DEVICE_OVERVIEW,
                    "fields_to_fill": ["overview_text"],
                },
            )
            mock_next.assert_called_once()

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state["tasks_completed"] == 1
        assert state["tasks_remaining"] == 2
        assert (
            state["report"]["llm_results"]["task_device_overview"]["overview_text"]
            == "Fleet overview."
        )

        # Task 2 -> should chain to task 3
        with patch.object(mut, "_process_next_enhancement_task") as mock_next:
            mut._handle_llm_response(
                botengine,
                {
                    "choices": [
                        {"message": {"content": "insights_text: Parameter insights."}}
                    ]
                },
                {
                    "task_id": "task_parameter_insights",
                    "task_type": services.TASK_PARAMETER_INSIGHTS,
                    "fields_to_fill": ["insights_text"],
                },
            )
            mock_next.assert_called_once()

        # Task 3 (last) -> should finalize
        with patch.object(mut, "_finalize_report") as mock_fin:
            mut._handle_llm_response(
                botengine,
                {"choices": [{"message": {"content": "recommendations_text: Do X."}}]},
                {
                    "task_id": "task_recommendations",
                    "task_type": services.TASK_RECOMMENDATIONS,
                    "fields_to_fill": ["recommendations_text"],
                },
            )
            mock_fin.assert_called_once()

    def test_llm_error_advances_pipeline(self):
        """LLM error should skip task and continue."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state(phase=services.PHASE_ANALYSIS)
        state["params_data"] = _sample_params_content()
        mut._compile_and_analyze(botengine, state)

        # Empty response -> should advance, not crash
        with patch.object(mut, "_process_next_enhancement_task"):
            mut._handle_llm_response(
                botengine,
                {},
                {
                    "task_id": "task_device_overview",
                    "task_type": services.TASK_DEVICE_OVERVIEW,
                    "fields_to_fill": ["overview_text"],
                },
            )

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state["tasks_completed"] >= 1

    def test_llm_error_on_last_task_finalizes(self):
        """LLM error on final task should still finalize."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state(phase=services.PHASE_ANALYSIS)
        state["params_data"] = _sample_params_content()
        mut._compile_and_analyze(botengine, state)

        # Advance to last task
        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        state["tasks_remaining"] = 1
        state["tasks_completed"] = 2
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        with patch.object(mut, "_finalize_report") as mock_fin:
            mut._handle_llm_response(
                botengine,
                None,
                {
                    "task_id": "task_recommendations",
                    "task_type": services.TASK_RECOMMENDATIONS,
                    "fields_to_fill": ["recommendations_text"],
                },
            )
            mock_fin.assert_called_once()

    def test_build_enhancement_messages(self):
        """All task types produce valid message sequences."""
        botengine, organization, mut = self._setup()

        state = _build_analysis_state(phase=services.PHASE_ANALYSIS)
        state["params_data"] = _sample_params_content()
        mut._compile_and_analyze(botengine, state)

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        tasks = state["report"]["enhancement_tasks"]

        tested_types = set()
        for task in tasks:
            messages, max_tokens = mut._build_enhancement_messages(task)
            assert len(messages) >= 2
            assert messages[0]["role"] == "system"
            assert "CRITICAL" in messages[0]["content"]
            assert "Never invent" in messages[0]["content"]
            assert max_tokens > 0
            tested_types.add(task["task_type"])

        assert tested_types == {
            services.TASK_DEVICE_OVERVIEW,
            services.TASK_PARAMETER_INSIGHTS,
            services.TASK_RECOMMENDATIONS,
        }

        # Unknown task type should return empty
        msgs, tokens = mut._build_enhancement_messages(
            {"task_id": "x", "task_type": "unknown", "data": {}, "fields_to_fill": []}
        )
        assert msgs == [] and tokens == 0

    def test_parse_llm_text_response(self):
        """Parse labeled fields and fallback to entire content."""
        botengine, organization, mut = self._setup()

        # Labeled field
        r = mut._parse_llm_text_response(
            "overview_text: The overview.", ["overview_text"]
        )
        assert r["overview_text"] == "The overview."

        # Fallback to entire content for single field
        r = mut._parse_llm_text_response("No label here.", ["overview_text"])
        assert r["overview_text"] == "No label here."

        # Multiple fields
        r = mut._parse_llm_text_response(
            "field_a: Value A\nfield_b: Value B", ["field_a", "field_b"]
        )
        assert r["field_a"] == "Value A"
        assert r["field_b"] == "Value B"

    def test_finalize_report_emails_pdf(self):
        """Finalize should generate PDF and email."""
        botengine, organization, mut = self._setup()

        report = _build_report_with_stats()
        report["llm_results"] = {
            "task_device_overview": {"overview_text": "Overview text."},
            "task_parameter_insights": {"insights_text": "Insights."},
            "task_recommendations": {"recommendations_text": "Recommendations."},
        }

        # Set state so cleanup works
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS,
            {"report": report, "start_time": botengine.get_timestamp()},
            overwrite=True,
        )

        with (
            patch.object(botengine, "add_email_attachment") as mock_attach,
            patch.object(botengine, "email_admins") as mock_email,
        ):
            mut._finalize_report(botengine, report, botengine.get_timestamp())
            mock_attach.assert_called_once()
            assert mock_attach.call_args[1]["content_type"] == "application/pdf"
            mock_email.assert_called_once()
            assert mock_email.call_args[1]["email_html"] is True
            assert mock_email.call_args[1]["email_addresses"] == ["admin@example.com"]

        # State should be cleaned up
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

    def test_finalize_handles_import_error(self):
        """Missing fpdf2 should not crash."""
        botengine, organization, mut = self._setup()

        report = _build_report_with_stats()
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS,
            {"report": report, "start_time": botengine.get_timestamp()},
            overwrite=True,
        )

        with patch.dict("sys.modules", {"fpdf": None}):
            mut._finalize_report(botengine, report, botengine.get_timestamp())

        # State should still be cleaned up
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

    def test_cleanup(self):
        """Cleanup should clear state variable."""
        botengine, organization, mut = self._setup()
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, {"test": True}, overwrite=True
        )
        mut._cleanup(botengine)
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None


# ===========================================================================
# Report Builder Tests
# ===========================================================================
class TestReportBuilder:
    def test_compile_statistics(self):
        """Statistics should include device, parameter, and location breakdown."""
        config = _sample_config()
        devices_data = _sample_devices_data()
        params_data = _sample_params_content()

        stats = report_builder.compile_statistics(devices_data, params_data, config)

        assert "device_stats" in stats
        assert "parameter_stats" in stats
        assert "location_breakdown" in stats
        assert "summary" in stats

        # Device stats
        ds = stats["device_stats"]
        assert ds["total_devices"] == 4
        assert ds["total_locations"] == 3
        assert ds["by_type"]["10038"] == 3
        assert ds["by_type"]["10036"] == 1

        # Parameter stats
        ps = stats["parameter_stats"]
        assert "motionStatus" in ps
        assert "state" in ps
        assert (
            ps["motionStatus"]["sample_count"] == 8
        )  # dev_001(3) + dev_003(4) + dev_004(1)
        assert ps["motionStatus"]["min"] == 0.0
        assert ps["motionStatus"]["max"] == 1.0
        assert ps["state"]["sample_count"] == 2

        # Location breakdown
        lb = stats["location_breakdown"]
        assert len(lb) == 3
        assert lb["100"]["device_count"] == 2
        assert lb["200"]["device_count"] == 1

        # Summary
        assert stats["summary"]["total_devices"] == 4
        assert stats["summary"]["total_locations"] == 3

    def test_compile_statistics_empty_data(self):
        """Empty data should produce zero-count stats without errors."""
        config = _sample_config()
        empty_devices = {
            "devices_by_location": {},
            "device_ids": [],
            "total_devices": 0,
            "total_locations": 0,
        }
        stats = report_builder.compile_statistics(empty_devices, {}, config)

        assert stats["summary"]["total_devices"] == 0
        assert stats["summary"]["total_locations"] == 0
        assert stats["parameter_stats"]["motionStatus"]["sample_count"] == 0
        assert stats["parameter_stats"]["motionStatus"]["mean"] is None

    def test_compile_statistics_non_numeric_values(self):
        """Non-numeric parameter values should be skipped."""
        config = {"parameters": ["textParam"], "device_types": [1]}
        devices_data = {
            "devices_by_location": {
                "100": [{"device_id": "d1", "device_type": 1, "description": ""}]
            },
            "device_ids": ["d1"],
            "total_devices": 1,
            "total_locations": 1,
        }
        params_data = {
            "d1": {
                "textParam": [
                    {"value": "hello"},
                    {"value": "world"},
                    {"value": "42"},
                ],
            },
        }
        stats = report_builder.compile_statistics(devices_data, params_data, config)
        # Only "42" should be parsed as numeric
        assert stats["parameter_stats"]["textParam"]["sample_count"] == 1
        assert stats["parameter_stats"]["textParam"]["mean"] == 42.0

    def test_location_breakdown_param_highlights(self):
        """Location breakdown should include per-location parameter means."""
        config = _sample_config()
        devices_data = _sample_devices_data()
        params_data = _sample_params_content()

        stats = report_builder.compile_statistics(devices_data, params_data, config)
        lb = stats["location_breakdown"]

        # Location 100 has dev_001 (motionStatus: 1,0,1) and dev_002 (state: 1,0)
        assert "motionStatus" in lb["100"]["param_highlights"]
        assert "state" in lb["100"]["param_highlights"]

        # Location 200 has dev_003 (motionStatus: 1,1,0,1)
        assert "motionStatus" in lb["200"]["param_highlights"]
        assert lb["200"]["param_highlights"]["motionStatus"]["sample_count"] == 4

    def test_generate_pdf(self):
        """PDF generation should produce non-empty bytes."""
        report = _build_report_with_stats()
        report["llm_results"] = {
            "task_device_overview": {"overview_text": "Fleet overview text."},
            "task_parameter_insights": {"insights_text": "Insights text."},
            "task_recommendations": {
                "recommendations_text": "1. Do this.\n2. Do that."
            },
        }

        pdf_bytes = report_builder.generate_pdf(report, "Test Analysis", 1773550800000)

        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert len(pdf_bytes) > 100
        assert pdf_bytes[:5] == b"%PDF-"

    def test_generate_pdf_empty_data(self):
        """PDF should generate even with empty stats."""
        config = _sample_config()
        empty_devices = {
            "devices_by_location": {},
            "device_ids": [],
            "total_devices": 0,
            "total_locations": 0,
        }
        stats = report_builder.compile_statistics(empty_devices, {}, config)
        report = {
            "config": config,
            "stats": stats,
            "enhancement_tasks": [],
            "llm_results": {},
        }

        pdf_bytes = report_builder.generate_pdf(report, "Empty Analysis", 1773550800000)
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert pdf_bytes[:5] == b"%PDF-"

    def test_generate_pdf_with_unicode(self):
        """PDF should handle unicode characters in LLM text."""
        report = _build_report_with_stats()
        report["llm_results"] = {
            "task_device_overview": {
                "overview_text": "Fleet has \u201csmart\u201d sensors \u2014 performing well\u2026"
            },
        }

        pdf_bytes = report_builder.generate_pdf(report, "Unicode Test", 1773550800000)
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert len(pdf_bytes) > 100

    def test_generate_html_summary(self):
        """HTML summary should contain key data."""
        report = _build_report_with_stats()
        report["llm_results"] = {
            "task_device_overview": {"overview_text": "Fleet overview."},
            "task_recommendations": {"recommendations_text": "Do X."},
        }

        html = report_builder.generate_html_summary(report, "Test Analysis")

        assert "Test Analysis" in html
        assert "Fleet overview." in html
        assert "Do X." in html
        assert "Total Devices" in html
        assert "4" in html  # total devices

    def test_generate_html_summary_empty(self):
        """HTML summary with no LLM results should still produce valid HTML."""
        config = _sample_config()
        empty_devices = {
            "devices_by_location": {},
            "device_ids": [],
            "total_devices": 0,
            "total_locations": 0,
        }
        stats = report_builder.compile_statistics(empty_devices, {}, config)
        report = {
            "config": config,
            "stats": stats,
            "enhancement_tasks": [],
            "llm_results": {},
        }

        html = report_builder.generate_html_summary(report, "Empty")
        assert "<html>" in html
        assert "</html>" in html

    def test_fmt_num(self):
        """Number formatting helper."""
        assert report_builder._fmt_num(None) == "N/A"
        assert report_builder._fmt_num(42.0) == "42"
        assert report_builder._fmt_num(3.14159) == "3.14"
        assert report_builder._fmt_num(0) == "0"
        assert report_builder._fmt_num("text") == "text"

    def test_to_numeric(self):
        """Numeric conversion helper."""
        assert report_builder._to_numeric(42) == 42.0
        assert report_builder._to_numeric(3.14) == 3.14
        assert report_builder._to_numeric("99") == 99.0
        assert report_builder._to_numeric("hello") is None
        assert report_builder._to_numeric(None) is None
        assert report_builder._to_numeric([1, 2]) is None
