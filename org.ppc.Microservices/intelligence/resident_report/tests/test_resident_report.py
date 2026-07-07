"""
Created on May 5, 2026

@author: Destry Teeter

Unit tests for the resident_report organization microservice.
"""

from unittest.mock import patch

from intelligence.resident_report import report_builder, services
from organization.organization import Organization  # type: ignore

from botengine_pytest import BotEnginePyTest

# ===========================================================================
# Synthetic data fixtures
# ===========================================================================
_NOW_MS = 1746489600000
_DAY_MS = 24 * 60 * 60 * 1000


def _resident_report_dict(*, resident_name, location_name, wellness=None,
                          falls=0, journal=None, bathroom_count=0,
                          daily_summary=None, narratives=None):
    """Build a minimal per-location resident_report dict matching the shape
    persisted by location_reports_resident_microservice._save_resident_report."""
    falls_data = [
        {
            "description": f"Fall detected at 09:00, lasting 12s ({i})",
            "device_desc": "Bedroom",
            "end_time_ms": _NOW_MS,
            "duration_ms": 12000,
        }
        for i in range(falls)
    ]
    return {
        "timestamp_ms": _NOW_MS,
        "resident_name": resident_name,
        "location_name": location_name,
        "report_date": "May 05, 2026",
        "dashboard_header": "Daily Resident Report",
        "dashboard_status": "OK",
        "wellness_data": {
            "score": wellness,
            "delta": 0,
            "categories": {
                key: {"value": wellness, "delta": 0, "display": str(wellness),
                      "zscore": 0, "avg": wellness}
                for key, _label in services.SCORE_CATEGORIES
            },
        } if wellness is not None else {},
        "journal_summary": journal,
        "falls_data": falls_data,
        "bathroom_data": (
            {"count": bathroom_count,
             "description": f"{bathroom_count} night bathroom visits"}
            if bathroom_count else {}
        ),
        "score_history": {
            "dates": ["05/05", "05/04", "05/03"],
            "summary": [
                {"date": "05/05", "value": wellness or 0},
                {"date": "05/04", "value": (wellness or 0) - 1},
                {"date": "05/03", "value": (wellness or 0) - 2},
            ],
        },
        "highlights_data": None,
        "daily_report": {"summary": daily_summary} if daily_summary else {},
        "narratives": narratives or [],
    }


def _build_data_request_content():
    """Mimic botengine.request_data() response for three locations."""
    healthy = _resident_report_dict(
        resident_name="Alice", location_name="Maple 101",
        wellness=82, journal="Quiet day, well-rested.", bathroom_count=1,
        daily_summary="Yesterday Alice slept well and stayed active.",
    )
    low_wellness = _resident_report_dict(
        resident_name="Bob", location_name="Maple 102",
        wellness=44, journal="Reduced activity, low energy.", bathroom_count=3,
        narratives=[
            {"narrative_id": 201, "priority": 3,
             "title": "Critical heart rate", "description": "Elevated overnight"},
            {"narrative_id": 202, "priority": 2,
             "title": "Broadband warning", "description": "Connectivity blip"},
        ],
    )
    with_fall = _resident_report_dict(
        resident_name="Carol", location_name="Maple 103",
        wellness=65, journal="Reported feeling unsteady this morning.",
        falls=1, bathroom_count=2,
        daily_summary="Yesterday Carol was unsteady on her feet.",
        narratives=[
            {"narrative_id": 203, "priority": 3,
             "title": "Fall detected", "description": "Bathroom, 12s"},
        ],
    )
    # Per-location state is a dict {timestamp_ms: report_dict}
    return {
        "100": {services.STATE_RESIDENT_REPORT: {
            _NOW_MS - _DAY_MS: {**healthy, "wellness_data": {"score": 80}},
            _NOW_MS: healthy,
        }},
        "101": {services.STATE_RESIDENT_REPORT: {_NOW_MS: low_wellness}},
        "102": {services.STATE_RESIDENT_REPORT: {_NOW_MS: with_fall}},
    }


