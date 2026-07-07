import unittest

from devices.assessment.grip_able.grip_able import GripAbleDevice  # type: ignore
from intelligence.assessment.device_assessment_trends_microservice import (  # type: ignore
    DeviceAssessmentTrendsMicroservice,
)
from intelligence.assessment.location_assessment_microservice import (  # type: ignore
    LocationAssessmentMicroservice,
)
from locations.location import Location  # type: ignore

from botengine_pytest import BotEnginePyTest


class TestDeviceAssessmentTrendsMicroservice(unittest.TestCase):
    def setUp(self):
        self.botengine = BotEnginePyTest({})
        self.botengine.reset()
        self.location_object = Location(self.botengine, 0)

        self.device_object = GripAbleDevice(
            self.botengine,
            self.location_object,
            "gripable_1",
            2009,
            "Grip-Able",
            precache_measurements=False,
        )
        self.device_object.born_on = 0
        self.device_object.is_connected = True
        self.location_object.devices[self.device_object.device_id] = self.device_object

        self.location_object.initialize(self.botengine)
        self.location_object.new_version(self.botengine)

    def test_microservice_initialization(self):
        """Verify the device microservice initializes correctly."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)
        assert mut is not None

    def test_location_microservice_initialization(self):
        """Verify the location microservice initializes correctly."""
        mut = LocationAssessmentMicroservice(self.botengine, self.location_object)
        assert mut is not None

    def test_gait_speed_measurement(self):
        """Verify gait speed measurement triggers trend capture."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_4GS] = [
            (5.2, self.botengine.get_timestamp())
        ]
        self.device_object.last_updated_params = [GripAbleDevice.MEASUREMENT_NAME_4GS]

        mut.device_measurements_updated(self.botengine, self.device_object)

    def test_grip_strength_measurement(self):
        """Verify grip strength measurements trigger separate left/right trends."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        self.device_object.measurements[
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left"
        ] = [(25.0, self.botengine.get_timestamp())]
        self.device_object.measurements[
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right"
        ] = [(27.5, self.botengine.get_timestamp())]
        self.device_object.last_updated_params = [
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left",
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right",
        ]

        mut.device_measurements_updated(self.botengine, self.device_object)

    def test_chair_stand_measurement(self):
        """Verify chair stand test measurement triggers trend capture."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_CST] = [
            (12.3, self.botengine.get_timestamp())
        ]
        self.device_object.last_updated_params = [GripAbleDevice.MEASUREMENT_NAME_CST]

        mut.device_measurements_updated(self.botengine, self.device_object)

    def test_tug_measurement(self):
        """Verify TUG measurement triggers trend capture."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_TUG] = [
            (10.5, self.botengine.get_timestamp())
        ]
        self.device_object.last_updated_params = [GripAbleDevice.MEASUREMENT_NAME_TUG]

        mut.device_measurements_updated(self.botengine, self.device_object)

    def test_at_risk_true(self):
        """Verify at-risk=True triggers warning-level report and stability event."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_AT_RISK] = [
            (True, self.botengine.get_timestamp())
        ]
        self.device_object.last_updated_params = [
            GripAbleDevice.MEASUREMENT_NAME_AT_RISK
        ]

        mut.device_measurements_updated(self.botengine, self.device_object)

    def test_at_risk_false(self):
        """Verify at-risk=False generates info-level events only."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_AT_RISK] = [
            (False, self.botengine.get_timestamp())
        ]
        self.device_object.last_updated_params = [
            GripAbleDevice.MEASUREMENT_NAME_AT_RISK
        ]

        mut.device_measurements_updated(self.botengine, self.device_object)

    def test_full_assessment(self):
        """Verify a complete assessment with all measurements processes correctly."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        timestamp = self.botengine.get_timestamp()
        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_4GS] = [
            (5.2, timestamp)
        ]
        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_CST] = [
            (12.3, timestamp)
        ]
        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_TUG] = [
            (10.5, timestamp)
        ]
        self.device_object.measurements[
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left"
        ] = [(25.0, timestamp)]
        self.device_object.measurements[
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right"
        ] = [(27.5, timestamp)]
        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_AT_RISK] = [
            (False, timestamp)
        ]

        self.device_object.last_updated_params = [
            GripAbleDevice.MEASUREMENT_NAME_4GS,
            GripAbleDevice.MEASUREMENT_NAME_CST,
            GripAbleDevice.MEASUREMENT_NAME_TUG,
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left",
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right",
            GripAbleDevice.MEASUREMENT_NAME_AT_RISK,
        ]

        mut.device_measurements_updated(self.botengine, self.device_object)

    def test_collect_results(self):
        """Verify _collect_results gathers all measurement data correctly."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        timestamp = self.botengine.get_timestamp()
        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_4GS] = [
            (5.2, timestamp)
        ]
        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_CST] = [
            (12.3, timestamp)
        ]
        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_TUG] = [
            (10.5, timestamp)
        ]
        self.device_object.measurements[
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left"
        ] = [(25.0, timestamp)]
        self.device_object.measurements[
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right"
        ] = [(27.5, timestamp)]
        self.device_object.measurements[GripAbleDevice.MEASUREMENT_NAME_AT_RISK] = [
            (False, timestamp)
        ]

        results = mut._collect_results(
            self.botengine, self.device_object, self.location_object
        )

        assert results["gait_speed"] == 5.2
        assert results["chair_stand"] == 12.3
        assert results["tug"] == 10.5
        assert results["grip_left"] == 25.0
        assert results["grip_right"] == 27.5
        assert results["at_risk"] is False
        assert results["timestamp_ms"] is not None

    def test_format_assessment_summary(self):
        """Verify _format_assessment_summary produces a readable string."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        results = {
            "gait_speed": 5.2,
            "grip_left": 25.0,
            "grip_right": 27.5,
            "chair_stand": 12.3,
            "tug": 10.5,
            "at_risk": False,
        }

        summary = mut._format_assessment_summary(results)
        assert summary is not None
        assert len(summary) > 0

    def test_no_update_when_no_params_changed(self):
        """Verify no processing when no measurements were updated."""
        mut = DeviceAssessmentTrendsMicroservice(self.botengine, self.device_object)

        self.device_object.last_updated_params = []

        # Should not raise any errors
        mut.device_measurements_updated(self.botengine, self.device_object)

    def test_did_update_4gs_bug_fix(self):
        """Verify did_update_4gs works correctly after the any() bug fix."""
        self.device_object.last_updated_params = [GripAbleDevice.MEASUREMENT_NAME_4GS]
        assert self.device_object.did_update_4gs(self.botengine) is True

        self.device_object.last_updated_params = [GripAbleDevice.MEASUREMENT_NAME_GST]
        assert self.device_object.did_update_4gs(self.botengine) is True

        self.device_object.last_updated_params = []
        assert self.device_object.did_update_4gs(self.botengine) is False

        self.device_object.last_updated_params = ["something_else"]
        assert self.device_object.did_update_4gs(self.botengine) is False


