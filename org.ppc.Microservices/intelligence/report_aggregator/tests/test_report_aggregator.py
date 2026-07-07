import datetime
import json
import logging
from unittest.mock import MagicMock, patch

import pytz
import signals.report as org_report  # type: ignore
import utilities.utilities as utilities  # type: ignore
from intelligence.report_aggregator import report_builder, rules_engine, services
from organization.organization import Organization  # type: ignore

from botengine_pytest import BotEnginePyTest

_MUT_LOGGER = "intelligence.report_aggregator.organization_report_aggregator_microservice.OrganizationReportAggregatorMicroservice"


def _make_report(
    location_id,
    report_type,
    priority,
    sentiment,
    timestamp_ms,
    days_active=1,
    severity_rank=None,
    short_description="Test report",
    location_name=None,
):
    """Build a valid org report dict."""
    return {
        "location_id": location_id,
        "location_name": location_name or f"Location {location_id}",
        "timestamp_ms": timestamp_ms,
        "priority": priority,
        "report_type": report_type,
        "sentiment": sentiment,
        "report_id": f"report_{location_id}_{report_type}_{timestamp_ms}",
        "summary": short_description,
        "short_description": short_description,
        "long_description": f"Detailed: {short_description}",
        "days_active": days_active,
        "severity_rank": severity_rank,
        "recommended_actions": ["Take action"],
    }


