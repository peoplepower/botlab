"""
Created on May 4, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Constants for the radar_subregion_analysis organization microservice.
"""

# ----------------------------------------------------------------------
# Radar device types
# ----------------------------------------------------------------------
# Sourced from each radar device class's DEVICE_TYPES attribute.
DEVICE_TYPE_VAYYAR = 2000
DEVICE_TYPE_PONTOSENSE = 2007
DEVICE_TYPE_ASSURE = 2020

RADAR_DEVICE_TYPES = [
    DEVICE_TYPE_VAYYAR,
    DEVICE_TYPE_PONTOSENSE,
    DEVICE_TYPE_ASSURE,
]

DEVICE_TYPE_NAMES = {
    DEVICE_TYPE_VAYYAR: "Vayyar",
    DEVICE_TYPE_PONTOSENSE: "Pontosense",
    DEVICE_TYPE_ASSURE: "Assure",
}

# ----------------------------------------------------------------------
# Pipeline state
# ----------------------------------------------------------------------
STATE_VAR_ANALYSIS_IN_PROGRESS = "radar_subregion_analysis_in_progress"

DATA_REQUEST_REFERENCE_DEVICES = "radar_subregion_analysis_devices"

PHASE_DEVICES = "devices"

# Timer scaffolding (mirrors device_analysis)
TIMER_TYPE_DATA_REQUEST_TIMEOUT = "data_request_timeout"
DATA_REQUEST_TIMEOUT_S = 10
MAX_DATA_REQUEST_RETRIES = 6

# ----------------------------------------------------------------------
# Location state names that together describe the radar configuration.
# Written by the location-side radar microservices, read at the org level
# via `botengine.get_state(name, location_id=...)`.
# ----------------------------------------------------------------------
STATE_NAME_RADAR_ROOM = "radar_room"
STATE_NAME_RADAR_SUBREGIONS = "radar_subregions"
STATE_NAME_RADAR_SUBREGION_BEHAVIORS = "radar_subregion_behaviors"

# ----------------------------------------------------------------------
# Mounting types (from RadarDevice.SENSOR_MOUNTING_*)
# ----------------------------------------------------------------------
MOUNTING_TYPE_WALL = 0
MOUNTING_TYPE_CEILING = 1
MOUNTING_TYPE_CEILING_45 = 2
MOUNTING_TYPE_WALL_45 = 3
MOUNTING_TYPE_CORNER = 4

MOUNTING_TYPE_NAMES = {
    MOUNTING_TYPE_WALL: "Wall",
    MOUNTING_TYPE_CEILING: "Ceiling",
    MOUNTING_TYPE_CEILING_45: "Ceiling 45°",
    MOUNTING_TYPE_WALL_45: "Wall 45°",
    MOUNTING_TYPE_CORNER: "Corner",
}

# ----------------------------------------------------------------------
# Subregion contexts (mirrors signals/radar.py SUBREGION_CONTEXT_*)
# ----------------------------------------------------------------------
CONTEXT_IGNORE = -1
CONTEXT_BED = 0
CONTEXT_BED_KING = 1
CONTEXT_BED_CALKING = 2
CONTEXT_BED_QUEEN = 3
CONTEXT_BED_FULL = 4
CONTEXT_BED_TWINXL = 5
CONTEXT_BED_TWIN = 6
CONTEXT_BED_CRIB = 7
CONTEXT_END_TABLE = 8
CONTEXT_CPAP = 9
CONTEXT_BATHROOM = 10
CONTEXT_TOILET = 11
CONTEXT_BATHTUB = 12
CONTEXT_WALK_IN_SHOWER = 13
CONTEXT_SINK = 14
CONTEXT_TOILET_TANK = 15
CONTEXT_CHAIR = 20
CONTEXT_COUCH = 22
CONTEXT_TABLE = 23
CONTEXT_OTHER = 99
CONTEXT_EXIT = 100

