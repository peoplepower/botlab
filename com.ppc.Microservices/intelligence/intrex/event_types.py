"""
Created on June 22, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

Intrex (Rythmos by Intrex) Real Time API event types.

The Real Time API delivers alert events on the `intrex_event` data stream. Each event carries an
`eventType` enum (`AlertType`) describing what happened. The lifecycle of a single alert is:

    activation  ->  accept by staff  ->  deactivation by staff

* Activation events (base 1-37, cellular 1001-1007) arrive in this integration as device measurements
  (e.g. buttonStatus, fallStatus), not on the `intrex_event` data stream.
* Accept-by-staff events (3001-3026, suffix "AcceptedByStaff") indicate a staff member tapped "Accept"
  on an incoming alert. This range mirrors the staff-deactivation range one-for-one with a +1000 offset.
* Deactivation-by-staff events (2001-2026, suffix "DeactivationFromRythmos") indicate a staff member
  deactivated the alert.

Accept and deactivation events share the same alert `id` (P-prefixed) as the original activation, so a
full alert lifecycle can be correlated.

See docs/Real Time API V1 - Confluence.pdf for the source enumeration.

@author: Destry Teeter
"""

# ----------------------------------------------------------------------------------------------------
# AlertType (a.k.a. EventType) enumeration - mirrors the Real Time API doc verbatim
# ----------------------------------------------------------------------------------------------------

EVENT_TYPE_UNKNOWN = 0

# Base activation/deactivation events (reported as device measurements in this integration)
EVENT_TYPE_BUTTON_PRESS_ACTIVATION = 1
EVENT_TYPE_BUTTON_PRESS_DEACTIVATION = 2
EVENT_TYPE_SOFT_FALL_ACTIVATION = 3
EVENT_TYPE_HARD_FALL_ACTIVATION = 4
EVENT_TYPE_FALL_DEACTIVATION = 5
EVENT_TYPE_WANDER_ACTIVATION = 6
EVENT_TYPE_PULL_CORD_ACTIVATION = 7
EVENT_TYPE_PULL_CORD_DEACTIVATION = 8
EVENT_TYPE_WINDOW_SENSOR_OPEN = 9
EVENT_TYPE_WINDOW_SENSOR_CLOSE = 10
EVENT_TYPE_DOOR_SENSOR_OPEN = 11
EVENT_TYPE_DOOR_SENSOR_CLOSE = 12
EVENT_TYPE_SMOKE_DETECTOR_ACTIVATION = 13
EVENT_TYPE_SMOKE_DETECTOR_DEACTIVATION = 14
EVENT_TYPE_DOOR_BELL_ACTIVATION = 15
EVENT_TYPE_DOOR_BELL_DEACTIVATION = 16
EVENT_TYPE_MOTION_SENSOR_ACTIVATION = 17
EVENT_TYPE_MOTION_SENSOR_DEACTIVATION = 18
EVENT_TYPE_PRESENCE_DETECTION_SENSOR_NO_DETECTED = 19
EVENT_TYPE_PRESENCE_DETECTION_SENSOR_START = 20
EVENT_TYPE_PRESENCE_DETECTION_SENSOR_END = 21
EVENT_TYPE_ALEXA_HELP_REQUEST_ACTIVATION = 23
EVENT_TYPE_LOITERING_ACTIVATION = 24
EVENT_TYPE_LOITERING_DEACTIVATION = 25
EVENT_TYPE_GEOFENCE_KEEP_OUT = 26
EVENT_TYPE_DOOR_BREACHED = 28
EVENT_TYPE_DOOR_PROPPED = 29
EVENT_TYPE_DOOR_OPENED = 30
EVENT_TYPE_DOOR_CLOSED = 31
EVENT_TYPE_MESH_DISCONNECT = 32
EVENT_TYPE_MESH_CONNECT = 33
EVENT_TYPE_GEOFENCE_KEEP_IN = 34
EVENT_TYPE_DOOR_BREACHED_ATTEMPT = 36
EVENT_TYPE_OUT_OF_BED_ALERT = 37

# Cellular device activation/deactivation events
EVENT_TYPE_CELLULAR_BUTTON_PRESS_ACTIVATION = 1001
EVENT_TYPE_CELLULAR_BUTTON_PRESS_DEACTIVATION = 1002
EVENT_TYPE_CELLULAR_SOFT_FALL_ACTIVATION = 1003
EVENT_TYPE_CELLULAR_SOFT_FALL_DEACTIVATION = 1004
EVENT_TYPE_CELLULAR_HARD_FALL_ACTIVATION = 1005
EVENT_TYPE_CELLULAR_HARD_FALL_DEACTIVATION = 1006
EVENT_TYPE_CELLULAR_WANDER_ACTIVATION = 1007