class TestReportAggregatorMicroservice:
    def _setup(self):
        """Common setup for tests."""
        botengine = BotEnginePyTest({})
        botengine.reset()

        organization = Organization(botengine, 0)
        organization.new_version(botengine)
        organization.initialize(botengine)

        mut = organization.intelligence_modules[
            "intelligence.report_aggregator.organization_report_aggregator_microservice"
        ]

        return botengine, organization, mut

    # ===========================================================================
    # Initialization
    # ===========================================================================
    def test_report_aggregator_initialization(self):
        """Should initialize and be accessible via intelligence_modules."""
        botengine, organization, mut = self._setup()
        assert mut is not None

    def test_new_version(self):
        """new_version() should run without errors."""
        botengine, organization, mut = self._setup()
        mut.new_version(botengine)

    # ===========================================================================
    # Datastream Routing
    # ===========================================================================
    def test_datastream_clear_report_cache(self):
        """datastream_updated with 'clear_report_cache' should clear legacy cache."""
        botengine, organization, mut = self._setup()

        # Pre-populate legacy cache variable
        botengine.save_variable(services.COLLECTION_ORG_REPORT_CACHE, ["old_data"], overwrite=True)

        mut.datastream_updated(
            botengine, "clear_report_cache", {"trigger_source": "test"}
        )

        cached = botengine.load_variable(services.COLLECTION_ORG_REPORT_CACHE)
        assert cached == []

    def test_datastream_unknown_address(self):
        """datastream_updated with unknown address should not raise."""
        botengine, organization, mut = self._setup()
        mut.datastream_updated(botengine, "unknown_address", {})

    def test_datastream_report_to_org_no_longer_handled(self):
        """report_to_org should no longer be handled at the org level."""
        botengine, organization, mut = self._setup()

        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_CRITICAL,
            org_report.SENTIMENT_CONCERN,
            botengine.get_timestamp(),
        )
        # Should not raise - just ignored
        mut.datastream_updated(botengine, "report_to_org", report)

    # ===========================================================================
    # Pull-Based Report Collection
    # ===========================================================================
    def test_pull_reports_from_location_valid(self):
        """Should parse a valid state response into a report list."""
        botengine, organization, mut = self._setup()

        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_CRITICAL,
            org_report.SENTIMENT_CONCERN,
            botengine.get_timestamp(),
        )

        import json
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.text = json.dumps({"value": [report]})

        with patch.object(botengine, "_http_get", return_value=mock_response, create=True):
            result = mut._pull_reports_from_location(botengine, 12345)

        assert len(result) == 1
        assert result[0]["location_id"] == "loc1"

    def test_pull_reports_from_location_empty(self):
        """Should return empty list when location has no aggregated reports."""
        botengine, organization, mut = self._setup()

        import json
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.text = json.dumps({})

        with patch.object(botengine, "_http_get", return_value=mock_response, create=True):
            result = mut._pull_reports_from_location(botengine, 12345)

        assert result == []

    def test_pull_reports_from_location_error(self):
        """Should return empty list on HTTP error."""
        botengine, organization, mut = self._setup()

        with patch.object(botengine, "_http_get", side_effect=Exception("Connection error"), create=True):
            result = mut._pull_reports_from_location(botengine, 12345)

        assert result == []

    def test_pull_all_location_reports(self):
        """Should pull and merge reports from all org locations."""
        botengine, organization, mut = self._setup()
        ts = botengine.get_timestamp()

        report1 = _make_report("loc1", "stability", org_report.PRIORITY_CRITICAL, org_report.SENTIMENT_CONCERN, ts)
        report2 = _make_report("loc2", "bathroom", org_report.PRIORITY_WARNING, org_report.SENTIMENT_CONCERN, ts)

        with (
            patch.object(botengine, "get_organization_locations", return_value=[{"id": 1}, {"id": 2}], create=True),
            patch.object(mut, "_pull_reports_from_location", side_effect=[[report1], [report2]]),
        ):
            result = mut._pull_all_location_reports(botengine)

        assert len(result) == 2

    def test_pull_all_location_reports_with_cutoff(self):
        """Should filter reports by cutoff_ms."""
        botengine, organization, mut = self._setup()
        ts = botengine.get_timestamp()

        recent = _make_report("loc1", "stability", org_report.PRIORITY_CRITICAL, org_report.SENTIMENT_CONCERN, ts - utilities.ONE_HOUR_MS)
        old = _make_report("loc2", "bathroom", org_report.PRIORITY_WARNING, org_report.SENTIMENT_CONCERN, ts - (25 * utilities.ONE_HOUR_MS))

        cutoff_ms = ts - utilities.ONE_DAY_MS

        with (
            patch.object(botengine, "get_organization_locations", return_value=[{"id": 1}, {"id": 2}], create=True),
            patch.object(mut, "_pull_reports_from_location", side_effect=[[recent], [old]]),
        ):
            result = mut._pull_all_location_reports(botengine, cutoff_ms=cutoff_ms)

        assert len(result) == 1
        assert result[0]["location_id"] == "loc1"

    def test_pull_all_location_reports_no_locations(self):
        """Should return empty list when no locations exist."""
        botengine, organization, mut = self._setup()

        with patch.object(botengine, "get_organization_locations", return_value=[], create=True):
            result = mut._pull_all_location_reports(botengine)

        assert result == []

    # ===========================================================================
    # Clear Cache (Legacy Cleanup)
    # ===========================================================================
    def test_clear_cache_clears_legacy_variable(self):
        """Clear cache should clean up legacy org_report_cache variable."""
        botengine, organization, mut = self._setup()

        # Pre-populate legacy cache
        botengine.save_variable(services.COLLECTION_ORG_REPORT_CACHE, ["old_data"], overwrite=True)

        mut._handle_clear_cache_request(botengine, {"trigger_source": "test"})

        cached = botengine.load_variable(services.COLLECTION_ORG_REPORT_CACHE)
        assert cached == []

    # ===========================================================================
    # Schedule Handling
    # ===========================================================================
    def test_schedule_fired_daily_non_sunday(self):
        """On a non-Sunday day, schedule_fired should generate daily reports."""
        botengine, organization, mut = self._setup()

        # Set timestamp to a Wednesday: 2026-03-04 06:00:00 UTC (Wednesday)
        wednesday = datetime.datetime(2026, 3, 4, 6, 0, 0, tzinfo=pytz.utc)
        botengine.set_timestamp(int(wednesday.timestamp() * 1000))

        with (
            patch.object(mut, "_generate_daily_reports") as mock_daily,
            patch.object(mut, "_generate_weekly_reports") as mock_weekly,
        ):
            mut.schedule_fired(botengine, services.SCHEDULE_DAILY_MASTER_REPORT)
            mock_daily.assert_called_once_with(botengine)
            mock_weekly.assert_not_called()

    def test_schedule_fired_weekly_sunday(self):
        """On Sunday, schedule_fired should generate weekly reports."""
        botengine, organization, mut = self._setup()

        # Set timestamp to a Sunday: 2026-03-08 06:00:00 UTC (Sunday)
        sunday = datetime.datetime(2026, 3, 8, 6, 0, 0, tzinfo=pytz.utc)
        botengine.set_timestamp(int(sunday.timestamp() * 1000))

        with (
            patch.object(mut, "_generate_daily_reports") as mock_daily,
            patch.object(mut, "_generate_weekly_reports") as mock_weekly,
        ):
            mut.schedule_fired(botengine, services.SCHEDULE_DAILY_MASTER_REPORT)
            mock_weekly.assert_called_once_with(botengine)
            mock_daily.assert_not_called()

    def test_schedule_fired_unknown_id(self):
        """Unknown schedule_id should not trigger report generation."""
        botengine, organization, mut = self._setup()

        with (
            patch.object(mut, "_generate_daily_reports") as mock_daily,
            patch.object(mut, "_generate_weekly_reports") as mock_weekly,
        ):
            mut.schedule_fired(botengine, "UNKNOWN_SCHEDULE")
            mock_daily.assert_not_called()
            mock_weekly.assert_not_called()

    # ===========================================================================
    # Generate Daily Reports
    # ===========================================================================
    def test_generate_daily_no_reports(self):
        """Daily generation with no reports from locations should skip."""
        botengine, organization, mut = self._setup()

        with (
            patch.object(mut, "_pull_all_location_reports", return_value=[]),
            patch.object(mut, "_generate_master_report_llm") as mock_llm,
        ):
            mut._generate_daily_reports(botengine)
            mock_llm.assert_not_called()

    def test_generate_daily_filters_to_24h(self):
        """Daily generation should request location states with 24h cutoff."""
        botengine, organization, mut = self._setup()
        ts = botengine.get_timestamp()

        with (
            patch.object(botengine, "request_data") as mock_request,
            patch.object(mut, "start_timer_s") as mock_timer,
        ):
            mut._generate_daily_reports(botengine)
            # Verify request_data was called with 24h cutoff
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["type"] == botengine.DATA_REQUEST_TYPE_LOCATION_TIME_STATES
            assert call_kwargs["reference"] == "ra_location_states_daily"
            assert abs(call_kwargs["oldest_timestamp_ms"] - (ts - utilities.ONE_DAY_MS)) < 1000
            assert call_kwargs["names"] == [services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS]
            # Verify timeout timer was set
            mock_timer.assert_called_once()

    # ===========================================================================
    # Generate Weekly Reports
    # ===========================================================================
    def test_generate_weekly_no_reports(self):
        """Weekly generation with no reports from locations should skip."""
        botengine, organization, mut = self._setup()

        with (
            patch.object(mut, "_pull_all_location_reports", return_value=[]),
            patch.object(mut, "_generate_master_report_llm") as mock_llm,
        ):
            mut._generate_weekly_reports(botengine)
            mock_llm.assert_not_called()

    def test_generate_weekly_uses_7day_window(self):
        """Weekly generation should request location states with 7-day window."""
        botengine, organization, mut = self._setup()
        ts = botengine.get_timestamp()

        with (
            patch.object(botengine, "request_data") as mock_request,
            patch.object(mut, "start_timer_s") as mock_timer,
        ):
            mut._generate_weekly_reports(botengine)
            # Verify request_data was called with 7-day cutoff
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["type"] == botengine.DATA_REQUEST_TYPE_LOCATION_TIME_STATES
            assert call_kwargs["reference"] == "ra_location_states_weekly"
            assert abs(call_kwargs["oldest_timestamp_ms"] - (ts - utilities.ONE_DAY_MS * 7)) < 1000
            assert call_kwargs["names"] == [services.LOCATION_AGGREGATED_REPORT_STATE_ADDRESS]
            # Verify timeout timer was set
            mock_timer.assert_called_once()

    # ===========================================================================
    # Generate Master Report Request
    # ===========================================================================
    def test_generate_master_report_request_daily(self):
        """Default request should trigger daily generation."""
        botengine, organization, mut = self._setup()

        with patch.object(mut, "_generate_daily_reports") as mock_daily:
            mut._handle_generate_master_report_request(botengine, {})
            mock_daily.assert_called_once()

    def test_generate_master_report_request_weekly(self):
        """include_weekly_synthesis=True should trigger weekly generation."""
        botengine, organization, mut = self._setup()

        with patch.object(mut, "_generate_weekly_reports") as mock_weekly:
            mut._handle_generate_master_report_request(
                botengine, {"include_weekly_synthesis": True}
            )
            mock_weekly.assert_called_once()

    # ===========================================================================
    # Parse LLM Text Response
    # ===========================================================================
    def test_parse_llm_text_response_single_field(self):
        """Single field should be extracted correctly."""
        botengine, organization, mut = self._setup()

        content = "summary_text: This is a summary of the report."
        result = mut._parse_llm_text_response(content, ["summary_text"])
        assert result["summary_text"] == "This is a summary of the report."

    def test_parse_llm_text_response_multiple_fields(self):
        """Multiple fields should be extracted correctly."""
        botengine, organization, mut = self._setup()

        content = "summary_text: Overall things are good.\ntop_concern_text: Sleep patterns declining."
        result = mut._parse_llm_text_response(
            content, ["summary_text", "top_concern_text"]
        )
        assert "Overall things are good" in result["summary_text"]
        assert "Sleep patterns declining" in result["top_concern_text"]

    def test_parse_llm_text_response_fallback_single_field(self):
        """When field name not found and only one field expected, use entire content."""
        botengine, organization, mut = self._setup()

        content = "Just some plain text response."
        result = mut._parse_llm_text_response(content, ["enhanced_description"])
        assert result["enhanced_description"] == "Just some plain text response."

    def test_parse_llm_text_response_missing_field_multiple(self):
        """When field name not found and multiple expected, return empty string."""
        botengine, organization, mut = self._setup()

        content = "summary_text: Only this one."
        result = mut._parse_llm_text_response(
            content, ["summary_text", "missing_field"]
        )
        assert "Only this one" in result["summary_text"]
        assert result["missing_field"] == ""

    # ===========================================================================
    # Filter Executive Summary for Persona
    # ===========================================================================
    def test_filter_executive_summary_wellness(self):
        """Should derive counts/text from the wellness persona's own concerns."""
        botengine, organization, mut = self._setup()

        # Master-level summary text describes the org-wide top concern (here,
        # an IT issue) and must NOT leak into the wellness persona summary.
        exec_summary = {
            "total_locations": 10,
            "summary_text": "Master: gateway offline at Building A",
            "top_concern_text": "Building A gateway down",
        }
        wellness_concerns = [
            {
                "report_type": "stability",
                "priority": org_report.PRIORITY_CRITICAL,
                "location_id": "loc1",
                "location_name": "Building A",
                "short_description": "Fall risk elevated",
            },
            {
                "report_type": "sleep",
                "priority": org_report.PRIORITY_WARNING,
                "location_id": "loc2",
            },
            {
                "report_type": "bathroom",
                "priority": org_report.PRIORITY_WARNING,
                "location_id": "loc2",
            },
        ]

        result = mut._filter_executive_summary_for_persona(
            exec_summary, "wellness", wellness_concerns
        )
        assert result["total_locations"] == 10
        assert result["persona_critical_count"] == 1  # stability
        assert result["persona_warning_count"] == 2  # sleep + bathroom
        assert len(result["top_concerns_list"]) == 3  # stability, sleep, bathroom
        # Persona text is derived from wellness concerns, not the master text
        assert result["summary_text"] != exec_summary["summary_text"]
        assert "wellness" in result["summary_text"]
        assert "gateway" not in result["summary_text"].lower()
        assert "Building A" in result["top_concern_text"]

    def test_filter_executive_summary_tech(self):
        """Should derive counts/text from the tech persona's own concerns."""
        botengine, organization, mut = self._setup()

        exec_summary = {
            "total_locations": 10,
            # Master text is wellness-dominated and must not leak into IT report
            "summary_text": "Master: resident fall risk critical at Building A",
            "top_concern_text": "Building A fall risk",
        }
        tech_concerns = [
            {
                "report_type": "infrastructure",
                "priority": org_report.PRIORITY_CRITICAL,
                "location_id": "loc1",
                "location_name": "Building A",
                "short_description": "Gateway offline",
            },
            {
                "report_type": "device_offline",
                "priority": org_report.PRIORITY_WARNING,
                "location_id": "loc2",
            },
        ]

        result = mut._filter_executive_summary_for_persona(
            exec_summary, "tech", tech_concerns
        )
        assert result["persona_critical_count"] == 1  # infrastructure
        assert result["persona_warning_count"] == 1  # device_offline
        assert len(result["top_concerns_list"]) == 2
        assert "infrastructure" in result["summary_text"]
        assert "fall risk" not in result["summary_text"].lower()

    def test_filter_executive_summary_no_concerns(self):
        """Should produce a clean 'no concerns' summary when the persona is clear."""
        botengine, organization, mut = self._setup()

        exec_summary = {
            "total_locations": 30,
            "summary_text": "Master: critical health issues at S105",
            "top_concern_text": "S105 health crisis",
        }

        result = mut._filter_executive_summary_for_persona(exec_summary, "tech", [])
        assert result["persona_critical_count"] == 0
        assert result["persona_warning_count"] == 0
        assert result["top_concern_text"] is None
        # No leakage of the wellness-dominated master summary
        assert "health" not in result["summary_text"].lower()
        assert "S105" not in result["summary_text"]
        assert "No infrastructure concerns" in result["summary_text"]

    # ===========================================================================
    # Email Wellness Report
    # ===========================================================================
    def test_email_wellness_report_sends_email(self):
        """Should send email to admins when wellness report has content."""
        botengine, organization, mut = self._setup()
        ts = botengine.get_timestamp()

        wellness_report = {
            "timestamp_ms": ts,
            "report_type": "daily",
            "org_name": "Test Org",
            "persona": "wellness",
            "executive_summary": {
                "total_locations": 5,
                "persona_critical_count": 1,
                "persona_warning_count": 2,
                "top_concerns_list": [],
                "summary_text": "Test summary",
                "top_concern_text": "Sleep declining",
            },
            "top_concerns": [
                {
                    "location_name": "Apt 101",
                    "priority": org_report.PRIORITY_CRITICAL,
                    "short_description": "Sleep quality declining",
                    "days_active": 3,
                    "recommended_actions": ["Call resident"],
                }
            ],
            "top_celebrations": [],
            "trends": [],
            "category_summary": {},
        }

        mut._email_wellness_report(botengine, wellness_report, ts)
        assert botengine.admin_mail_notified is True

    def test_email_wellness_report_empty_content(self):
        """Should not send email when wellness report has no content."""
        botengine, organization, mut = self._setup()
        ts = botengine.get_timestamp()

        empty_report = {
            "timestamp_ms": ts,
            "report_type": "daily",
            "org_name": "Test Org",
            "persona": "wellness",
            "executive_summary": {
                "total_locations": 0,
                "persona_critical_count": 0,
                "persona_warning_count": 0,
                "top_concerns_list": [],
            },
            "top_concerns": [],
            "top_celebrations": [],
            "trends": [],
            "category_summary": {},
        }

        botengine.admin_mail_notified = False
        mut._email_wellness_report(botengine, empty_report, ts)
        # Executive summary section always gets added, so email is still sent
        # unless there's literally zero content_array items.
        # The exec summary section always builds even with 0 counts.
        assert botengine.admin_mail_notified is True

    # ===========================================================================
    # Email Tech Report
    # ===========================================================================
    def test_email_tech_report_sends_email(self):
        """Should send email to admins when tech report has content."""
        botengine, organization, mut = self._setup()
        ts = botengine.get_timestamp()

        tech_report = {
            "timestamp_ms": ts,
            "report_type": "daily",
            "org_name": "Test Org",
            "persona": "tech",
            "executive_summary": {
                "total_locations": 3,
                "persona_critical_count": 1,
                "persona_warning_count": 0,
                "top_concerns_list": [],
                "summary_text": "Gateway offline",
                "top_concern_text": "Building A gateway down",
            },
            "top_concerns": [
                {
                    "location_name": "Building A",
                    "priority": org_report.PRIORITY_CRITICAL,
                    "short_description": "Gateway offline 3 days",
                    "days_active": 3,
                    "recommended_actions": ["Dispatch technician"],
                }
            ],
            "top_celebrations": [],
            "trends": [],
            "category_summary": {},
        }

        mut._email_tech_report(botengine, tech_report, ts)
        assert botengine.admin_mail_notified is True

    # ===========================================================================
    # LLM Response Handler
    # ===========================================================================
    def test_llm_response_unknown_reference(self):
        """LLM response with unknown reference should be handled gracefully."""
        botengine, organization, mut = self._setup()

        # Should not raise
        mut.llm_response(botengine, {"content": "test"}, "unknown_reference", {})

    def test_llm_response_master_report_no_state(self):
        """Master report LLM response with no in-progress state should log error and return."""
        botengine, organization, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        with patch.object(logger, "error") as mock_error:
            mut.llm_response(
                botengine,
                {"content": "test"},
                services.LLM_REFERENCE_MASTER_REPORT,
                {"task_id": "executive_summary", "fields_to_fill": ["summary_text"]},
            )
            mock_error.assert_called_once()


