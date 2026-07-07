import json
import os
from io import BytesIO
from unittest.mock import patch

import utilities.utilities as utilities  # type: ignore
from intelligence.trends_report import report_builder, services
from organization.organization import Organization  # type: ignore

from botengine_pytest import BotEnginePyTest

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_REPORT_TIMESTAMP_MS = 1773550800000


# ===========================================================================
# Data Loading Helpers
# ===========================================================================
def _load_trends_metadata():
    with open(os.path.join(_DATA_DIR, "trends_metadata.json")) as f:
        return json.load(f)


def _load_trends_data():
    """Load trends data: {location_id: {day_ms: {trend_id: {...}}}}"""
    with open(os.path.join(_DATA_DIR, "trends.json")) as f:
        raw = json.load(f)
    return {
        str(loc_id): loc["trends"]
        for loc_id, loc in raw.items()
    }


def _load_data_request_content():
    """Load as data request content: {location_id: {"trends": {...}}}"""
    with open(os.path.join(_DATA_DIR, "trends.json")) as f:
        raw = json.load(f)
    return {
        loc_id: {services.TRENDS_NOW_NAME: loc["trends"]}
        for loc_id, loc in raw.items()
    }


def _build_skeleton():
    trends_data = _load_trends_data()
    metadata = _load_trends_metadata()
    return report_builder.build_report_skeleton(
        trends_data, metadata, _REPORT_TIMESTAMP_MS
    )