# Deactivation by staff (from the Rythmos backend feature or app). Suffix: DeactivationFromRythmos
EVENT_TYPE_BUTTON_PRESS_DEACTIVATION_FROM_RYTHMOS = 2001
EVENT_TYPE_FALL_DEACTIVATION_FROM_RYTHMOS = 2002
EVENT_TYPE_WANDER_DEACTIVATION_FROM_RYTHMOS = 2003
EVENT_TYPE_PULL_CORD_DEACTIVATION_FROM_RYTHMOS = 2004
EVENT_TYPE_WINDOW_SENSOR_OPENED_DEACTIVATION_FROM_RYTHMOS = 2005
EVENT_TYPE_WINDOW_SENSOR_CLOSED_DEACTIVATION_FROM_RYTHMOS = 2006
EVENT_TYPE_DOOR_SENSOR_OPENED_DEACTIVATION_FROM_RYTHMOS = 2007
EVENT_TYPE_DOOR_SENSOR_CLOSED_DEACTIVATION_FROM_RYTHMOS = 2008
EVENT_TYPE_SMOKE_DETECTOR_DEACTIVATION_FROM_RYTHMOS = 2009
EVENT_TYPE_DOOR_BELL_DEACTIVATION_FROM_RYTHMOS = 2010
EVENT_TYPE_MOTION_SENSOR_DEACTIVATION_FROM_RYTHMOS = 2011
EVENT_TYPE_PRESENCE_DETECTION_SENSOR_MOTION_DEACTIVATION = 2012
EVENT_TYPE_ALEXA_HELP_REQUEST_DEACTIVATION_FROM_RYTHMOS = 2013
EVENT_TYPE_LOITERING_DEACTIVATION_FROM_RYTHMOS = 2014
EVENT_TYPE_GEOFENCE_DEACTIVATION_FROM_RYTHMOS = 2015
EVENT_TYPE_WEARABLE_REMOVED_DEACTIVATION_FROM_RYTHMOS = 2016
EVENT_TYPE_DOOR_BREACHED_DEACTIVATION_FROM_RYTHMOS = 2017
EVENT_TYPE_DOOR_PROPPED_DEACTIVATION_FROM_RYTHMOS = 2018
EVENT_TYPE_DOOR_OPENED_DEACTIVATION_FROM_RYTHMOS = 2019
EVENT_TYPE_DOOR_CLOSED_DEACTIVATION_FROM_RYTHMOS = 2020
EVENT_TYPE_INCONTINENCE_ALERT_DEACTIVATION_FROM_RYTHMOS = 2021
EVENT_TYPE_DOOR_BREACHED_ATTEMPT_DEACTIVATION_FROM_RYTHMOS = 2022
EVENT_TYPE_OUT_OF_BED_ALERT_DEACTIVATION_FROM_RYTHMOS = 2023
EVENT_TYPE_CELLULAR_BUTTON_PRESS_DEACTIVATION_FROM_RYTHMOS = 2024
EVENT_TYPE_CELLULAR_FALL_DEACTIVATION_FROM_RYTHMOS = 2025
EVENT_TYPE_CELLULAR_WANDER_DEACTIVATION_FROM_RYTHMOS = 2026