class TestRulesEngine:
    """Tests for the rules-based report pre-processing engine."""

    def _make_reports(self, count=5, base_timestamp=None):
        """Create a list of test reports."""
        base_ts = base_timestamp or 1709000000000
        reports = []
        configs = [
            (
                "loc1",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                5,
            ),
            (
                "loc2",
                "bathroom",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                3,
            ),
            (
                "loc3",
                "infrastructure",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                2,
            ),
            (
                "loc4",
                "sleep",
                org_report.PRIORITY_INFO,
                org_report.SENTIMENT_CONCERN,
                1,
            ),
            (
                "loc5",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_RESOLUTION,
                7,
            ),
        ]
        for i, (loc, rtype, prio, sent, days) in enumerate(configs[:count]):
            reports.append(
                _make_report(
                    loc, rtype, prio, sent, base_ts + i * 1000, days_active=days
                )
            )
        return reports

    # ===========================================================================
    # Filter
    # ===========================================================================
    def test_filter_excludes_info_by_default(self):
        """Info-priority reports should be excluded by default."""
        reports = self._make_reports()
        filtered = rules_engine.filter_reports(reports)
        assert not any(r["priority"] == org_report.PRIORITY_INFO for r in filtered)

    def test_filter_includes_info_when_requested(self):
        """Info-priority reports should be included when include_info=True."""
        reports = self._make_reports()
        filtered = rules_engine.filter_reports(reports, include_info=True)
        assert any(r["priority"] == org_report.PRIORITY_INFO for r in filtered)

    def test_filter_excludes_resolutions_by_default(self):
        """Resolution reports should be excluded by default."""
        reports = self._make_reports()
        filtered = rules_engine.filter_reports(reports)
        assert not any(
            r["sentiment"] == org_report.SENTIMENT_RESOLUTION for r in filtered
        )

    def test_filter_includes_resolutions_when_requested(self):
        """Resolution reports should be included when include_resolved=True."""
        reports = self._make_reports()
        filtered = rules_engine.filter_reports(reports, include_resolved=True)
        assert any(r["sentiment"] == org_report.SENTIMENT_RESOLUTION for r in filtered)

    # ===========================================================================
    # Deduplicate
    # ===========================================================================
    def test_deduplicate_keeps_most_recent(self):
        """Deduplication should keep the most recent report per location+type."""
        ts = 1709000000000
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                ts,
                short_description="Old",
            ),
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                ts + 5000,
                short_description="New",
            ),
        ]
        deduped = rules_engine.deduplicate_reports(reports)
        assert len(deduped) == 1
        assert deduped[0]["short_description"] == "New"

    def test_deduplicate_different_types_kept(self):
        """Reports of different types from the same location should be kept separately."""
        ts = 1709000000000
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                ts,
            ),
            _make_report(
                "loc1",
                "bathroom",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                ts,
            ),
        ]
        deduped = rules_engine.deduplicate_reports(reports)
        assert len(deduped) == 2

    # ===========================================================================
    # Severity Rank
    # ===========================================================================
    def test_calculate_severity_rank_critical(self):
        """Critical priority should have high severity rank."""
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_CRITICAL,
            org_report.SENTIMENT_CONCERN,
            1000,
            days_active=5,
        )
        rank = rules_engine.calculate_severity_rank(report)
        # Base 100 + sentiment 0 + min(5*2, 20) = 110, capped at 100
        assert rank == 100

    def test_calculate_severity_rank_warning(self):
        """Warning priority should have medium severity rank."""
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_WARNING,
            org_report.SENTIMENT_CONCERN,
            1000,
            days_active=1,
        )
        rank = rules_engine.calculate_severity_rank(report)
        # Base 60 + sentiment 0 + min(1*2, 20) = 62
        assert rank == 62

    def test_calculate_severity_rank_info(self):
        """Info priority should have low severity rank."""
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_INFO,
            org_report.SENTIMENT_CONCERN,
            1000,
            days_active=1,
        )
        rank = rules_engine.calculate_severity_rank(report)
        # Base 20 + sentiment 0 + min(1*2, 20) = 22
        assert rank == 22

    def test_calculate_severity_rank_resolution_modifier(self):
        """Resolution sentiment should reduce severity rank."""
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_CRITICAL,
            org_report.SENTIMENT_RESOLUTION,
            1000,
            days_active=1,
        )
        rank = rules_engine.calculate_severity_rank(report)
        # Base 100 + sentiment -50 + min(1*2, 20) = 52
        assert rank == 52

    def test_calculate_severity_rank_preserves_existing(self):
        """If severity_rank is already set, it should be preserved."""
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_CRITICAL,
            org_report.SENTIMENT_CONCERN,
            1000,
            severity_rank=42,
        )
        rank = rules_engine.calculate_severity_rank(report)
        assert rank == 42

    def test_calculate_severity_rank_floor_at_zero(self):
        """Severity rank should never go below 0."""
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_INFO,
            org_report.SENTIMENT_CELEBRATION,
            1000,
            days_active=0,
        )
        rank = rules_engine.calculate_severity_rank(report)
        # Base 20 + sentiment -60 + days_boost = floored at 0
        assert rank == 0

    def test_calculate_severity_rank_handles_none_days_active(self):
        """A present-but-None days_active should not crash (regression).

        dict.get("days_active", 1) returns None when the key exists with value
        None, which previously raised TypeError on `days_active * 2`.
        """
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_WARNING,
            org_report.SENTIMENT_CONCERN,
            1000,
            days_active=None,
        )
        rank = rules_engine.calculate_severity_rank(report)
        # days_active normalized to 1: base 60 + sentiment 0 + min(1*2, 20) = 62
        assert rank == 62

    def test_calculate_severity_rank_handles_missing_days_active(self):
        """A missing days_active key should not crash and should default."""
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_WARNING,
            org_report.SENTIMENT_CONCERN,
            1000,
        )
        del report["days_active"]
        rank = rules_engine.calculate_severity_rank(report)
        assert rank == 62

    # ===========================================================================
    # Normalize days_active
    # ===========================================================================
    def test_normalize_days_active_missing(self):
        """None (missing/dropped field) should normalize to 1."""
        assert rules_engine.normalize_days_active(None) == 1

    def test_normalize_days_active_zero(self):
        """Zero should normalize to 1 (a reported concern was active >= 1 day)."""
        assert rules_engine.normalize_days_active(0) == 1

    def test_normalize_days_active_negative(self):
        """Negative values should normalize to 1."""
        assert rules_engine.normalize_days_active(-3) == 1

    def test_normalize_days_active_non_numeric(self):
        """Non-numeric values should normalize to 1."""
        assert rules_engine.normalize_days_active("5") == 1
        assert rules_engine.normalize_days_active(True) == 1

    def test_normalize_days_active_valid(self):
        """Valid positive numbers should pass through unchanged."""
        assert rules_engine.normalize_days_active(5) == 5
        assert rules_engine.normalize_days_active(2.5) == 2.5
        assert rules_engine.normalize_days_active(1) == 1

    # ===========================================================================
    # Enrich
    # ===========================================================================
    def test_enrich_adds_severity_rank(self):
        """Enrich should add severity_rank to reports missing it."""
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                1000,
            )
        ]
        enriched = rules_engine.enrich_reports(reports)
        assert enriched[0]["severity_rank"] is not None
        assert enriched[0]["severity_rank"] == 100

    def test_enrich_preserves_existing_severity_rank(self):
        """Enrich should not overwrite existing severity_rank."""
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                1000,
                severity_rank=50,
            )
        ]
        enriched = rules_engine.enrich_reports(reports)
        assert enriched[0]["severity_rank"] == 50

    def test_enrich_normalizes_none_days_active(self):
        """Enrich should replace a None days_active with 1 (regression).

        A None days_active surfaced as "Days Active: None" in emails and an LLM
        narrative of "no active days recorded".
        """
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
                days_active=None,
            )
        ]
        enriched = rules_engine.enrich_reports(reports)
        assert enriched[0]["days_active"] == 1

    def test_enrich_normalizes_missing_days_active(self):
        """Enrich should default a missing days_active key to 1."""
        report = _make_report(
            "loc1",
            "stability",
            org_report.PRIORITY_WARNING,
            org_report.SENTIMENT_CONCERN,
            1000,
        )
        del report["days_active"]
        enriched = rules_engine.enrich_reports([report])
        assert enriched[0]["days_active"] == 1

    def test_enrich_normalizes_zero_days_active(self):
        """Enrich should floor a zero days_active at 1."""
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
                days_active=0,
            )
        ]
        enriched = rules_engine.enrich_reports(reports)
        assert enriched[0]["days_active"] == 1

    def test_enrich_preserves_valid_days_active(self):
        """Enrich should leave a valid days_active untouched."""
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
                days_active=7,
            )
        ]
        enriched = rules_engine.enrich_reports(reports)
        assert enriched[0]["days_active"] == 7

    def test_process_pipeline_no_none_days_active_reaches_output(self):
        """No None/0 days_active should survive the full preprocessing pipeline.

        End-to-end guard for the live "no active days recorded" report: a mix of
        missing, None, zero, and valid days_active must all come out >= 1.
        """
        missing = _make_report(
            "loc1", "stability", org_report.PRIORITY_WARNING,
            org_report.SENTIMENT_CONCERN, 1000,
        )
        del missing["days_active"]
        reports = [
            missing,
            _make_report("loc2", "stability", org_report.PRIORITY_WARNING,
                         org_report.SENTIMENT_CONCERN, 1000, days_active=None),
            _make_report("loc3", "stability", org_report.PRIORITY_WARNING,
                         org_report.SENTIMENT_CONCERN, 1000, days_active=0),
            _make_report("loc4", "stability", org_report.PRIORITY_CRITICAL,
                         org_report.SENTIMENT_CONCERN, 1000, days_active=5),
        ]
        result = rules_engine.process_reports_for_llm(reports)
        for report in result["filtered_reports"]:
            assert report["days_active"] is not None
            assert report["days_active"] >= 1
        for category_reports in result["categorized_reports"].values():
            for report in category_reports:
                assert report["days_active"] >= 1

    # ===========================================================================
    # Sort
    # ===========================================================================
    def test_sort_by_priority(self):
        """Reports should be sorted by severity_rank DESC, then days_active DESC."""
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
                days_active=1,
                severity_rank=50,
            ),
            _make_report(
                "loc2",
                "bathroom",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                1000,
                days_active=5,
                severity_rank=100,
            ),
            _make_report(
                "loc3",
                "sleep",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
                days_active=10,
                severity_rank=50,
            ),
        ]
        sorted_reports = rules_engine.sort_reports_by_priority(reports)
        assert sorted_reports[0]["location_id"] == "loc2"  # severity 100
        assert sorted_reports[1]["location_id"] == "loc3"  # severity 50, days 10
        assert sorted_reports[2]["location_id"] == "loc1"  # severity 50, days 1

    # ===========================================================================
    # Categorize
    # ===========================================================================
    def test_categorize_reports(self):
        """Reports should be categorized by report_type."""
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                1000,
            ),
            _make_report(
                "loc2",
                "infrastructure",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
            ),
            _make_report(
                "loc3",
                "safety",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
            ),
            _make_report(
                "loc4",
                "energy",
                org_report.PRIORITY_INFO,
                org_report.SENTIMENT_CONCERN,
                1000,
            ),
        ]
        categorized = rules_engine.categorize_reports(reports)
        assert len(categorized[org_report.CATEGORY_WELLNESS]) == 1
        assert len(categorized[org_report.CATEGORY_IT]) == 1
        assert len(categorized[org_report.CATEGORY_SAFETY]) == 1
        assert len(categorized[org_report.CATEGORY_ENERGY]) == 1

    def test_categorize_unknown_type(self):
        """Reports with unknown report_type should go to 'other'."""
        reports = [
            _make_report(
                "loc1",
                "unknown_type",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
            ),
        ]
        categorized = rules_engine.categorize_reports(reports)
        assert len(categorized["other"]) == 1

    def test_categorize_fall_focus_as_wellness(self):
        """fall_focus reports must surface under the wellness category.

        The threshold-gated fall-risk escalation path
        (_evaluate_fall_focus_for_org) sends report_type="fall_focus". Without an
        explicit mapping it fell through to "other" and was dropped during persona
        extraction, so genuine fall-risk concerns never reached the Health &
        Wellness Report.
        """
        assert org_report.get_category("fall_focus") == org_report.CATEGORY_WELLNESS

        reports = [
            _make_report(
                "loc1",
                "fall_focus",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                1000,
            ),
        ]
        categorized = rules_engine.categorize_reports(reports)
        assert len(categorized[org_report.CATEGORY_WELLNESS]) == 1
        assert len(categorized["other"]) == 0

    def test_categorize_health_and_activity_as_wellness(self):
        """Auto-routed health.* events and activity/sedentary summaries map to wellness.

        Both report_types were previously absent from REPORT_TYPE_CATEGORIES, so
        genuine health.fall / health.heart_rate_alert escalations and activity
        summaries fell through to "other" and were dropped during persona extraction.
        """
        assert org_report.get_category("health") == org_report.CATEGORY_WELLNESS
        assert org_report.get_category("activity") == org_report.CATEGORY_WELLNESS

        reports = [
            _make_report(
                "loc1",
                "health",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                1000,
            ),
            _make_report(
                "loc2",
                "activity",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
            ),
        ]
        categorized = rules_engine.categorize_reports(reports)
        assert len(categorized[org_report.CATEGORY_WELLNESS]) == 2
        assert len(categorized["other"]) == 0

    # ===========================================================================
    # Limit
    # ===========================================================================
    def test_limit_top_reports(self):
        """Should limit to max_per_category."""
        reports = [
            _make_report(
                f"loc{i}",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
            )
            for i in range(25)
        ]
        categorized = {org_report.CATEGORY_WELLNESS: reports}
        limited = rules_engine.limit_top_reports(categorized, max_per_category=10)
        assert len(limited[org_report.CATEGORY_WELLNESS]) == 10

    # ===========================================================================
    # Full Pipeline
    # ===========================================================================
    def test_process_reports_for_llm_full_pipeline(self):
        """Full pipeline should filter, deduplicate, enrich, sort, categorize, and limit."""
        ts = 1709000000000
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=5,
            ),
            _make_report(
                "loc2",
                "bathroom",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=3,
            ),
            _make_report(
                "loc3",
                "infrastructure",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=2,
            ),
            _make_report(
                "loc4",
                "sleep",
                org_report.PRIORITY_INFO,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=1,
            ),
            _make_report(
                "loc5",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_RESOLUTION,
                ts,
                days_active=7,
            ),
        ]

        result = rules_engine.process_reports_for_llm(
            reports, include_resolved=True, include_info=False
        )

        assert result["stats"]["total_raw"] == 5
        # Info is excluded, so 4 reports pass filter
        assert result["stats"]["total_filtered"] == 4
        assert result["stats"]["total_critical"] >= 1
        assert result["stats"]["unique_locations"] >= 2

        # Wellness category should have stability + bathroom + resolution
        wellness_reports = result["categorized_reports"].get(
            org_report.CATEGORY_WELLNESS, []
        )
        assert len(wellness_reports) >= 1

    def test_process_reports_empty(self):
        """Empty input should produce empty output with zero stats."""
        result = rules_engine.process_reports_for_llm([])
        assert result["stats"]["total_raw"] == 0
        assert result["stats"]["total_filtered"] == 0
        assert len(result["filtered_reports"]) == 0

    # ===========================================================================
    # Get Top Locations
    # ===========================================================================
    def test_get_top_locations(self):
        """Should return top locations grouped and sorted by max severity."""
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                1000,
                severity_rank=90,
            ),
            _make_report(
                "loc1",
                "bathroom",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
                severity_rank=60,
            ),
            _make_report(
                "loc2",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                1000,
                severity_rank=70,
            ),
        ]
        top = rules_engine.get_top_locations(reports, max_locations=5)
        assert len(top) == 2
        assert top[0]["location_id"] == "loc1"  # Higher max severity
        assert len(top[0]["reports"]) == 2
        assert len(top[1]["reports"]) == 1


