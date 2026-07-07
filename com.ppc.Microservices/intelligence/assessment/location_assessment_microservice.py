"""
Created on April 16, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

Location-level microservice for assessment device management.

Handles dashboard updates, trend category registration, and location-wide
assessment coordination. Listens for assessment signals from device microservices.
"""

import signals.dashboard as dashboard  # type: ignore
import signals.trends as trends  # type: ignore
import utilities.utilities as utilities  # type: ignore  # noqa: F401
from intelligence.intelligence import Intelligence  # type: ignore

# Dashboard header name
DASHBOARD_HEADER_NAME = "assessment_status"

# Longitudinal trend window in days for non-device assessment measurements.
# Mirrors the device assessment microservice (TREND_WINDOW_DAYS).
TREND_WINDOW_DAYS = 90


class LocationAssessmentMicroservice(Intelligence):
    """
    Location Assessment Microservice

    Coordinates assessment results at the location level:
    - Responds to assessment signals from device microservices
    - Updates dashboard headers when assessments complete
    """

    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, either a location or a device object.
        """
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        return

    def new_version(self, botengine):
        """
        New bot version deployed - re-register trend categories.
        :param botengine: BotEngine environment
        """
        pass

    # ===========================================================================
    # Datastream handlers
    # ===========================================================================

    def datastream_updated(self, botengine, address, content):
        """
        Data stream message received.
        :param botengine: BotEngine environment
        :param address: Data stream address
        :param content: Data stream content
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    def assessment_completed(self, botengine, content):
        """
        Assessment completed from a device.
        :param botengine: BotEngine environment
        :param content: Dict with assessment completion content
        """
        botengine.get_logger(f"{__name__}").info(
            ">assessment_completed() content: {}".format(
                content
            )
        )
        results = content.get("results", {})
        if not results:
            botengine.get_logger(f"{__name__}").warning(
                "<assessment_completed() missing results in content: {}".format(
                    content
                )
            )
            return
        schema = {
            "device_id": str,
            "results": dict,
        }
        results_schema = {
            "gait_speed": (int, float),
            "tug": (int, float),
            "chair_stand": (int, float),
            "grip_left": (int, float),
            "grip_right": (int, float),
            "at_risk": bool,
            "user_id": int,
            "timestamp_ms": int,
            # Senior Fitness Test raw measurements (e.g. from a wellness assessment).
            # chair_stand_reps (count) is distinct from chair_stand (GripAble seconds).
            "chair_stand_reps": (int, float),
            "arm_curl_right": (int, float),
            "arm_curl_left": (int, float),
            "max_grip": (int, float),
            "chair_sit_reach_right": (int, float),
            "chair_sit_reach_left": (int, float),
            "back_scratch_right": (int, float),
            "back_scratch_left": (int, float),
            "static_balance_right": (int, float),
            "static_balance_left": (int, float),
            "eight_foot_up_go": (int, float),
            "two_minute_step": (int, float),
        }
        try:
            if not isinstance(content, dict):
                botengine.get_logger(f"{__name__}").error(
                    "<assessment_completed() content is not a dict: {}".format(
                        content
                    )
                )
                raise ValueError("Content must be a dict")
            if "results" not in content:
                botengine.get_logger(f"{__name__}").error(
                    "<assessment_completed() missing or invalid 'results' in content: {}".format(
                        content
                    )
                )
                raise ValueError("Content must include 'results' dict")
            for key, expected_type in schema.items():
                if key not in content:
                    botengine.get_logger(f"{__name__}").debug(
                        "|assessment_completed() missing key '{}' in content: {}".format(
                            key, content
                        )
                    )
                    continue
                if not isinstance(content[key], expected_type):
                    botengine.get_logger(f"{__name__}").warning(
                        "|assessment_completed() key '{}' has wrong type in content: {}. Expected {}, got {}.".format(
                            key, content, expected_type, type(content[key])
                        )
                    )
                    raise ValueError("Invalid content schema for {}: {}".format(key, content))
                if key == "results":
                    for result_key, result_expected_type in results_schema.items():
                        if result_key not in content["results"]:
                            botengine.get_logger(f"{__name__}").debug(
                                "|assessment_completed() missing key '{}' in results: {}".format(
                                    result_key, content["results"]
                                )
                            )
                            continue
                        if not isinstance(content["results"][result_key], result_expected_type):
                            botengine.get_logger(f"{__name__}").warning(
                                "|assessment_completed() key '{}' has wrong type in results: {}. Expected {}, got {}.".format(
                                    result_key, content["results"], result_expected_type, type(content["results"][result_key])
                                )
                            )
                            raise ValueError("Invalid results schema for {}: {}".format(result_key, content["results"]))
        except ValueError as e:
            import traceback
            botengine.get_logger(f"{__name__}").error(
                "|assessment_completed() invalid content: {}. Error: {}\n{}".format(
                    content, e, traceback.format_exc()
                )
            )
            return
        except Exception as e:
            import traceback
            botengine.get_logger(f"{__name__}").error(
                "|assessment_completed() error validating content: {}. Error: {}\n{}".format(
                    content, e, traceback.format_exc()
                )
            )
            return
        device_id = content.get("device_id")
        device_object = self.parent.devices.get(device_id) if device_id else None
        user_id = results.get("user_id")
        user = self.parent.get_user(botengine, user_id) if user_id else None
        if user:
            botengine.get_logger(f"{__name__}").info(
                "|assessment_completed() user [{}]: {}".format(
                    user_id,
                    user.full_name() if user else "Unknown User"
                )
            )
        at_risk = results.get("at_risk")
        # Source label for the dashboard: a device's description when an
        # assessment device is present, otherwise the optional label supplied by
        # a 3rd-party platform (e.g. "Wellness Assessment"), falling back to a
        # generic name when neither is available.
        source_label = (
            device_object.description
            if device_object
            else (content.get("device_desc") or _("New"))  # noqa: F821 # type: ignore
        )

        if at_risk:
            dashboard.update_dashboard_header(
                botengine,
                self.parent,
                name=DASHBOARD_HEADER_NAME,
                priority=dashboard.DASHBOARD_PRIORITY_SUBJECTIVE_WARNING,
                title=_("Fall Risk Elevated"),  # noqa: F821 # type: ignore
                comment=_("{} assessment indicates elevated fall risk for {}.").format(source_label, user.full_name() if user else _("Resident")),  # noqa: F821 # type: ignore
                icon="exclamation-triangle",
                # Process sleep quantification - continue with existing logic
                resolution_object=dashboard.oneshot_resolution_object(
                    botengine,
                    name=DASHBOARD_HEADER_NAME,
                    ack=_("Okay."),  # noqa: F821 # type: ignore
                )
            )
        else:
            dashboard.update_dashboard_header(
                botengine,
                self.parent,
                name=DASHBOARD_HEADER_NAME,
                priority=dashboard.DASHBOARD_PRIORITY_OKAY,
                title=_("Assessment Complete"),  # noqa: F821 # type: ignore
                comment=_("{} assessment completed successfully for {}.").format(source_label, user.full_name() if user else _("Resident")),  # noqa: F821 # type: ignore
                icon="hands",
                ttl_ms=utilities.ONE_HOUR_MS * 2,
            )

        # Update the TODAY card with assessment summary
        summary_parts = []
        if results.get("gait_speed") is not None:
            summary_parts.append(_("Gait: {} m/s").format(round(results["gait_speed"], 1)))  # noqa: F821 # type: ignore
        if results.get("tug") is not None:
            summary_parts.append(_("TUG: {} s").format(round(results["tug"], 1)))  # noqa: F821 # type: ignore
        if results.get("chair_stand") is not None:
            summary_parts.append(_("Chair Stand: {} s").format(round(results["chair_stand"], 1)))  # noqa: F821 # type: ignore
        if (
            results.get("grip_left") is not None
            or results.get("grip_right") is not None
        ):
            grip_parts = []
            if results.get("grip_left") is not None:
                grip_parts.append(_("L:{}kg").format(round(results["grip_left"], 1)))  # noqa: F821 # type: ignore
            if results.get("grip_right") is not None:
                grip_parts.append(_("R:{}kg").format(round(results["grip_right"], 1)))  # noqa: F821 # type: ignore
            summary_parts.append(_("Grip {}").format("/".join(grip_parts)))  # noqa: F821 # type: ignore
        # Senior Fitness Test raw measurements (e.g. from a wellness assessment)
        if results.get("chair_stand_reps") is not None:
            summary_parts.append(_("Chair Stand: {} reps").format(round(results["chair_stand_reps"], 1)))  # noqa: F821 # type: ignore
        if (
            results.get("arm_curl_right") is not None
            or results.get("arm_curl_left") is not None
        ):
            arm_curl_parts = []
            if results.get("arm_curl_left") is not None:
                arm_curl_parts.append(_("L:{}").format(round(results["arm_curl_left"], 1)))  # noqa: F821 # type: ignore
            if results.get("arm_curl_right") is not None:
                arm_curl_parts.append(_("R:{}").format(round(results["arm_curl_right"], 1)))  # noqa: F821 # type: ignore
            summary_parts.append(_("Arm Curl {} reps").format("/".join(arm_curl_parts)))  # noqa: F821 # type: ignore
        if results.get("max_grip") is not None:
            summary_parts.append(_("Max Grip: {} kg").format(round(results["max_grip"], 1)))  # noqa: F821 # type: ignore
        if results.get("eight_foot_up_go") is not None:
            summary_parts.append(_("8ft Up & Go: {} s").format(round(results["eight_foot_up_go"], 1)))  # noqa: F821 # type: ignore
        if results.get("two_minute_step") is not None:
            summary_parts.append(_("2min Step: {} steps").format(round(results["two_minute_step"], 1)))  # noqa: F821 # type: ignore
        if (
            results.get("static_balance_right") is not None
            or results.get("static_balance_left") is not None
        ):
            balance_parts = []
            if results.get("static_balance_left") is not None:
                balance_parts.append(_("L:{}s").format(round(results["static_balance_left"], 1)))  # noqa: F821 # type: ignore
            if results.get("static_balance_right") is not None:
                balance_parts.append(_("R:{}s").format(round(results["static_balance_right"], 1)))  # noqa: F821 # type: ignore
            summary_parts.append(_("Static Balance {}").format("/".join(balance_parts)))  # noqa: F821 # type: ignore
        botengine.get_logger(f"{__name__}").info(
            "|assessment_completed() summary_parts: {}".format(
                summary_parts
            )
        )
        if summary_parts:
            dashboard.set_status(
                botengine,
                self.parent,
                unique_identifier="assessment_{}".format(user.user_id if user else "resident"),
                comment=_("Assessment for {}: {}").format(user.full_name() if user else _("Resident"), ", ".join(summary_parts)),  # noqa: F821 # type: ignore
                status=dashboard.STATUS_WARNING if at_risk else dashboard.STATUS_GOOD,
                icon="hands",
                delete_timestamp_ms=botengine.get_timestamp() + utilities.ONE_HOUR_MS * 2,
            )
        

        # Persist assessment results
        self.parent.set_location_property_separately(
            botengine,
            "assessment_results",
            content,
            overwrite=True,
            timestamp_ms=results.get("timestamp_ms", botengine.get_timestamp())
        )

        # Capture longitudinal trends for non-device assessments. Device
        # assessments already capture their own trends in the device
        # microservice, so we only do this when no device is associated.
        if device_object is None:
            self._capture_assessment_trends(botengine, results, user_id)

    # ===========================================================================
    # Helpers
    # ===========================================================================

    def _capture_assessment_trends(self, botengine, results, user_id):
        """
        Capture longitudinal trends for an assessment that did not originate
        from a device (e.g. a 3rd-party wellness assessment feed). Mirrors the
        device assessment microservice's trend capture so non-device and device
        assessments produce comparable trends.

        :param botengine: BotEngine environment
        :param results: Assessment results dict (raw measurements)
        :param user_id: Resident user id, or None
        """
        # (results key, trend id, title, comment, icon, units, min_value, max_value)
        # Icons are restricted to the FontAwesome free set.
        trend_definitions = [
            ("gait_speed", "trend.assessment_gait_speed", _("Gait Speed"), _("4-Meter Gait Speed Test result."), "walking", "sec", 0, 20),  # noqa: F821 # type: ignore
            ("chair_stand", "trend.assessment_chair_stand", _("Chair Stand"), _("Chair Stand Test result."), "chair", "sec", 0, 60),  # noqa: F821 # type: ignore
            ("tug", "trend.assessment_tug", _("Timed Up and Go"), _("Timed Up and Go Test result."), "stopwatch", "sec", 0, 60),  # noqa: F821 # type: ignore
            ("grip_left", "trend.assessment_grip_left", _("Grip Strength (Left)"), _("Left hand grip strength."), "hand-fist", "kg", 0, 100),  # noqa: F821 # type: ignore
            ("grip_right", "trend.assessment_grip_right", _("Grip Strength (Right)"), _("Right hand grip strength."), "hand-fist", "kg", 0, 100),  # noqa: F821 # type: ignore
            ("chair_stand_reps", "trend.assessment_chair_stand_reps", _("Chair Stand"), _("30-Second Chair Stand repetitions."), "chair", "reps", 0, 50),  # noqa: F821 # type: ignore
            ("arm_curl_left", "trend.assessment_arm_curl_left", _("Arm Curl (Left)"), _("Left arm curl repetitions."), "dumbbell", "reps", 0, 50),  # noqa: F821 # type: ignore
            ("arm_curl_right", "trend.assessment_arm_curl_right", _("Arm Curl (Right)"), _("Right arm curl repetitions."), "dumbbell", "reps", 0, 50),  # noqa: F821 # type: ignore
            ("max_grip", "trend.assessment_max_grip", _("Max Grip"), _("Maximum grip strength."), "weight-hanging", "kg", 0, 100),  # noqa: F821 # type: ignore
            ("chair_sit_reach_left", "trend.assessment_chair_sit_reach_left", _("Chair Sit & Reach (Left)"), _("Left chair sit-and-reach distance."), "ruler-horizontal", "in", -20, 20),  # noqa: F821 # type: ignore
            ("chair_sit_reach_right", "trend.assessment_chair_sit_reach_right", _("Chair Sit & Reach (Right)"), _("Right chair sit-and-reach distance."), "ruler-horizontal", "in", -20, 20),  # noqa: F821 # type: ignore
            ("back_scratch_left", "trend.assessment_back_scratch_left", _("Back Scratch (Left)"), _("Left back-scratch reach distance."), "ruler-vertical", "in", -20, 20),  # noqa: F821 # type: ignore
            ("back_scratch_right", "trend.assessment_back_scratch_right", _("Back Scratch (Right)"), _("Right back-scratch reach distance."), "ruler-vertical", "in", -20, 20),  # noqa: F821 # type: ignore
            ("static_balance_left", "trend.assessment_static_balance_left", _("Static Balance (Left)"), _("Left-leg static balance time."), "stopwatch", "sec", 0, 60),  # noqa: F821 # type: ignore
            ("static_balance_right", "trend.assessment_static_balance_right", _("Static Balance (Right)"), _("Right-leg static balance time."), "stopwatch", "sec", 0, 60),  # noqa: F821 # type: ignore
            ("eight_foot_up_go", "trend.assessment_eight_foot_up_go", _("8-Foot Up & Go"), _("8-Foot Up-and-Go Test result."), "stopwatch", "sec", 0, 60),  # noqa: F821 # type: ignore
            ("two_minute_step", "trend.assessment_two_minute_step", _("2-Minute Step"), _("2-Minute Step Test result."), "shoe-prints", "steps", 0, 200),  # noqa: F821 # type: ignore
        ]

        # Historical/backfilled assessments carry the assessment time; align the
        # trend timestamp with it when available.
        timestamp_override_ms = results.get("timestamp_ms")

        for (
            key,
            trend_id,
            title,
            comment,
            icon,
            units,
            min_value,
            max_value,
        ) in trend_definitions:
            value = results.get(key)
            if value is None:
                continue
            trends.capture(
                botengine,
                location_object=self.parent,
                trend_id=trend_id,
                value=value,
                display_value="{} {}".format(round(value, 1), units),
                title=title,
                comment=comment,
                icon=icon,
                units=units,
                window=TREND_WINDOW_DAYS,
                once=True,
                trend_category=trends.TREND_CATEGORY_STABILITY,
                operation=trends.OPERATION_TYPE_INSTANTANEOUS,
                related_services=[],
                user_id=user_id,
                min_value=min_value,
                max_value=max_value,
                timestamp_override_ms=timestamp_override_ms,
                running_type=trends.RUNNING_TYPE_LAST,
            )