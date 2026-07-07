"""
Created on April 16, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

Assessment Signals
------------------
Signals for on-demand clinical assessments. These may originate from a connected
assessment device (e.g., GripAble Able-Assess) or from a 3rd-party platform with
no physical device (e.g., an EHR/HL7 wellness assessment feed).

When administered via a device, the assessments are administered infrequently by
staff for residents; the device is not expected to remain connected between
assessments and its user_id identifies which resident took the assessment. When
originating from a 3rd-party platform, the device is omitted and the caller may
supply an optional source label (device_desc) and/or user_id instead.

Microservices can implement the following events:
    def did_complete_assessment(self, botengine, device_object, results)
"""

# Datastream addresses
DATASTREAM_ADDRESS_ASSESSMENT_COMPLETED = "assessment_completed"

def assessment_completed(
    botengine,
    location_object,
    results,
    device_object=None,
    device_desc=None,
    user_id=None,
):
    """
    An administered assessment has been completed.

    :param botengine: BotEngine environment
    :param location_object: Location object
    :param results: Dict with assessment results. Supported keys (all optional):
        - gait_speed: 4-Meter Gait Speed in seconds (float or None)
        - grip_left: Left grip strength in kg (float or None)
        - grip_right: Right grip strength in kg (float or None)
        - chair_stand: GripAble Chair Stand Test in seconds (float or None)
        - tug: Timed Up and Go in seconds (float or None)
        - at_risk: At-risk flag (bool or None)
        - user_id: Resident user id (int or None)
        - timestamp_ms: Assessment timestamp in milliseconds
        Senior Fitness Test raw measurements (e.g. from a wellness assessment):
        - chair_stand_reps: 30-second Chair Stand in reps (int/float or None)
        - arm_curl_right / arm_curl_left: Arm Curl in reps (int/float or None)
        - max_grip: Maximum grip strength in kg (int/float or None)
        - chair_sit_reach_right / chair_sit_reach_left: in inches (int/float or None)
        - back_scratch_right / back_scratch_left: in inches (int/float or None)
        - static_balance_right / static_balance_left: in seconds (int/float or None)
        - eight_foot_up_go: 8-Foot Up-and-Go in seconds (int/float or None)
        - two_minute_step: 2-Minute Step in steps (int/float or None)
    :param device_object: Device object that performed the assessment, or None for
        assessments originating from a 3rd-party platform with no physical device
    :param device_desc: Optional source label used when device_object is None
        (e.g. "Wellness Assessment"). Ignored when device_object is provided.
    :param user_id: Optional resident user id used when device_object is None.
        Ignored when device_object is provided.
    """
    if device_object is not None:
        content = {
            "device_id": device_object.device_id,
            "device_type": device_object.device_type,
            "device_desc": device_object.description,
            "user_id": device_object.user_id,
        }
    else:
        content = {
            "device_desc": device_desc,
            "user_id": user_id,
        }
    # Sanitize message
    content = {k: v for k, v in content.items() if v is not None}
    results = {k: v for k, v in results.items() if v is not None}
    content["results"] = results

    location_object.distribute_datastream_message(
        botengine,
        DATASTREAM_ADDRESS_ASSESSMENT_COMPLETED,
        content,
        internal=True,
        external=False,
    )