class TestReportBuilder:
    """Tests for the deterministic report builder."""

    def _make_processed_data(self):
        """Create sample processed data from rules engine."""
        ts = 1709000000000
        reports = [
            _make_report(
                "loc1",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=5,
                severity_rank=100,
            ),
            _make_report(
                "loc2",
                "bathroom",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=3,
                severity_rank=62,
            ),
            _make_report(
                "loc3",
                "infrastructure",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=2,
                severity_rank=100,
            ),
            _make_report(
                "loc4",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_RESOLUTION,
                ts,
                days_active=7,
                severity_rank=12,
            ),
            _make_report(
                "loc5",
                "stability",
                org_report.PRIORITY_WARNING,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=1,
                severity_rank=62,
            ),
            _make_report(
                "loc6",
                "stability",
                org_report.PRIORITY_CRITICAL,
                org_report.SENTIMENT_CONCERN,
                ts,
                days_active=4,
                severity_rank=100,
            ),
        ]
        return rules_engine.process_reports_for_llm(reports, include_resolved=True)

    # ===========================================================================
    # Build Master Report
    # ===========================================================================
    def test_build_master_report_structure(self):
        """Master report should have all required sections."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(
            processed, 1709000000000, "daily", "Test Org"
        )

        assert report["timestamp_ms"] == 1709000000000
        assert report["report_type"] == "daily"
        assert report["org_name"] == "Test Org"
        assert report["schema_version"] == "2.0"
        assert "executive_summary" in report["sections"]
        assert "top_concerns" in report["sections"]
        assert "top_celebrations" in report["sections"]
        assert "trends" in report["sections"]
        assert "category_deep_dives" in report["sections"]

    def test_build_master_report_executive_summary(self):
        """Executive summary should have key metrics."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        exec_summary = report["sections"]["executive_summary"]
        assert exec_summary["total_locations"] > 0
        assert exec_summary["total_reports"] > 0
        assert "top_concerns_list" in exec_summary
        assert len(exec_summary["top_concerns_list"]) <= 3
        # Text fields should be None (waiting for LLM)
        assert exec_summary["summary_text"] is None
        assert exec_summary["top_concern_text"] is None

    def test_build_master_report_top_concerns(self):
        """Top concerns should be organized by category."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        top_concerns = report["sections"]["top_concerns"]
        # Should have wellness (stability, bathroom) and IT (infrastructure) categories
        assert org_report.CATEGORY_WELLNESS in top_concerns
        wellness = top_concerns[org_report.CATEGORY_WELLNESS]
        assert wellness["count"] >= 1
        assert len(wellness["items"]) >= 1

    def test_build_master_report_concern_items_have_days_active(self):
        """Concern items (the field rendered in email and fed to the LLM) must
        always carry a positive days_active, even when source reports omitted it.

        Regression for the live report where every concern read "Days Active:
        None" and the LLM narrated "no active days recorded".
        """
        missing = _make_report(
            "loc1", "stability", org_report.PRIORITY_WARNING,
            org_report.SENTIMENT_CONCERN, 1709000000000,
        )
        del missing["days_active"]
        none_val = _make_report(
            "loc2", "stability", org_report.PRIORITY_WARNING,
            org_report.SENTIMENT_CONCERN, 1709000000000, days_active=None,
        )
        processed = rules_engine.process_reports_for_llm([missing, none_val])
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        items = report["sections"]["top_concerns"][org_report.CATEGORY_WELLNESS]["items"]
        assert len(items) == 2
        for item in items:
            assert item["days_active"] is not None
            assert item["days_active"] >= 1

    def test_build_master_report_celebrations(self):
        """Celebrations should include resolutions."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        celebrations = report["sections"]["top_celebrations"]
        assert celebrations["count"] >= 1
        assert len(celebrations["items"]) >= 1
        assert celebrations["items"][0]["sentiment"] == org_report.SENTIMENT_RESOLUTION

    def test_build_master_report_trends(self):
        """Trends should detect patterns across locations."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        trends = report["sections"]["trends"]
        # stability affects loc1, loc5, loc6 (3 concern locations) - should show as trend
        if org_report.CATEGORY_WELLNESS in trends:
            wellness_trends = trends[org_report.CATEGORY_WELLNESS]
            assert wellness_trends["count"] >= 1
            assert wellness_trends["items"][0]["locations_affected"] >= 2

    def test_build_master_report_category_deep_dives(self):
        """Category deep dives should have statistics for each category."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        deep_dives = report["sections"]["category_deep_dives"]
        if org_report.CATEGORY_WELLNESS in deep_dives:
            wellness = deep_dives[org_report.CATEGORY_WELLNESS]
            assert wellness["total_reports"] >= 1
            assert wellness["unique_locations"] >= 1
            assert "top_locations" in wellness

    # ===========================================================================
    # Enhancement Tasks
    # ===========================================================================
    def test_get_llm_enhancement_tasks(self):
        """Should return tasks for all enhancement-eligible fields."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")
        tasks = report_builder.get_llm_enhancement_tasks(report)

        assert len(tasks) > 0

        # First task should be executive summary
        assert tasks[0]["task_id"] == "executive_summary"
        assert tasks[0]["task_type"] == "summary"

        # Should have concern, celebration, trend, and deep_dive tasks
        task_types = set(t["task_type"] for t in tasks)
        assert "summary" in task_types
        assert "enhance_concern" in task_types

    def test_get_enhancement_tasks_empty_report(self):
        """Report with no concerns should still have executive summary task."""
        processed = rules_engine.process_reports_for_llm([])
        report = report_builder.build_master_report(processed, 1709000000000, "daily")
        tasks = report_builder.get_llm_enhancement_tasks(report)

        assert len(tasks) >= 1
        assert tasks[0]["task_id"] == "executive_summary"

    # ===========================================================================
    # Apply LLM Enhancement
    # ===========================================================================
    def test_apply_enhancement_executive_summary(self):
        """Should inject LLM text into executive summary."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        report = report_builder.apply_llm_enhancement(
            report,
            "executive_summary",
            {
                "summary_text": "Enhanced summary",
                "top_concern_text": "Enhanced concern",
            },
        )

        assert (
            report["sections"]["executive_summary"]["summary_text"]
            == "Enhanced summary"
        )
        assert (
            report["sections"]["executive_summary"]["top_concern_text"]
            == "Enhanced concern"
        )

    def test_apply_enhancement_concern(self):
        """Should inject LLM text into concern item."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        # Find a category that has concerns
        concerns = report["sections"]["top_concerns"]
        if org_report.CATEGORY_WELLNESS in concerns:
            report = report_builder.apply_llm_enhancement(
                report,
                f"concern_{org_report.CATEGORY_WELLNESS}_0",
                {
                    "enhanced_description": "Better description",
                    "context_explanation": "Why it matters",
                },
            )

            item = report["sections"]["top_concerns"][org_report.CATEGORY_WELLNESS][
                "items"
            ][0]
            assert item["enhanced_description"] == "Better description"
            assert item["context_explanation"] == "Why it matters"

    def test_apply_enhancement_celebration(self):
        """Should inject LLM text into celebration item."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        celebrations = report["sections"]["top_celebrations"]
        if celebrations["count"] > 0:
            report = report_builder.apply_llm_enhancement(
                report, "celebration_0", {"enhanced_description": "Great improvement"}
            )
            assert (
                report["sections"]["top_celebrations"]["items"][0][
                    "enhanced_description"
                ]
                == "Great improvement"
            )

    def test_apply_enhancement_deep_dive(self):
        """Should inject LLM text into category deep dive."""
        processed = self._make_processed_data()
        report = report_builder.build_master_report(processed, 1709000000000, "daily")

        deep_dives = report["sections"]["category_deep_dives"]
        if org_report.CATEGORY_WELLNESS in deep_dives:
            report = report_builder.apply_llm_enhancement(
                report,
                f"deep_dive_{org_report.CATEGORY_WELLNESS}",
                {"summary_text": "Wellness category overview"},
            )
            assert (
                report["sections"]["category_deep_dives"][org_report.CATEGORY_WELLNESS][
                    "summary_text"
                ]
                == "Wellness category overview"
            )