# ===========================================================================
# report_builder pure-function tests
# ===========================================================================
class TestReportBuilder:
    def test_latest_report_per_location_picks_most_recent(self):
        content = _build_data_request_content()
        latest = report_builder.latest_report_per_location(content)
        assert set(latest.keys()) == {"100", "101", "102"}
        # location 100 has two snapshots; the most recent (NOW_MS) wins
        assert latest["100"]["wellness_data"]["score"] == 82

    def test_latest_handles_missing_or_empty(self):
        assert report_builder.latest_report_per_location({}) == {}
        assert report_builder.latest_report_per_location({"5": {}}) == {}
        assert report_builder.latest_report_per_location(
            {"5": {services.STATE_RESIDENT_REPORT: {}}}
        ) == {}

    def test_skeleton_sorts_falls_first(self):
        latest = report_builder.latest_report_per_location(
            _build_data_request_content()
        )
        skeleton = report_builder.build_report_skeleton(
            latest, organization_name="Maple Grove",
            timestamp_ms=_NOW_MS, disable_llm=False,
        )
        residents = skeleton["section2_residents"]
        # Carol has the fall -> first
        assert residents[0]["resident_name"] == "Carol"
        # Bob has wellness 44 -> second
        assert residents[1]["resident_name"] == "Bob"
        # Alice (wellness 82, no falls) -> last
        assert residents[2]["resident_name"] == "Alice"

    def test_skeleton_metadata_counts(self):
        latest = report_builder.latest_report_per_location(
            _build_data_request_content()
        )
        skeleton = report_builder.build_report_skeleton(
            latest, organization_name="Maple Grove",
            timestamp_ms=_NOW_MS, disable_llm=False,
        )
        meta = skeleton["metadata"]
        assert meta["total_residents"] == 3
        assert meta["with_falls"] == 1
        assert meta["total_falls"] == 1
        assert meta["with_low_wellness"] == 1  # Bob @ 44
        assert meta["with_journal"] == 3
        # avg of 82, 44, 65 = 63.67 -> rounded to 63.7
        assert meta["avg_wellness_score"] == 63.7
        assert meta["night_bathroom_total"] == 6  # 1 + 3 + 2
        # Bob (2) + Carol (1) have narratives
        assert meta["with_critical_events"] == 2
        assert meta["total_critical_events"] == 3

    def test_disable_llm_emits_no_enhancement_tasks(self):
        latest = report_builder.latest_report_per_location(
            _build_data_request_content()
        )
        skeleton = report_builder.build_report_skeleton(
            latest, organization_name="Maple Grove",
            timestamp_ms=_NOW_MS, disable_llm=True,
        )
        assert skeleton["enhancement_tasks"] == []

    def test_executive_summary_messages_anonymized(self):
        latest = report_builder.latest_report_per_location(
            _build_data_request_content()
        )
        skeleton = report_builder.build_report_skeleton(
            latest, organization_name="Maple Grove",
            timestamp_ms=_NOW_MS, disable_llm=False,
        )
        task = skeleton["enhancement_tasks"][0]
        messages, max_tokens = report_builder.build_executive_summary_messages(
            task["data"]
        )
        assert max_tokens == services.LLM_MAX_TOKENS_SUMMARY
        assert messages[0]["role"] == "system"
        # No resident names should leak through to the prompt
        for msg in messages:
            assert "Alice" not in msg["content"]
            assert "Bob" not in msg["content"]
            assert "Carol" not in msg["content"]

    def test_apply_llm_enhancement_writes_overview(self):
        latest = report_builder.latest_report_per_location(
            _build_data_request_content()
        )
        skeleton = report_builder.build_report_skeleton(
            latest, organization_name="Maple Grove",
            timestamp_ms=_NOW_MS, disable_llm=False,
        )
        report_builder.apply_llm_enhancement(
            skeleton,
            services.TASK_EXECUTIVE_SUMMARY,
            {"overview_text": "Test summary."},
        )
        assert skeleton["section1_overview"]["overview_text"] == "Test summary."