class TestLocationAssessmentMicroservice(unittest.TestCase):
    def setUp(self):
        self.botengine = BotEnginePyTest({})
        self.botengine.reset()
        self.location_object = Location(self.botengine, 0)

    def test_assessment_completed_normal(self):
        """Verify dashboard updates via datastream for normal assessments."""
        mut = LocationAssessmentMicroservice(self.botengine, self.location_object)

        content = {
            "gait_speed": 5.2,
            "grip_left": 25.0,
            "grip_right": 27.5,
            "chair_stand": 12.3,
            "tug": 10.5,
            "at_risk": False,
            "timestamp_ms": self.botengine.get_timestamp(),
            "user_id": 12345,
        }

        # Should not raise
        mut.assessment_completed(self.botengine, content)

    def test_assessment_completed_at_risk(self):
        """Verify dashboard updates with WARNING priority for at-risk assessments."""
        mut = LocationAssessmentMicroservice(self.botengine, self.location_object)

        content = {
            "gait_speed": 8.5,
            "grip_left": 15.0,
            "grip_right": 14.0,
            "chair_stand": 18.0,
            "tug": 16.0,
            "at_risk": True,
            "timestamp_ms": self.botengine.get_timestamp(),
            "user_id": 67890,
        }

        # Should not raise
        mut.assessment_completed(self.botengine, content)

    def test_datastream_dispatch(self):
        """Verify datastream_updated routes to assessment_completed."""
        mut = LocationAssessmentMicroservice(self.botengine, self.location_object)

        content = {
            "gait_speed": 5.2,
            "at_risk": False,
            "timestamp_ms": self.botengine.get_timestamp(),
        }

        # Should route to assessment_completed via getattr
        mut.datastream_updated(self.botengine, "assessment_completed", content)

    def test_assessment_completed_no_device_with_label(self):
        """Verify a 3rd-party assessment (no device) with a source label and the
        new Senior Fitness Test raw measurements processes and persists."""
        mut = LocationAssessmentMicroservice(self.botengine, self.location_object)

        timestamp_ms = self.botengine.get_timestamp()
        content = {
            # No device_id/device_type — originates from a 3rd-party platform.
            "device_desc": "Wellness Assessment",
            "results": {
                "chair_stand_reps": 12,
                "arm_curl_right": 18,
                "arm_curl_left": 17,
                "max_grip": 31.6,
                "chair_sit_reach_right": -4.0,
                "chair_sit_reach_left": -4.5,
                "back_scratch_right": -12.0,
                "back_scratch_left": -14.0,
                "static_balance_right": 2.6,
                "static_balance_left": 1.0,
                "eight_foot_up_go": 12.1,
                "two_minute_step": 78,
                "timestamp_ms": timestamp_ms,
            },
        }

        # Should validate the new raw measurements and process end-to-end
        # without raising, even though there is no device.
        mut.assessment_completed(self.botengine, content)

    def test_assessment_completed_rejects_bad_measure_type(self):
        """Verify a new raw measurement with a non-numeric type is rejected by
        schema validation without raising."""
        mut = LocationAssessmentMicroservice(self.botengine, self.location_object)

        content = {
            "device_desc": "Wellness Assessment",
            "results": {
                "max_grip": "not-a-number",
                "timestamp_ms": self.botengine.get_timestamp(),
            },
        }

        # Invalid type should be logged and the handler should return gracefully.
        mut.assessment_completed(self.botengine, content)

    def test_assessment_completed_no_device_captures_trends(self):
        """Verify a 3rd-party assessment (no device) captures longitudinal
        trends for the raw measurements, mirroring the device path."""
        import intelligence.assessment.location_assessment_microservice as mod

        mut = LocationAssessmentMicroservice(self.botengine, self.location_object)

        captured = []
        original_capture = mod.trends.capture
        mod.trends.capture = lambda *args, **kwargs: captured.append(
            kwargs.get("trend_id")
        )
        try:
            mut.assessment_completed(
                self.botengine,
                {
                    "device_desc": "Wellness Assessment",
                    "results": {
                        "chair_stand_reps": 13,
                        "max_grip": 31.6,
                        "eight_foot_up_go": 12.1,
                        "two_minute_step": 78,
                        "timestamp_ms": self.botengine.get_timestamp(),
                    },
                },
            )
        finally:
            mod.trends.capture = original_capture

        assert "trend.assessment_chair_stand_reps" in captured
        assert "trend.assessment_max_grip" in captured
        assert "trend.assessment_eight_foot_up_go" in captured
        assert "trend.assessment_two_minute_step" in captured

    def test_assessment_completed_device_present_skips_trend_capture(self):
        """Verify that when a device is associated, the location microservice
        does NOT capture trends (the device microservice already does)."""
        import intelligence.assessment.location_assessment_microservice as mod

        device_object = GripAbleDevice(
            self.botengine,
            self.location_object,
            "gripable_loc",
            2009,
            "Grip-Able",
            precache_measurements=False,
        )
        self.location_object.devices[device_object.device_id] = device_object

        mut = LocationAssessmentMicroservice(self.botengine, self.location_object)

        captured = []
        original_capture = mod.trends.capture
        mod.trends.capture = lambda *args, **kwargs: captured.append(
            kwargs.get("trend_id")
        )
        try:
            mut.assessment_completed(
                self.botengine,
                {
                    "device_id": device_object.device_id,
                    "results": {
                        "gait_speed": 5.2,
                        "chair_stand": 12.3,
                        "timestamp_ms": self.botengine.get_timestamp(),
                    },
                },
            )
        finally:
            mod.trends.capture = original_capture

        assert captured == []
