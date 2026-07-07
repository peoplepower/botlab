from unittest.mock import patch, MagicMock

from botengine_pytest import BotEnginePyTest

from locations.location import Location  # type: ignore
import utilities.utilities as utilities  # type: ignore

from intelligence.dailyheartbeat.location_dailyheartbeat_microservice import (
    LocationDailyHeartbeatMicroservice,
    TIMER_REFERENCE_DAILY_HEARTBEAT,
)


class TestDailyHeartbeat:
    def _setup(self):
        """Common setup: botengine, location, and the microservice under test."""
        botengine = BotEnginePyTest({})
        botengine.set_timestamp(1685602800000)  # June 1, 2023 midnight PST

        location = Location(botengine, 0)
        location.initialize(botengine)
        location.new_version(botengine)

        mut = location.intelligence_modules.get(
            "intelligence.dailyheartbeat.location_dailyheartbeat_microservice"
        )
        if mut is None:
            mut = LocationDailyHeartbeatMicroservice(botengine, location)
            location.intelligence_modules[
                "intelligence.dailyheartbeat.location_dailyheartbeat_microservice"
            ] = mut

        return botengine, location, mut

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def test_initialization(self):
        botengine, location, mut = self._setup()
        assert mut is not None
        assert mut.critical_report_sent_today is False

    def test_new_version_adds_missing_attribute(self):
        botengine, location, mut = self._setup()
        del mut.critical_report_sent_today
        mut.new_version(botengine)
        assert mut.critical_report_sent_today is False

    # ------------------------------------------------------------------
    # Timer: heartbeat sent when no critical reports today
    # ------------------------------------------------------------------

    def test_timer_sends_heartbeat_when_no_critical_reports(self):
        botengine, location, mut = self._setup()

        # Add a mock report service so _send_daily_heartbeat doesn't bail
        mock_report_svc = MagicMock()
        location.intelligence_modules[
            "intelligence.reports.location_reports_microservice"
        ] = mock_report_svc

        with patch("signals.report.send_org_report") as mock_send:
            mut.timer_fired(botengine, TIMER_REFERENCE_DAILY_HEARTBEAT)
            mock_send.assert_called_once()

        # Flag should be reset after firing
        assert mut.critical_report_sent_today is False

    def test_timer_skips_heartbeat_when_critical_report_sent(self):
        botengine, location, mut = self._setup()
        mut.critical_report_sent_today = True

        with patch("signals.report.send_org_report") as mock_send:
            mut.timer_fired(botengine, TIMER_REFERENCE_DAILY_HEARTBEAT)
            mock_send.assert_not_called()

        # Flag should be reset even when skipped
        assert mut.critical_report_sent_today is False

    def test_timer_ignores_unrelated_argument(self):
        botengine, location, mut = self._setup()

        with patch("signals.report.send_org_report") as mock_send:
            mut.timer_fired(botengine, "SOMETHING_ELSE")
            mock_send.assert_not_called()

    # ------------------------------------------------------------------
    # Datastream: tracking critical reports
    # ------------------------------------------------------------------

    def test_datastream_marks_critical_report(self):
        botengine, location, mut = self._setup()
        mut.datastream_updated(
            botengine,
            "report_sent_to_org",
            {"priority": "critical"},
        )
        assert mut.critical_report_sent_today is True

    def test_datastream_marks_warning_report(self):
        botengine, location, mut = self._setup()
        mut.datastream_updated(
            botengine,
            "report_sent_to_org",
            {"priority": "warning"},
        )
        assert mut.critical_report_sent_today is True

    def test_datastream_ignores_info_report(self):
        botengine, location, mut = self._setup()
        mut.datastream_updated(
            botengine,
            "report_sent_to_org",
            {"priority": "info"},
        )
        assert mut.critical_report_sent_today is False

    def test_datastream_ignores_unrelated_address(self):
        botengine, location, mut = self._setup()
        mut.datastream_updated(
            botengine,
            "something_else",
            {"priority": "critical"},
        )
        assert mut.critical_report_sent_today is False

    # ------------------------------------------------------------------
    # Helper: device counting
    # ------------------------------------------------------------------

    def test_count_devices_online_empty(self):
        botengine, location, mut = self._setup()
        location.devices = {}
        assert mut._count_devices_online(botengine) == 0

    def test_count_devices_online_with_recent_device(self):
        botengine, location, mut = self._setup()
        device = MagicMock()
        device.last_updated_ms = botengine.get_timestamp() - utilities.ONE_HOUR_MS
        location.devices = {"dev1": device}
        assert mut._count_devices_online(botengine) == 1

    def test_count_devices_online_stale_device(self):
        botengine, location, mut = self._setup()
        device = MagicMock()
        device.last_updated_ms = botengine.get_timestamp() - (
            25 * utilities.ONE_HOUR_MS
        )
        location.devices = {"dev1": device}
        assert mut._count_devices_online(botengine) == 0

    # ------------------------------------------------------------------
    # Helper: last activity timestamp
    # ------------------------------------------------------------------

    def test_last_activity_timestamp_none_when_no_devices(self):
        botengine, location, mut = self._setup()
        location.devices = {}
        assert mut._get_last_activity_timestamp(botengine) is None

    def test_last_activity_timestamp_returns_latest(self):
        botengine, location, mut = self._setup()
        d1 = MagicMock()
        d1.last_updated_ms = 1000
        d2 = MagicMock()
        d2.last_updated_ms = 5000
        location.devices = {"a": d1, "b": d2}
        assert mut._get_last_activity_timestamp(botengine) == 5000