# ===========================================================================
# Microservice integration tests
# ===========================================================================
class TestResidentReportMicroservice:
    def _setup(self):
        botengine = BotEnginePyTest({})
        botengine.reset()
        botengine.logging_service_names = ["resident_report"]
        organization = Organization(botengine, 0)
        organization.new_version(botengine)
        organization.initialize(botengine)
        mut = organization.intelligence_modules[
            "intelligence.resident_report.organization_resident_report_microservice"
        ]
        return botengine, organization, mut

    def test_initialization(self):
        botengine, organization, mut = self._setup()
        assert mut is not None
        mut.new_version(botengine)

    def test_data_request_and_skeleton(self):
        botengine, organization, mut = self._setup()

        with patch.object(botengine, "request_data") as mock_rd:
            mut._request_resident_data(botengine)
            mock_rd.assert_called_once()
            kwargs = mock_rd.call_args[1]
            assert kwargs["reference"] == services.DATA_REQUEST_REFERENCE_RESIDENT
            assert kwargs["names"] == [services.STATE_RESIDENT_REPORT]

        # Async response with real data should build a skeleton
        content = _build_data_request_content()
        mut.async_data_request_ready(
            botengine, services.DATA_REQUEST_REFERENCE_RESIDENT, content
        )
        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        assert state is not None
        assert state["ready_for_processing"] is True
        assert len(state["report"]["section2_residents"]) == 3

        # Empty content should NOT save a report
        botengine.save_variable(
            services.STATE_VAR_REPORT_IN_PROGRESS, None, overwrite=True
        )
        mut.async_data_request_ready(
            botengine, services.DATA_REQUEST_REFERENCE_RESIDENT,
            {"100": {services.STATE_RESIDENT_REPORT: {}}},
        )
        assert botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS) is None

        # Wrong reference should be ignored
        mut.async_data_request_ready(botengine, "some_other_reference", {})
        assert botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS) is None

    def test_timer_bridge_retries_and_finalizes(self):
        botengine, organization, mut = self._setup()

        # Non-dict argument is ignored
        mut.timer_fired(botengine, "not_a_dict")

        # No data yet -> retry with incremented count
        with patch.object(mut, "start_timer_s") as mock_timer:
            mut.timer_fired(
                botengine,
                {"type": "data_request_timeout", "retry_count": 0},
            )
            mock_timer.assert_called_once()
            assert mock_timer.call_args[1]["argument"]["retry_count"] == 1

        # Max retries -> give up (no new timer)
        with patch.object(mut, "start_timer_s") as mock_timer:
            mut.timer_fired(botengine, {
                "type": "data_request_timeout",
                "retry_count": services.MAX_DATA_REQUEST_RETRIES,
            })
            mock_timer.assert_not_called()

        # Ready skeleton + LLM enabled -> kicks off executive summary task
        latest = report_builder.latest_report_per_location(
            _build_data_request_content()
        )
        skeleton = report_builder.build_report_skeleton(
            latest, "Maple Grove", _NOW_MS, disable_llm=False
        )
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, {
            "report": skeleton,
            "tasks_remaining": len(skeleton["enhancement_tasks"]),
            "tasks_completed": 0,
            "start_time": botengine.get_timestamp(),
            "ready_for_processing": True,
            "disable_llm": False,
        }, overwrite=True)
        with patch.object(mut, "_process_executive_summary_task") as mock_task:
            mut.timer_fired(
                botengine,
                {"type": "data_request_timeout", "retry_count": 0},
            )
            mock_task.assert_called_once()

        # Ready skeleton + disable_llm=True -> finalize directly
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, {
            "report": skeleton,
            "tasks_remaining": 0,
            "tasks_completed": 0,
            "start_time": botengine.get_timestamp(),
            "ready_for_processing": True,
            "disable_llm": True,
        }, overwrite=True)
        with patch.object(mut, "_finalize_report") as mock_final, \
             patch.object(mut, "_process_executive_summary_task") as mock_task:
            mut.timer_fired(
                botengine,
                {"type": "data_request_timeout", "retry_count": 0},
            )
            mock_final.assert_called_once()
            mock_task.assert_not_called()

    def test_llm_response_routes_and_finalizes(self):
        botengine, organization, mut = self._setup()

        # Wrong reference -> handler not called
        with patch.object(mut, "_handle_executive_summary_response") as mock_h:
            mut.llm_response(botengine, {}, "unknown_ref", {})
            mock_h.assert_not_called()

        latest = report_builder.latest_report_per_location(
            _build_data_request_content()
        )
        skeleton = report_builder.build_report_skeleton(
            latest, "Maple Grove", _NOW_MS, disable_llm=False
        )
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, {
            "report": skeleton,
            "tasks_remaining": 1,
            "tasks_completed": 0,
            "start_time": botengine.get_timestamp(),
            "ready_for_processing": False,
            "disable_llm": False,
        }, overwrite=True)

        # Real LLM response -> writes overview text and finalizes
        with patch.object(mut, "_finalize_report") as mock_final:
            mut.llm_response(
                botengine,
                {"choices": [{"message": {
                    "content": "overview_text: All looks well today.",
                }}]},
                services.LLM_REFERENCE_RESIDENT_REPORT,
                {"task_id": services.TASK_EXECUTIVE_SUMMARY,
                 "task_type": services.TASK_EXECUTIVE_SUMMARY,
                 "fields_to_fill": ["overview_text"]},
            )
            mock_final.assert_called_once()
        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        assert (state["report"]["section1_overview"]["overview_text"]
                == "All looks well today.")

    def test_pdf_generation_does_not_raise(self):
        """End-to-end smoke: a non-empty PDF byte stream is produced and
        emailed without exceptions when LLM is disabled."""
        botengine, organization, mut = self._setup()


        latest = report_builder.latest_report_per_location(
            _build_data_request_content()
        )
        report = report_builder.build_report_skeleton(
            latest, "Maple Grove", _NOW_MS, disable_llm=True,
        )

        captured = {}
        def capture_attachment(*, destination_attachment_array, filename,
                               content, content_type, content_id):
            destination_attachment_array.append({"filename": filename,
                                                 "content": content})
            captured["filename"] = filename
            captured["content_b64"] = content

        with patch.object(botengine, "add_email_attachment",
                          side_effect=capture_attachment), \
             patch.object(botengine, "email_admins") as mock_email:
            mut._generate_and_email_pdf(botengine, report)
            mock_email.assert_called_once()
            assert captured.get("filename") == "Resident_Report_Organization.pdf"
            assert captured.get("content_b64")
            assert len(captured["content_b64"]) > 100
            kwargs = mock_email.call_args.kwargs
            assert kwargs["email_html"] is True
            html_body = kwargs["email_content"]
            assert "<table" in html_body
            assert "Resident Roster" in html_body
            assert "Maple 101" in html_body  # Alice's location
            assert "Maple 103" in html_body  # Carol's location
            # Critical row (Carol has fall) should use the critical fill color
            assert "#FFE0E0" in html_body
            # Critical-events rollup stat and per-resident marker are present
            assert "Total Critical Events" in html_body
            assert "critical event(s)" in html_body
            # Daily report summary surfaces in the roster status (Alice has no
            # narratives, so her daily summary is used as the status text)
            assert "Yesterday Alice slept well" in html_body