class TestTrendsReportMicroservice:
    def _setup(self):
        botengine = BotEnginePyTest({})
        botengine.reset()
        organization = Organization(botengine, 0)
        organization.new_version(botengine)
        organization.initialize(botengine)
        mut = organization.intelligence_modules[
            "intelligence.trends_report.organization_trends_report_microservice"
        ]
        return botengine, organization, mut

    def test_initialization(self):
        """Module should initialize and new_version should run without errors."""
        botengine, organization, mut = self._setup()
        assert mut is not None
        mut.new_version(botengine)

    @patch('botengine_pytest.BotEnginePyTest.get_state')
    def test_data_request_and_skeleton(self, mock_get_state):
        """Data request pipeline: request, build skeleton, reject bad input."""
        botengine, organization, mut = self._setup()

        # _request_trends_data should call botengine.request_data
        with patch.object(botengine, "request_data") as mock_rd:
            mut._request_trends_data(botengine)
            mock_rd.assert_called_once()
            assert mock_rd.call_args[1]["reference"] == services.DATA_REQUEST_REFERENCE_TRENDS

        # async_data_request_ready with real data should build a skeleton
        content = _load_data_request_content()
        mock_get_state.return_value = _load_trends_metadata()
        mut.async_data_request_ready(
            botengine, services.DATA_REQUEST_REFERENCE_TRENDS, content
        )
        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        assert state is not None
        assert state["ready_for_processing"] is True
        report = state["report"]
        assert report["section1_overview"]["total_locations"] == len(content)
        total_locations = len(content)
        detailed = len(report["section2_individuals"])
        summary = len(report["section2_summary"])
        assert detailed + summary == total_locations
        assert detailed <= services.MAX_DETAILED_LOCATIONS
        assert "section3_review" in report

        # Empty data should not create a report
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, None, overwrite=True)
        mut.async_data_request_ready(
            botengine, services.DATA_REQUEST_REFERENCE_TRENDS,
            {"100": {services.TRENDS_NOW_NAME: {}}},
        )
        assert botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS) is None

        # Wrong reference should be ignored
        mut.async_data_request_ready(botengine, "some_other_reference", {})
        assert botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS) is None

    def test_timer_bridge(self):
        """Timer: detect ready skeleton, retry on missing data, give up after max."""
        botengine, organization, mut = self._setup()

        # Non-dict argument should be ignored (no error)
        mut.timer_fired(botengine, "not_a_dict")

        # No data yet -> should retry with incremented count
        with patch.object(mut, "start_timer_s") as mock_timer:
            mut.timer_fired(botengine, {"type": "data_request_timeout", "retry_count": 0})
            mock_timer.assert_called_once()
            assert mock_timer.call_args[1]["argument"]["retry_count"] == 1

        # Max retries -> should give up (no timer set)
        with patch.object(mut, "start_timer_s") as mock_timer:
            mut.timer_fired(botengine, {
                "type": "data_request_timeout",
                "retry_count": services.MAX_DATA_REQUEST_RETRIES,
            })
            mock_timer.assert_not_called()

        # Ready skeleton -> should start LLM pipeline
        skeleton = _build_skeleton()
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, {
            "report": skeleton,
            "tasks_remaining": len(skeleton["enhancement_tasks"]),
            "tasks_completed": 0,
            "start_time": botengine.get_timestamp(),
            "ready_for_processing": True,
        }, overwrite=True)
        with patch.object(mut, "_process_next_enhancement_task") as mock_process:
            mut.timer_fired(botengine, {"type": "data_request_timeout", "retry_count": 0})
            mock_process.assert_called_once()

    def test_llm_enhancement_pipeline(self):
        """LLM: routing, chaining, individual text, finalize, and parsing."""
        botengine, organization, mut = self._setup()

        # Route to handler on correct reference; ignore unknown
        with patch.object(mut, "_handle_report_llm_response") as mock_h:
            mut.llm_response(botengine, {"choices": [{"message": {"content": "t"}}]},
                             services.LLM_REFERENCE_TRENDS_REPORT, {"task_id": "t"})
            mock_h.assert_called_once()
        with patch.object(mut, "_handle_report_llm_response") as mock_h:
            mut.llm_response(botengine, {}, "unknown_reference", {})
            mock_h.assert_not_called()

        # Setup skeleton state for chaining tests
        skeleton = _build_skeleton()
        total_tasks = len(skeleton["enhancement_tasks"])
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, {
            "report": skeleton,
            "tasks_remaining": total_tasks,
            "tasks_completed": 0,
            "start_time": botengine.get_timestamp(),
            "ready_for_processing": False,
        }, overwrite=True)

        # Overview enhancement should chain to next and apply text
        with patch.object(mut, "_process_next_enhancement_task") as mock_next:
            mut._handle_report_llm_response(botengine,
                {"choices": [{"message": {"content": "overview_text: Test overview."}}]},
                {"task_id": services.TASK_ANALYSIS_OVERVIEW,
                 "task_type": services.TASK_ANALYSIS_OVERVIEW,
                 "fields_to_fill": ["overview_text"]})
            mock_next.assert_called_once()
        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        assert state["report"]["section1_overview"]["overview_text"] == "Test overview."

        # Individual enhancement should apply to correct location
        individual_task = [t for t in skeleton["enhancement_tasks"]
                           if t["task_type"] == services.TASK_INDIVIDUAL_ANALYSIS][0]
        location_id = individual_task["data"]["location_id"]
        with patch.object(mut, "_process_next_enhancement_task"):
            mut._handle_report_llm_response(botengine,
                {"choices": [{"message": {"content": "individual_text: Looks great."}}]},
                {"task_id": individual_task["task_id"],
                 "task_type": services.TASK_INDIVIDUAL_ANALYSIS,
                 "fields_to_fill": ["individual_text"]})
        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        assert state["report"]["section2_individuals"][location_id]["individual_text"] == "Looks great."

        # Last task should trigger finalize
        state["tasks_remaining"] = 1
        state["tasks_completed"] = total_tasks - 1
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, state, overwrite=True)
        with patch.object(mut, "_finalize_report") as mock_fin:
            mut._handle_report_llm_response(botengine,
                {"choices": [{"message": {"content": "review_text: Test review."}}]},
                {"task_id": services.TASK_REVIEW_SUMMARY,
                 "task_type": services.TASK_REVIEW_SUMMARY,
                 "fields_to_fill": ["review_text"]})
            mock_fin.assert_called_once()

        # Parse: labeled field + fallback to entire content
        r = mut._parse_llm_text_response("overview_text: The overview.", ["overview_text"])
        assert r["overview_text"] == "The overview."
        r = mut._parse_llm_text_response("No label here.", ["overview_text"])
        assert r["overview_text"] == "No label here."

    def test_build_enhancement_messages(self):
        """All task types produce 4-message sequences with hallucination guards."""
        botengine, organization, mut = self._setup()
        skeleton = _build_skeleton()

        # Verify all task types include hallucination guard
        tested_types = set()
        for task in skeleton["enhancement_tasks"]:
            if task["task_type"] in tested_types:
                continue
            messages, max_tokens = mut._build_enhancement_messages(task)
            assert len(messages) == 4
            assert messages[0]["role"] == "system"
            assert messages[2]["role"] == "assistant"
            assert "CRITICAL" in messages[0]["content"]
            assert "Never invent" in messages[0]["content"]
            assert max_tokens > 0
            tested_types.add(task["task_type"])

        assert tested_types == {
            services.TASK_ANALYSIS_OVERVIEW,
            services.TASK_INDIVIDUAL_ANALYSIS,
            services.TASK_REVIEW_SUMMARY,
        }

        # Overview message should contain location/trend counts
        overview_task = skeleton["enhancement_tasks"][0]
        msgs, _ = mut._build_enhancement_messages(overview_task)
        user_msg = msgs[3]["content"]
        assert str(overview_task["data"]["total_locations"]) in user_msg
        assert str(overview_task["data"]["total_trend_types"]) in user_msg

        # Individual message with outliers should reference outlier data
        individual_tasks = [t for t in skeleton["enhancement_tasks"]
                            if t["task_type"] == services.TASK_INDIVIDUAL_ANALYSIS]
        task_with_outliers = next(
            (t for t in individual_tasks if t["data"]["outlier_trends"]),
            individual_tasks[0],
        )
        msgs, _ = mut._build_enhancement_messages(task_with_outliers)
        if task_with_outliers["data"]["outlier_trends"]:
            assert task_with_outliers["data"]["outlier_trends"][0]["title"] in msgs[3]["content"]

        # Unknown task type returns empty
        msgs, tokens = mut._build_enhancement_messages(
            {"task_id": "x", "task_type": "x", "data": {}, "fields_to_fill": []}
        )
        assert msgs == [] and tokens == 0

    def test_pdf_handles_import_error(self):
        """Missing fpdf2 should not raise."""
        botengine, organization, mut = self._setup()
        with patch.dict("sys.modules", {"fpdf": None}):
            mut._generate_and_email_pdf(botengine, _build_skeleton())


