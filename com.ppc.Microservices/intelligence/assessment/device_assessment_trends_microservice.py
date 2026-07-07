"""
Created on April 16, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

Device-level microservice for GripAble assessment devices.

Processes clinical assessment measurements and captures trends for longitudinal tracking.
GripAble is an on-demand assessment device used infrequently by residents for administered
clinical tests. The device is not expected to remain connected between assessments.
"""

import signals.assessment as assessment  # type: ignore
import signals.report.report as report  # type: ignore
import signals.trends as trends  # type: ignore
from devices.assessment.grip_able.grip_able import GripAbleDevice  # type: ignore
from intelligence.intelligence import Intelligence  # type: ignore
from signals.report.constants import (  # type: ignore
    CRITICALITY_INFO,
    CRITICALITY_WARNING,
    EVENT_TYPE_ASSESSMENT_CHAIR_STAND,
    EVENT_TYPE_ASSESSMENT_COMPLETED,
    EVENT_TYPE_ASSESSMENT_GAIT_SPEED,
    EVENT_TYPE_ASSESSMENT_GRIP_STRENGTH,
    EVENT_TYPE_ASSESSMENT_TUG,
    EVENT_TYPE_STABILITY_FALL_RISK,
)

# Trend window in days for longitudinal tracking of assessment results
TREND_WINDOW_DAYS = 90


