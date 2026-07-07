"""
Created on March 31, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Tests for LocationDeviceHealthMicroservice
"""

import unittest
from unittest.mock import patch, MagicMock

from locations.location import Location  # type: ignore
import utilities.utilities as utilities  # type: ignore

from botengine_pytest import BotEnginePyTest

from intelligence.devicehealth.location_devicehealth_microservice import (
    TIMER_REFERENCE_CHECK_DEVICES,
    OFFLINE_THRESHOLD_MS,
)


class TestLocationDeviceHealthMicroservice(unittest.TestCase):
    """Test cases for LocationDeviceHealthMicroservice"""

    def setUp(self):
        """Set up test fixtures"""
        self.botengine = BotEnginePyTest({})
        self.location_object = Location(self.botengine, 0)
        self.location_object.initialize(self.botengine)
        self.location_object.new_version(self.botengine)

        # Get the microservice under test
        self.mut = self.location_object.intelligence_modules.get(
            "intelligence.devicehealth.location_devicehealth_microservice"
        )

    def _skip_if_not_loaded(self):
        if self.mut is None:
            self.skipTest("Device health microservice not loaded")

    def test_initialization(self):
        """Test that microservice initializes with correct default state"""
        self._skip_if_not_loaded()
        self.assertIsNotNone(self.mut)
        self.assertIsInstance(self.mut.offline_concerns, dict)
        self.assertEqual(len(self.mut.offline_concerns), 0)

    def test_new_version_initializes_offline_concerns(self):
        """Test new_version creates offline_concerns if missing"""
        self._skip_if_not_loaded()
        del self.mut.offline_concerns
        self.mut.new_version(self.botengine)
        self.assertIsInstance(self.mut.offline_concerns, dict)

    def test_new_version_preserves_existing_offline_concerns(self):
        """Test new_version does not overwrite existing offline_concerns"""
        self._skip_if_not_loaded()
        self.mut.offline_concerns = {
            "device_1": {"report_id": "r1", "offline_since_ms": 1000}
        }
        self.mut.new_version(self.botengine)
        self.assertIn("device_1", self.mut.offline_concerns)

    def test_is_device_offline_true(self):
        """Test device is considered offline when last measurement exceeds threshold"""
        self._skip_if_not_loaded()
        device = MagicMock()
        device.last_updated_ms = (
            self.botengine.get_timestamp() - OFFLINE_THRESHOLD_MS - 1
        )
        self.assertTrue(self.mut._is_device_offline(self.botengine, device))

    def test_is_device_offline_false_recent(self):
        """Test device is online when last measurement is recent"""
        self._skip_if_not_loaded()
        device = MagicMock()
        device.last_updated_ms = self.botengine.get_timestamp() - (
            OFFLINE_THRESHOLD_MS // 2
        )
        self.assertFalse(self.mut._is_device_offline(self.botengine, device))

    def test_is_device_offline_false_no_measurement(self):
        """Test device with no last measurement is not considered offline"""
        self._skip_if_not_loaded()
        device = MagicMock(spec=[])  # no attributes
        self.assertFalse(self.mut._is_device_offline(self.botengine, device))

    def test_get_device_last_measurement_ms_last_updated(self):
        """Test getting last measurement from last_updated_ms"""
        self._skip_if_not_loaded()
        device = MagicMock()
        device.last_updated_ms = 12345
        device.measurements_timestamp = 99999
        self.assertEqual(self.mut._get_device_last_measurement_ms(device), 12345)

    def test_get_device_last_measurement_ms_measurements_timestamp(self):
        """Test fallback to measurements_timestamp"""
        self._skip_if_not_loaded()
        device = MagicMock(spec=[])
        device.measurements_timestamp = 67890
        self.assertEqual(self.mut._get_device_last_measurement_ms(device), 67890)

    def test_get_device_last_measurement_ms_none(self):
        """Test returns None when no measurement timestamps exist"""
        self._skip_if_not_loaded()
        device = MagicMock(spec=[])
        self.assertIsNone(self.mut._get_device_last_measurement_ms(device))

    @patch("signals.report.send_org_report")
    @patch("utilities.utilities.good_enough_unique_id", return_value="abc123")
    def test_check_offline_devices_sends_concern(self, mock_uid, mock_send):
        """Test that offline device triggers a concern report"""
        self._skip_if_not_loaded()

        now_ms = self.botengine.get_timestamp()

        device = MagicMock()
        device.device_id = "device_1"
        device.description = "Front Door Sensor"
        device.device_type = 10071
        device.last_updated_ms = now_ms - (2 * utilities.ONE_HOUR_MS)

        self.location_object.devices = {"device_1": device}

        # Add report service mock so the concern path doesn't bail out
        self.location_object.intelligence_modules[
            "intelligence.reports.location_reports_microservice"
        ] = MagicMock()

        self.mut._check_offline_devices(self.botengine)

        mock_send.assert_called_once()
        self.assertIn("device_1", self.mut.offline_concerns)
        self.assertEqual(
            self.mut.offline_concerns["device_1"]["report_id"], "device_offline_0_abc123"
        )

    @patch("signals.report.send_org_report")
    @patch("utilities.utilities.good_enough_unique_id", return_value="abc123")
    def test_check_offline_devices_no_duplicate_concern(
        self, mock_uid, mock_send
    ):
        """Test that an already-tracked offline device does not generate a duplicate concern"""
        self._skip_if_not_loaded()

        now_ms = self.botengine.get_timestamp()

        device = MagicMock()
        device.device_id = "device_1"
        device.description = "Front Door Sensor"
        device.device_type = 10071
        device.last_updated_ms = now_ms - (2 * utilities.ONE_HOUR_MS)

        self.location_object.devices = {"device_1": device}
        self.location_object.intelligence_modules[
            "intelligence.reports.location_reports_microservice"
        ] = MagicMock()

        # Pre-populate concern
        self.mut.offline_concerns["device_1"] = {
            "report_id": "existing_report",
            "offline_since_ms": now_ms - (2 * utilities.ONE_HOUR_MS),
        }

        self.mut._check_offline_devices(self.botengine)

        mock_send.assert_not_called()

    @patch("signals.report.send_org_report")
    def test_check_offline_devices_skips_online_device(self, mock_send):
        """Test that an online device does not trigger a concern"""
        self._skip_if_not_loaded()

        device = MagicMock()
        device.device_id = "device_1"
        device.last_updated_ms = self.botengine.get_timestamp() - 1000  # 1 second ago

        self.location_object.devices = {"device_1": device}

        self.mut._check_offline_devices(self.botengine)

        mock_send.assert_not_called()
        self.assertEqual(len(self.mut.offline_concerns), 0)

    @patch("signals.report.send_org_report")
    def test_device_measurements_updated_sends_resolution(self, mock_send):
        """Test that a device coming back online sends a resolution report"""
        self._skip_if_not_loaded()

        now_ms = self.botengine.get_timestamp()
        offline_since_ms = now_ms - (3 * utilities.ONE_HOUR_MS)

        device = MagicMock()
        device.device_id = "device_1"
        device.description = "Front Door Sensor"
        device.device_type = 10071

        self.mut.offline_concerns["device_1"] = {
            "report_id": "concern_report_456",
            "offline_since_ms": offline_since_ms,
        }

        self.location_object.intelligence_modules[
            "intelligence.reports.location_reports_microservice"
        ] = MagicMock()

        self.mut.device_measurements_updated(self.botengine, device)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        self.assertEqual(
            call_kwargs.kwargs.get("previous_report_id")
            or call_kwargs[1].get(
                "previous_report_id",
                call_kwargs[0][6] if len(call_kwargs[0]) > 6 else None,
            ),
            "concern_report_456",
        )
        self.assertNotIn("device_1", self.mut.offline_concerns)

    def test_device_measurements_updated_no_concern_is_noop(self):
        """Test that a measurement update for a non-concerned device is a no-op"""
        self._skip_if_not_loaded()

        device = MagicMock()
        device.device_id = "device_2"

        # Should not raise or change state
        self.mut.device_measurements_updated(self.botengine, device)
        self.assertEqual(len(self.mut.offline_concerns), 0)

    def test_device_deleted_cleans_up_concern(self):
        """Test that deleting a device removes its offline concern"""
        self._skip_if_not_loaded()

        device = MagicMock()
        device.device_id = "device_1"

        self.mut.offline_concerns["device_1"] = {
            "report_id": "r1",
            "offline_since_ms": 1000,
        }

        self.mut.device_deleted(self.botengine, device)
        self.assertNotIn("device_1", self.mut.offline_concerns)

    def test_device_deleted_no_concern_is_noop(self):
        """Test that deleting a device with no concern is a no-op"""
        self._skip_if_not_loaded()

        device = MagicMock()
        device.device_id = "device_99"

        self.mut.device_deleted(self.botengine, device)
        self.assertEqual(len(self.mut.offline_concerns), 0)

    @patch("signals.report.send_org_report")
    @patch("utilities.utilities.good_enough_unique_id", return_value="abc789")
    def test_timer_fired_checks_devices(self, mock_uid, mock_send):
        """Test that firing the check timer runs the offline check"""
        self._skip_if_not_loaded()

        now_ms = self.botengine.get_timestamp()

        device = MagicMock()
        device.device_id = "device_1"
        device.description = "Sensor"
        device.device_type = 10071
        device.last_updated_ms = now_ms - (5 * utilities.ONE_HOUR_MS)

        self.location_object.devices = {"device_1": device}
        self.location_object.intelligence_modules[
            "intelligence.reports.location_reports_microservice"
        ] = MagicMock()

        self.mut.timer_fired(self.botengine, TIMER_REFERENCE_CHECK_DEVICES)

        mock_send.assert_called_once()
        self.assertIn("device_1", self.mut.offline_concerns)

    def test_timer_fired_ignores_other_references(self):
        """Test that timer_fired ignores unrelated timer references"""
        self._skip_if_not_loaded()

        # Should not raise or check devices
        self.mut.timer_fired(self.botengine, "SOME_OTHER_TIMER")
        self.assertEqual(len(self.mut.offline_concerns), 0)

    @patch("signals.report.send_org_report")
    @patch("utilities.utilities.good_enough_unique_id", return_value="abccrit")
    def test_severity_critical_over_24h(self, mock_uid, mock_send):
        """Test that devices offline > 24 hours get critical priority"""
        self._skip_if_not_loaded()

        now_ms = self.botengine.get_timestamp()

        device = MagicMock()
        device.device_id = "device_1"
        device.description = "Sensor"
        device.device_type = 10071
        device.last_updated_ms = now_ms - (25 * utilities.ONE_HOUR_MS)

        self.location_object.devices = {"device_1": device}
        self.location_object.intelligence_modules[
            "intelligence.reports.location_reports_microservice"
        ] = MagicMock()

        self.mut._check_offline_devices(self.botengine)

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        # priority is the 3rd positional arg or keyword
        if call_kwargs.kwargs.get("priority"):
            self.assertEqual(call_kwargs.kwargs["priority"], "critical")
        elif len(call_kwargs.args) > 2:
            self.assertEqual(call_kwargs.args[2], "critical")

    @patch("signals.report.send_org_report")
    def test_send_concern_no_report_service(self, mock_send):
        """Test that concern is not sent if report service is unavailable"""
        self._skip_if_not_loaded()

        device = MagicMock()
        device.device_id = "device_1"

        # Ensure no report service
        if (
            "intelligence.reports.location_reports_microservice"
            in self.location_object.intelligence_modules
        ):
            del self.location_object.intelligence_modules[
                "intelligence.reports.location_reports_microservice"
            ]

        self.mut._send_device_concern(self.botengine, device, 1000)

        mock_send.assert_not_called()
        self.assertNotIn("device_1", self.mut.offline_concerns)

    @patch("signals.report.send_org_report")
    def test_send_resolution_no_report_service(self, mock_send):
        """Test that resolution is not sent if report service is unavailable"""
        self._skip_if_not_loaded()

        device = MagicMock()
        device.device_id = "device_1"

        self.mut.offline_concerns["device_1"] = {
            "report_id": "r1",
            "offline_since_ms": 1000,
        }

        if (
            "intelligence.reports.location_reports_microservice"
            in self.location_object.intelligence_modules
        ):
            del self.location_object.intelligence_modules[
                "intelligence.reports.location_reports_microservice"
            ]

        self.mut._send_device_resolution(self.botengine, device)

        mock_send.assert_not_called()
        # Concern should still be tracked since resolution wasn't sent
        self.assertIn("device_1", self.mut.offline_concerns)