class TestReportBuilder:
    def test_build_skeleton(self):
        """Skeleton structure, metadata, and empty-data edge case."""
        skeleton = _build_skeleton()
        for key in ("section1_overview", "section2_individuals", "section2_summary",
                     "section3_review", "enhancement_tasks", "metadata", "timestamp_ms"):
            assert key in skeleton
        assert skeleton["metadata"] == _load_trends_metadata()

        # Empty data produces empty sections
        empty = report_builder.build_report_skeleton({}, {}, _REPORT_TIMESTAMP_MS)
        assert empty["section1_overview"]["total_locations"] == 0
        assert len(empty["section2_individuals"]) == 0
        assert len(empty["section2_summary"]) == 0

    def test_section_content(self):
        """All three sections contain correct data from real sample."""
        trends_data = _load_trends_data()
        metadata = _load_trends_metadata()
        skeleton = report_builder.build_report_skeleton(
            trends_data, metadata, _REPORT_TIMESTAMP_MS
        )

        # Section 1: overview with category stats — _get_latest_trends collects
        # the most recent data point per trend across all days, so all categories
        # should be represented even when the latest calendar day is sparse.
        s1 = skeleton["section1_overview"]
        assert s1["total_locations"] == len(trends_data)
        assert s1["total_trend_types"] > 10, (
            f"Only {s1['total_trend_types']} trend types — latest-day-only bug?"
        )
        assert "category.sleep" in s1["category_stats"]
        assert "category.activity" in s1["category_stats"]
        assert "category.summary" in s1["category_stats"]

        # Section 2: detailed individuals + summary split
        s2 = skeleton["section2_individuals"]
        s2_summary = skeleton["section2_summary"]
        assert len(s2) + len(s2_summary) == len(trends_data)
        assert len(s2) <= services.MAX_DETAILED_LOCATIONS

        for loc_id, loc in s2.items():
            assert loc_id in trends_data
            for key in ("current_trends", "historical", "alerts",
                        "individual_text", "health_distribution", "wellness_history"):
                assert key in loc

            # Health distribution covers all trends
            h = loc["health_distribution"]
            assert h["healthy"] + h["concerning"] + h["critical"] == len(loc["current_trends"])

            # Wellness history has entries (may be fewer than total days
            # if some days lack wellness data)
            assert len(loc["wellness_history"]) > 0

            # Historical has one point per day the trend was active
            num_days = len(trends_data[loc_id])
            for history in loc["historical"].values():
                assert 0 < len(history) <= num_days

        # Summary locations have lightweight data only
        for loc_id, loc in s2_summary.items():
            assert loc_id in trends_data
            for key in ("category_scores", "total_trends", "critical_count",
                        "concerning_count"):
                assert key in loc

        # Section 3: review with category health
        s3 = skeleton["section3_review"]
        assert len(s3["category_health"]) > 0
        assert "cross_location_patterns" in s3
        assert "review_text" in s3

    def test_enhancement_tasks(self):
        """Task ordering, count, and apply_llm_enhancement."""
        skeleton = _build_skeleton()
        tasks = skeleton["enhancement_tasks"]
        detailed_count = len(skeleton["section2_individuals"])

        # 1 overview + min(N, MAX) individual + 1 review
        assert len(tasks) == 1 + detailed_count + 1
        assert tasks[0]["task_type"] == services.TASK_ANALYSIS_OVERVIEW
        assert tasks[-1]["task_type"] == services.TASK_REVIEW_SUMMARY
        individual = [t for t in tasks if t["task_type"] == services.TASK_INDIVIDUAL_ANALYSIS]
        assert len(individual) == detailed_count
        assert detailed_count <= services.MAX_DETAILED_LOCATIONS

        # Apply enhancements
        report_builder.apply_llm_enhancement(
            skeleton, services.TASK_ANALYSIS_OVERVIEW, {"overview_text": "O"}
        )
        assert skeleton["section1_overview"]["overview_text"] == "O"

        report_builder.apply_llm_enhancement(
            skeleton, services.TASK_REVIEW_SUMMARY, {"review_text": "R"}
        )
        assert skeleton["section3_review"]["review_text"] == "R"