# Accept by staff - mirrors the deactivation range above with a +1000 offset. Suffix: AcceptedByStaff
EVENT_TYPE_BUTTON_PRESS_ACCEPTED_BY_STAFF = 3001
EVENT_TYPE_FALL_ACCEPTED_BY_STAFF = 3002
EVENT_TYPE_WANDER_ACCEPTED_BY_STAFF = 3003
EVENT_TYPE_PULL_CORD_ACCEPTED_BY_STAFF = 3004
EVENT_TYPE_WINDOW_SENSOR_OPENED_ACCEPTED_BY_STAFF = 3005
EVENT_TYPE_WINDOW_SENSOR_CLOSED_ACCEPTED_BY_STAFF = 3006
EVENT_TYPE_DOOR_SENSOR_OPENED_ACCEPTED_BY_STAFF = 3007
EVENT_TYPE_DOOR_SENSOR_CLOSED_ACCEPTED_BY_STAFF = 3008
EVENT_TYPE_SMOKE_DETECTOR_ACCEPTED_BY_STAFF = 3009
EVENT_TYPE_DOOR_BELL_ACCEPTED_BY_STAFF = 3010
EVENT_TYPE_MOTION_SENSOR_ACCEPTED_BY_STAFF = 3011
EVENT_TYPE_PRESENCE_DETECTION_SENSOR_MOTION_ACCEPTED_BY_STAFF = 3012
EVENT_TYPE_ALEXA_HELP_REQUEST_ACCEPTED_BY_STAFF = 3013
EVENT_TYPE_LOITERING_ACCEPTED_BY_STAFF = 3014
EVENT_TYPE_GEOFENCE_ACCEPTED_BY_STAFF = 3015
EVENT_TYPE_WEARABLE_REMOVED_ACCEPTED_BY_STAFF = 3016
EVENT_TYPE_DOOR_BREACHED_ACCEPTED_BY_STAFF = 3017
EVENT_TYPE_DOOR_PROPPED_ACCEPTED_BY_STAFF = 3018
EVENT_TYPE_DOOR_OPENED_ACCEPTED_BY_STAFF = 3019
EVENT_TYPE_DOOR_CLOSED_ACCEPTED_BY_STAFF = 3020
EVENT_TYPE_INCONTINENCE_ALERT_ACCEPTED_BY_STAFF = 3021
EVENT_TYPE_DOOR_BREACHED_ATTEMPT_ACCEPTED_BY_STAFF = 3022
EVENT_TYPE_OUT_OF_BED_ALERT_ACCEPTED_BY_STAFF = 3023
EVENT_TYPE_CELLULAR_BUTTON_PRESS_ACCEPTED_BY_STAFF = 3024
EVENT_TYPE_CELLULAR_FALL_ACCEPTED_BY_STAFF = 3025
EVENT_TYPE_CELLULAR_WANDER_ACCEPTED_BY_STAFF = 3026

# ----------------------------------------------------------------------------------------------------
# Ranges and helpers
# ----------------------------------------------------------------------------------------------------

# Staff deactivation events: 2001-2026 (suffix DeactivationFromRythmos)
STAFF_DEACTIVATION_RANGE = range(2001, 2027)

# Staff accept events: 3001-3026 (suffix AcceptedByStaff), a +1000 mirror of the deactivation range
STAFF_ACCEPT_RANGE = range(3001, 3027)

# Canonical alert "kind" shared by a deactivation/accept pair, keyed by the offset within each staff range
# (e.g. 2001 & 3001 -> "button_press", 2002 & 3002 -> "fall", ...). The offset is eventType modulo 1000.
ALERT_KIND_BY_OFFSET = {
    1: "button_press",
    2: "fall",
    3: "wander",
    4: "pull_cord",
    5: "window_sensor_opened",
    6: "window_sensor_closed",
    7: "door_sensor_opened",
    8: "door_sensor_closed",
    9: "smoke_detector",
    10: "door_bell",
    11: "motion_sensor",
    12: "presence_detection_sensor_motion",
    13: "alexa_help_request",
    14: "loitering",
    15: "geofence",
    16: "wearable_removed",
    17: "door_breached",
    18: "door_propped",
    19: "door_opened",
    20: "door_closed",
    21: "incontinence_alert",
    22: "door_breached_attempt",
    23: "out_of_bed_alert",
    24: "cellular_button_press",
    25: "cellular_fall",
    26: "cellular_wander",
}

# Alert kinds that correspond to a fall, used to route false-alarm classification into the falls trend gate
FALL_ALERT_KINDS = ("fall", "cellular_fall")


def is_staff_deactivation(event_type):
    """
    :param event_type: Intrex eventType integer
    :return: True if this is a staff deactivation event (2001-2026)
    """
    return event_type in STAFF_DEACTIVATION_RANGE


def is_staff_accept(event_type):
    """
    :param event_type: Intrex eventType integer
    :return: True if this is a staff accept event (3001-3026)
    """
    return event_type in STAFF_ACCEPT_RANGE


def alert_kind(event_type):
    """
    Return the canonical alert kind for a staff deactivation or accept event. Both 2001 and 3001 map to
    "button_press", etc. Returns "unknown" for event types outside the staff ranges or not recognized.

    :param event_type: Intrex eventType integer
    :return: Canonical alert kind string
    """
    if is_staff_deactivation(event_type) or is_staff_accept(event_type):
        return ALERT_KIND_BY_OFFSET.get(event_type % 1000, "unknown")
    return "unknown"


def is_fall_alert_kind(kind):
    """
    :param kind: Canonical alert kind string from alert_kind()
    :return: True if this alert kind represents a fall
    """
    return kind in FALL_ALERT_KINDS