class DeviceAssessmentTrendsMicroservice(Intelligence):
    """
    GripAble Assessment Trends Microservice

    Captures clinical assessment measurements as trends and generates report events.
    Each GripAble device gets its own instance of this microservice.

    Measurements processed:
    - 4-Meter Gait Speed (4GS/GST) - walking speed in seconds
    - Chair Stand Test (CST) - sit-to-stand time in seconds
    - Timed Up and Go (TUG) - mobility test in seconds
    - Single Maximum Grip Strength (SMGT) - grip force in kg (left/right)
    - At Risk flag - binary risk indicator
    """

    def __init__(self, botengine, parent):
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        return

    def device_measurements_updated(self, botengine, device_object):
        """
        Device measurements updated. Process GripAble assessment data.

        :param botengine: BotEngine environment
        :param device_object: GripAbleDevice object with updated measurements
        """
        if not isinstance(device_object, GripAbleDevice):
            return

        location_object = self.parent.location_object
        results = self._collect_results(botengine, device_object, location_object)

        # Capture trends for each updated measurement
        self._capture_gait_speed_trend(botengine, device_object, location_object)
        self._capture_grip_strength_trends(botengine, device_object, location_object)
        self._capture_chair_stand_trend(botengine, device_object, location_object)
        self._capture_tug_trend(botengine, device_object, location_object)

        # Signal assessment completion via the assessment signal module
        if any(
            param in device_object.last_updated_params
            for param in GripAbleDevice.MEASUREMENT_PARAMETERS_LIST
        ):
            report.add_event(
                botengine,
                location_object,
                event_type=EVENT_TYPE_ASSESSMENT_COMPLETED,
                comment=self._format_assessment_summary(results),
                criticality=CRITICALITY_WARNING
                if results.get("at_risk")
                else CRITICALITY_INFO,
            )

        assessment.assessment_completed(
            botengine, location_object, results, device_object=device_object
        )

    # ===========================================================================
    # Trend Capture
    # ===========================================================================

    def _capture_gait_speed_trend(self, botengine, device_object, location_object):
        """Capture 4-Meter Gait Speed trend."""
        if not device_object.did_update_4gs(botengine):
            return

        value = device_object.get_4gs(botengine)
        if value is None:
            return

        trends.capture(
            botengine,
            location_object=location_object,
            trend_id="trend.assessment_gait_speed",
            value=value,
            display_value=_("{} sec").format(round(value, 1)),  # noqa: F821 # type: ignore
            title=_("Gait Speed"),  # noqa: F821 # type: ignore
            comment=_("4-Meter Gait Speed Test result."),  # noqa: F821 # type: ignore
            icon="walking",
            units="sec",
            window=TREND_WINDOW_DAYS,
            once=True,
            trend_category=trends.TREND_CATEGORY_STABILITY,
            operation=trends.OPERATION_TYPE_INSTANTANEOUS,
            related_services=[],
            user_id=device_object.user_id,
        )

    def _capture_grip_strength_trends(self, botengine, device_object, location_object):
        """Capture grip strength trends for left and right hands."""
        if not device_object.did_update_smgt(botengine):
            return

        left = device_object.get_smgt_left(botengine)
        right = device_object.get_smgt_right(botengine)

        if left is not None and device_object.did_update_smgt_left(botengine):
            trends.capture(
                botengine,
                location_object=location_object,
                trend_id="trend.assessment_grip_left",
                value=left,
                display_value=_("{} kg").format(round(left, 1)),  # noqa: F821 # type: ignore
                title=_("Grip Strength (Left)"),  # noqa: F821 # type: ignore
                comment=_("Left hand grip strength."),  # noqa: F821 # type: ignore
                icon="hand-fist",
                units="kg",
                window=TREND_WINDOW_DAYS,
                once=True,
                trend_category=trends.TREND_CATEGORY_STABILITY,
                operation=trends.OPERATION_TYPE_INSTANTANEOUS,
                related_services=[],
                user_id=device_object.user_id,
            )

        if right is not None and device_object.did_update_smgt_right(botengine):
            trends.capture(
                botengine,
                location_object=location_object,
                trend_id="trend.assessment_grip_right",
                value=right,
                display_value=_("{} kg").format(round(right, 1)),  # noqa: F821 # type: ignore
                title=_("Grip Strength (Right)"),  # noqa: F821 # type: ignore
                comment=_("Right hand grip strength."),  # noqa: F821 # type: ignore
                icon="hand-fist",
                units="kg",
                window=TREND_WINDOW_DAYS,
                once=True,
                trend_category=trends.TREND_CATEGORY_STABILITY,
                operation=trends.OPERATION_TYPE_INSTANTANEOUS,
                related_services=[],
                user_id=device_object.user_id,
            )

    def _capture_chair_stand_trend(self, botengine, device_object, location_object):
        """Capture Chair Stand Test trend."""
        if not device_object.did_update_cst(botengine):
            return

        value = device_object.get_cst(botengine)
        if value is None:
            return

        trends.capture(
            botengine,
            location_object=location_object,
            trend_id="trend.assessment_chair_stand",
            value=value,
            display_value=_("{} sec").format(round(value, 1)),  # noqa: F821 # type: ignore
            title=_("Chair Stand"),  # noqa: F821 # type: ignore
            comment=_("Chair Stand Test result."),  # noqa: F821 # type: ignore
            icon="chair",
            units="sec",
            window=TREND_WINDOW_DAYS,
            once=True,
            trend_category=trends.TREND_CATEGORY_STABILITY,
            operation=trends.OPERATION_TYPE_INSTANTANEOUS,
            related_services=[],
            user_id=device_object.user_id,

        )

    def _capture_tug_trend(self, botengine, device_object, location_object):
        """Capture Timed Up and Go trend."""
        if not device_object.did_update_tug(botengine):
            return

        value = device_object.get_tug(botengine)
        if value is None:
            return

        trends.capture(
            botengine,
            location_object=location_object,
            trend_id="trend.assessment_tug",
            value=value,
            display_value=_("{} sec").format(round(value, 1)),  # noqa: F821 # type: ignore
            title=_("Timed Up and Go"),  # noqa: F821 # type: ignore
            comment=_("Timed Up and Go Test result."),  # noqa: F821 # type: ignore
            icon="stopwatch",
            units="sec",
            window=TREND_WINDOW_DAYS,
            once=True,
            trend_category=trends.TREND_CATEGORY_STABILITY,
            operation=trends.OPERATION_TYPE_INSTANTANEOUS,
            related_services=[],
            user_id=device_object.user_id,
        )

    # ===========================================================================
    # Helpers
    # ===========================================================================

    def _collect_results(self, botengine, device_object, location_object):
        """
        Collect all current assessment results into a dict for signal dispatch.
        :param botengine: BotEngine environment
        :param device_object: GripAbleDevice
        :param location_object: Location object
        :return: Results dict
        """
        grip_left, grip_right = device_object.get_smgt(botengine)

        return {
            "user_id": device_object.user_id,
            "gait_speed": device_object.get_4gs(botengine),
            "grip_left": grip_left,
            "grip_right": grip_right,
            "chair_stand": device_object.get_cst(botengine),
            "tug": device_object.get_tug(botengine),
            "at_risk": device_object.get_at_risk(botengine),
            "timestamp_ms": botengine.get_timestamp(),
        }

    def _format_assessment_summary(self, results):
        """
        Format a human-readable summary of assessment results.
        :param results: Results dict
        :return: Summary string
        """
        parts = []
        if results.get("gait_speed") is not None:
            parts.append(_("Gait: {} sec").format(round(results["gait_speed"], 1)))  # noqa: F821 # type: ignore
        if results.get("chair_stand") is not None:
            parts.append(
                _("Chair Stand: {} sec").format(round(results["chair_stand"], 1))  # noqa: F821 # type: ignore
            )
        if results.get("tug") is not None:
            parts.append(_("TUG: {} sec").format(round(results["tug"], 1)))  # noqa: F821 # type: ignore
        if results.get("grip_left") is not None:
            parts.append(_("Grip L: {} kg").format(round(results["grip_left"], 1)))  # noqa: F821 # type: ignore
        if results.get("grip_right") is not None:
            parts.append(_("Grip R: {} kg").format(round(results["grip_right"], 1)))  # noqa: F821 # type: ignore

        summary = ", ".join(parts) if parts else _("Assessment data received")  # noqa: F821 # type: ignore
        if results.get("at_risk"):
            summary = _("AT RISK - {}").format(summary)  # noqa: F821 # type: ignore

        return summary