class TestPlotBuilder:
    def test_charts_with_real_data(self):
        """All chart generators produce valid BytesIO from real skeleton data."""
        from intelligence.trends_report import plot_builder

        skeleton = _build_skeleton()
        metadata = skeleton["metadata"]
        s1 = skeleton["section1_overview"]
        s2 = skeleton["section2_individuals"]
        s3 = skeleton["section3_review"]
        first_loc = list(s2.values())[0]

        # Category overview bar chart
        buf = plot_builder.generate_category_overview_chart(s1["category_stats"], metadata)
        assert isinstance(buf, BytesIO) and len(buf.getvalue()) > 0
        buf.close()

        # Z-score heatmap (returns list of pages)
        pages = plot_builder.generate_zscore_heatmap(s2, metadata)
        assert isinstance(pages, list) and len(pages) > 0
        for buf in pages:
            assert isinstance(buf, BytesIO) and len(buf.getvalue()) > 0
            buf.close()

        # Category health chart
        buf = plot_builder.generate_category_health_chart(s3["category_health"])
        assert isinstance(buf, BytesIO) and len(buf.getvalue()) > 0
        buf.close()

        # Individual overview (pie + wellness timeline)
        buf = plot_builder.generate_individual_overview_charts(
            first_loc["health_distribution"], first_loc["wellness_history"]
        )
        assert isinstance(buf, BytesIO) and len(buf.getvalue()) > 0
        buf.close()

    def test_charts_with_empty_data(self):
        """Chart generators handle empty input gracefully."""
        from intelligence.trends_report import plot_builder

        for buf in [
            plot_builder.generate_category_overview_chart({}, {}),
            plot_builder.generate_individual_overview_charts(
                {"healthy": 0, "concerning": 0, "critical": 0}, []
            ),
            plot_builder.generate_category_health_chart({}),
        ]:
            assert isinstance(buf, BytesIO) and len(buf.getvalue()) > 0
            buf.close()

        # Heatmap returns a list even for empty data
        pages = plot_builder.generate_zscore_heatmap({}, {})
        assert isinstance(pages, list) and len(pages) > 0
        for buf in pages:
            assert isinstance(buf, BytesIO) and len(buf.getvalue()) > 0
            buf.close()

    def test_charts_edge_cases(self):
        """Charts handle all-zero z-scores gracefully."""
        from intelligence.trends_report import plot_builder

        # Heatmap with all-zero z-scores
        pages = plot_builder.generate_zscore_heatmap(
            {"loc1": {"current_trends": {
                "t1": {"category": "category.sleep", "zscore": 0},
            }}},
            {},
        )
        assert isinstance(pages, list) and len(pages) == 1
        assert isinstance(pages[0], BytesIO) and len(pages[0].getvalue()) > 0
        pages[0].close()