CONTEXT_NAMES = {
    CONTEXT_IGNORE: "Ignore",
    CONTEXT_BED: "Bed",
    CONTEXT_BED_KING: "King Bed",
    CONTEXT_BED_CALKING: "Cal King Bed",
    CONTEXT_BED_QUEEN: "Queen Bed",
    CONTEXT_BED_FULL: "Full Bed",
    CONTEXT_BED_TWINXL: "Twin XL Bed",
    CONTEXT_BED_TWIN: "Twin Bed",
    CONTEXT_BED_CRIB: "Crib",
    CONTEXT_END_TABLE: "End Table",
    CONTEXT_CPAP: "CPAP",
    CONTEXT_BATHROOM: "Bathroom",
    CONTEXT_TOILET: "Toilet",
    CONTEXT_BATHTUB: "Bathtub",
    CONTEXT_WALK_IN_SHOWER: "Walk-in Shower",
    CONTEXT_SINK: "Sink",
    CONTEXT_TOILET_TANK: "Toilet Tank",
    CONTEXT_CHAIR: "Chair",
    CONTEXT_COUCH: "Couch",
    CONTEXT_TABLE: "Table",
    CONTEXT_OTHER: "Other",
    CONTEXT_EXIT: "Exit",
}

# Color palette extends the one from animate_occupancy_targets.py.
_BED_COLOR = "#4A90E2"
_BATHROOM_COLOR = "#9B59B6"
_TOILET_COLOR = "#8E44AD"
_SHOWER_COLOR = "#1ABC9C"
_CHAIR_COLOR = "#F5A623"
_COUCH_COLOR = "#7ED321"
_TABLE_COLOR = "#50E3C2"
_OTHER_COLOR = "#BD10E0"
_EXIT_COLOR = "#E74C3C"
_IGNORE_COLOR = "#BDC3C7"

CONTEXT_COLORS = {
    CONTEXT_IGNORE: _IGNORE_COLOR,
    CONTEXT_BED: _BED_COLOR,
    CONTEXT_BED_KING: _BED_COLOR,
    CONTEXT_BED_CALKING: _BED_COLOR,
    CONTEXT_BED_QUEEN: _BED_COLOR,
    CONTEXT_BED_FULL: _BED_COLOR,
    CONTEXT_BED_TWINXL: _BED_COLOR,
    CONTEXT_BED_TWIN: _BED_COLOR,
    CONTEXT_BED_CRIB: _BED_COLOR,
    CONTEXT_END_TABLE: "#3498DB",
    CONTEXT_CPAP: "#2980B9",
    CONTEXT_BATHROOM: _BATHROOM_COLOR,
    CONTEXT_TOILET: _TOILET_COLOR,
    CONTEXT_BATHTUB: _SHOWER_COLOR,
    CONTEXT_WALK_IN_SHOWER: _SHOWER_COLOR,
    CONTEXT_SINK: "#16A085",
    CONTEXT_TOILET_TANK: _TOILET_COLOR,
    CONTEXT_CHAIR: _CHAIR_COLOR,
    CONTEXT_COUCH: _COUCH_COLOR,
    CONTEXT_TABLE: _TABLE_COLOR,
    CONTEXT_OTHER: _OTHER_COLOR,
    CONTEXT_EXIT: _EXIT_COLOR,
}

DEFAULT_CONTEXT_COLOR = "#888888"


def context_name(context_id):
    """Return a human-friendly label for a subregion context_id."""
    return CONTEXT_NAMES.get(context_id, "Other")


def context_color(context_id):
    """Return the chart color for a subregion context_id."""
    return CONTEXT_COLORS.get(context_id, DEFAULT_CONTEXT_COLOR)


def device_type_name(device_type):
    """Return a human-friendly label for a radar device type integer."""
    return DEVICE_TYPE_NAMES.get(device_type, f"Type {device_type}")


def mounting_type_name(mounting_type):
    """Return a human-friendly label for a mounting_type integer."""
    return MOUNTING_TYPE_NAMES.get(mounting_type, f"Type {mounting_type}")


# ----------------------------------------------------------------------
# Default room (used when a device has never published its 'room' property).
# Values mirror RadarDevice.X_MIN_METERS_WALL et al.
# ----------------------------------------------------------------------
DEFAULT_ROOM = {
    "x_min_meters": -3.0,
    "x_max_meters": 2.0,
    "y_min_meters": 0.3,
    "y_max_meters": 4.0,
    "z_min_meters": 0.0,
    "z_max_meters": 2.0,
    "mounting_type": MOUNTING_TYPE_WALL,
    "sensor_height_m": 1.5,
}