class TestReportBuilderExtended:
    """Extended report builder tests covering edge cases and Phase 1 fixes."""

    def test_trends_not_in_metadata(self):
        """Trends in data but not metadata should fall back to category.other."""
        skeleton = _build_skeleton()
        s1 = skeleton["section1_overview"]
        # trend.visitor, trend.absent, dow.*, etc. are in data but not metadata
        assert "category.other" in s1["category_stats"]
        other_stats = s1["category_stats"]["category.other"]
        assert other_stats["trend_count"] > 0

    def test_hidden_trends_filtered(self):
        """Trends with hidden:true in metadata should be excluded from all sections."""
        metadata = _load_trends_metadata()
        hidden_ids = {tid for tid, meta in metadata.items() if meta.get("hidden")}
        assert len(hidden_ids) > 0, "Test data should have hidden trends"

        skeleton = _build_skeleton()

        # Section 1: hidden trends should not appear in category stats
        s1 = skeleton["section1_overview"]
        for cat_stats in s1["category_stats"].values():
            for trend_id in cat_stats.get("avg_values", {}):
                assert trend_id not in hidden_ids, (
                    f"Hidden trend {trend_id} in category stats"
                )

        # Section 1: hidden trends should not appear in outliers
        for outlier in s1.get("outliers", []):
            assert outlier["trend_id"] not in hidden_ids, (
                f"Hidden trend {outlier['trend_id']} in outliers"
            )

        # Section 2: hidden trends should not appear in current_trends
        s2 = skeleton["section2_individuals"]
        for loc_id, loc_data in s2.items():
            for trend_id in loc_data["current_trends"]:
                assert trend_id not in hidden_ids, (
                    f"Hidden trend {trend_id} in location {loc_id} current_trends"
                )
            for trend_id in loc_data["historical"]:
                assert trend_id not in hidden_ids, (
                    f"Hidden trend {trend_id} in location {loc_id} historical"
                )

        # Section 3: hidden trends should not appear in cross-location patterns
        s3 = skeleton["section3_review"]
        for pattern in s3["cross_location_patterns"]:
            assert pattern["trend_id"] not in hidden_ids, (
                f"Hidden trend {pattern['trend_id']} in cross-location patterns"
            )

    def test_critical_zscore_classification(self):
        """Z-scores >= 2.5 should be classified as critical when present in latest trends."""
        # The real test data's critical z-scores are on older days, not the
        # latest per-trend snapshot.  Verify with synthetic data instead.
        trends_data = {
            "loc1": {
                "1000": {
                    "trend.a": {"value": 10, "zscore": 3.0},  # critical
                    "trend.b": {"value": 20, "zscore": 1.8},  # concerning
                    "trend.c": {"value": 30, "zscore": 0.5},  # healthy
                },
            },
        }
        metadata = {
            "trend.a": {"category": "category.sleep", "title": "A"},
            "trend.b": {"category": "category.sleep", "title": "B"},
            "trend.c": {"category": "category.sleep", "title": "C"},
        }
        skeleton = report_builder.build_report_skeleton(
            trends_data, metadata, _REPORT_TIMESTAMP_MS
        )
        s3 = skeleton["section3_review"]
        total_critical = sum(
            cat["critical"] for cat in s3["category_health"].values()
        )
        assert total_critical == 1
        total_concerning = sum(
            cat["concerning"] for cat in s3["category_health"].values()
        )
        assert total_concerning == 1

    def test_wellness_history_strategy2(self):
        """Falls back to category.summary when no wellness title exists."""
        metadata_no_wellness = {
            "trend.overall": {
                "category": "category.summary",
                "title": "Overall Score",
            }
        }
        days = {
            "1000": {"trend.overall": {"value": 80, "zscore": 0.5}},
            "2000": {"trend.overall": {"value": 85, "zscore": 0.3}},
        }
        history = report_builder._extract_wellness_history(
            days, ["1000", "2000"], metadata_no_wellness
        )
        assert len(history) == 2
        assert history[0]["value"] == 80
        assert history[1]["value"] == 85

    def test_wellness_history_strategy3(self):
        """Falls back to synthetic z-score proxy when no wellness/summary exists."""
        metadata_none = {
            "trend.x": {"category": "category.sleep", "title": "X Metric"}
        }
        days = {
            "1000": {"trend.x": {"value": 50, "zscore": 1.0}},
        }
        history = report_builder._extract_wellness_history(
            days, ["1000"], metadata_none
        )
        assert len(history) == 1
        # Synthetic: 100 - (avg |z| * 20) = 100 - 20 = 80
        assert history[0]["value"] == 80.0

    def test_apply_unknown_task_id(self):
        """Unknown task_id should not crash or modify the report."""
        skeleton = _build_skeleton()
        original_overview = skeleton["section1_overview"]["overview_text"]
        original_review = skeleton["section3_review"]["review_text"]
        report_builder.apply_llm_enhancement(
            skeleton, "unknown_task", {"x": "y"}
        )
        assert skeleton["section1_overview"]["overview_text"] == original_overview
        assert skeleton["section3_review"]["review_text"] == original_review

    def test_location_limit_and_summary(self):
        """Locations beyond MAX_DETAILED_LOCATIONS get summary-only treatment."""
        metadata = {
            "trend.a": {"category": "category.sleep", "title": "A"},
            "trend.b": {"category": "category.activity", "title": "B"},
        }
        # Build 25 synthetic locations
        trends_data = {}
        for i in range(25):
            trends_data[f"loc_{i}"] = {
                "1000": {
                    "trend.a": {"value": 10, "zscore": float(i) * 0.2},
                    "trend.b": {"value": 20, "zscore": 0.1},
                },
            }

        skeleton = report_builder.build_report_skeleton(
            trends_data, metadata, _REPORT_TIMESTAMP_MS
        )

        s2 = skeleton["section2_individuals"]
        s2_summary = skeleton["section2_summary"]

        # Exactly MAX_DETAILED_LOCATIONS get full treatment
        assert len(s2) == services.MAX_DETAILED_LOCATIONS
        assert len(s2_summary) == 25 - services.MAX_DETAILED_LOCATIONS

        # All locations accounted for
        all_ids = set(s2.keys()) | set(s2_summary.keys())
        assert all_ids == set(trends_data.keys())

        # LLM tasks only for detailed locations
        tasks = skeleton["enhancement_tasks"]
        individual_tasks = [
            t for t in tasks
            if t["task_type"] == services.TASK_INDIVIDUAL_ANALYSIS
        ]
        assert len(individual_tasks) == services.MAX_DETAILED_LOCATIONS

        # Section 1 overview still counts ALL locations
        assert skeleton["section1_overview"]["total_locations"] == 25

        # Summary entries have expected structure
        for loc_data in s2_summary.values():
            assert "category_scores" in loc_data
            assert "total_trends" in loc_data
            assert "critical_count" in loc_data
            assert "concerning_count" in loc_data

    def test_criticality_sort_order(self):
        """_sort_by_criticality places most critical locations first."""
        from intelligence.trends_report.organization_trends_report_microservice import (
            OrganizationTrendsReportMicroservice,
        )

        trends_data = {
            "healthy": {
                "1000": {
                    "t1": {"value": 1, "zscore": 0.2},
                    "t2": {"value": 2, "zscore": 0.1},
                },
            },
            "concerning": {
                "1000": {
                    "t1": {"value": 1, "zscore": 1.8},
                    "t2": {"value": 2, "zscore": 0.1},
                },
            },
            "critical": {
                "1000": {
                    "t1": {"value": 1, "zscore": 3.0},
                    "t2": {"value": 2, "zscore": 0.1},
                },
            },
        }

        sorted_data = OrganizationTrendsReportMicroservice._sort_by_criticality(
            trends_data
        )
        sorted_ids = list(sorted_data.keys())

        assert sorted_ids[0] == "critical"
        assert sorted_ids[1] == "concerning"
        assert sorted_ids[2] == "healthy"


class TestMicroserviceExtended:
    """Extended microservice tests covering error handling edge cases."""

    def _setup(self):
        botengine = BotEnginePyTest({})
        botengine.reset()
        organization = Organization(botengine, 0)
        organization.new_version(botengine)
        organization.initialize(botengine)
        mut = organization.intelligence_modules[
            "intelligence.trends_report.organization_trends_report_microservice"
        ]
        return botengine, organization, mut

    def test_llm_error_advances_pipeline(self):
        """LLM processing error should skip the task and continue pipeline."""
        botengine, organization, mut = self._setup()
        skeleton = _build_skeleton()
        total_tasks = len(skeleton["enhancement_tasks"])
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, {
            "report": skeleton,
            "tasks_remaining": total_tasks,
            "tasks_completed": 0,
            "start_time": botengine.get_timestamp(),
            "ready_for_processing": False,
        }, overwrite=True)

        # Completely empty response — should not crash, should advance
        with patch.object(mut, "_process_next_enhancement_task") as mock_next:
            mut._handle_report_llm_response(
                botengine, {},
                {"task_id": services.TASK_ANALYSIS_OVERVIEW,
                 "task_type": services.TASK_ANALYSIS_OVERVIEW,
                 "fields_to_fill": ["overview_text"]},
            )
        state = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        assert state is not None
        assert state["tasks_completed"] >= 1
        assert state["tasks_remaining"] < total_tasks

    def test_llm_error_on_last_task_finalizes(self):
        """LLM error on the final task should still finalize the report."""
        botengine, organization, mut = self._setup()
        skeleton = _build_skeleton()
        botengine.save_variable(services.STATE_VAR_REPORT_IN_PROGRESS, {
            "report": skeleton,
            "tasks_remaining": 1,
            "tasks_completed": len(skeleton["enhancement_tasks"]) - 1,
            "start_time": botengine.get_timestamp(),
            "ready_for_processing": False,
        }, overwrite=True)

        # Force an error by passing a response that will fail parsing
        with patch.object(mut, "_finalize_report") as mock_fin:
            # None response triggers exception in content extraction
            mut._handle_report_llm_response(
                botengine, None,
                {"task_id": services.TASK_REVIEW_SUMMARY,
                 "task_type": services.TASK_REVIEW_SUMMARY,
                 "fields_to_fill": ["review_text"]},
            )
            mock_fin.assert_called_once()
