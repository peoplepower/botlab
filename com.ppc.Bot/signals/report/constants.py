"""
Created on December 29, 2025

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss

Static constants and schema definitions for the report signal module.
See README.md for the full architecture guide.
"""

# ==============================================================================
# CATEGORY CONSTANTS
# ==============================================================================
# Categories determine organizational routing and high-level grouping

CATEGORY_WELLNESS = "wellness"
CATEGORY_IT = "it"
CATEGORY_ENERGY = "energy"
CATEGORY_SAFETY = "safety"
CATEGORY_SECURITY = "security"
CATEGORY_SOCIAL = "social"
CATEGORY_HOME = "home"
CATEGORY_CARE = "care"
CATEGORY_ALERT = "alert"
CATEGORY_TASK = "task"
CATEGORY_ACTIVITY = "activity"

# ==============================================================================
# CRITICALITY CONSTANTS
# ==============================================================================
# Criticality levels for events - affects presentation and routing priority

CRITICALITY_INFO = "info"
CRITICALITY_WARNING = "warning"
CRITICALITY_CRITICAL = "critical"

# ==============================================================================
# SENTIMENT CONSTANTS
# ==============================================================================
# Sentiment values for organizational report lifecycle tracking

SENTIMENT_CONCERN = "concern"          # New problem detected
SENTIMENT_RESOLUTION = "resolution"    # Previous problem resolved
SENTIMENT_UPDATE = "update"            # Status update on ongoing issue
SENTIMENT_CELEBRATION = "celebration"  # Positive trend worth celebrating
SENTIMENT_SUMMARY = "summary"          # Daily/weekly summary (no specific concern)

# ==============================================================================
# PRIORITY CONSTANTS
# ==============================================================================
# Priority levels for org report triage

PRIORITY_CRITICAL = "critical"         # Requires immediate attention (within 24 hours)
PRIORITY_WARNING = "warning"           # Requires attention soon (within 1-3 days)
PRIORITY_INFO = "info"                 # Informational, no immediate action required

# ==============================================================================
# REPORT ADDRESS CONSTANTS
# ==============================================================================
# Time-series state variable addresses for report storage

REPORT_ADDRESS_DAILY = "dailyreport"  # Backward compatibility
REPORT_ADDRESS_WEEKLY = "weeklyreport"
REPORT_ADDRESS_MONTHLY = "monthlyreport"

# Protected report addresses that cannot be deleted
PROTECTED_REPORT_ADDRESSES = [
    REPORT_ADDRESS_DAILY,
    REPORT_ADDRESS_WEEKLY,
    REPORT_ADDRESS_MONTHLY,
]

# ==============================================================================
# SLEEP EVENT TYPES (prefix: "sleep")
# ==============================================================================

EVENT_TYPE_SLEEP_WAKEUP = "sleep.wakeup"
EVENT_TYPE_SLEEP_BEDTIME = "sleep.bedtime"
EVENT_TYPE_SLEEP_DURATION = "sleep.duration"
EVENT_TYPE_SLEEP_QUALITY = "sleep.quality"
EVENT_TYPE_SLEEP_BATHROOM_VISIT = "sleep.bathroom_visit"
EVENT_TYPE_SLEEP_RESTLESSNESS = "sleep.restlessness"
EVENT_TYPE_SLEEP_NAP = "sleep.nap"
EVENT_TYPE_SLEEP_OUT_OF_BED = "sleep.out_of_bed"
EVENT_TYPE_SLEEP_SUMMARY = "sleep.summary"
EVENT_TYPE_SLEEP_SCORE = "sleep.score"

# ==============================================================================
# ACTIVITY EVENT TYPES (prefix: "activity")
# ==============================================================================

EVENT_TYPE_ACTIVITY_MOVEMENT = "activity.movement"
EVENT_TYPE_ACTIVITY_MOBILITY_DAILY = "activity.mobility_daily"
EVENT_TYPE_ACTIVITY_BATHROOM_VISIT = "activity.bathroom_visit"
EVENT_TYPE_ACTIVITY_MEAL = "activity.meal"
EVENT_TYPE_ACTIVITY_MEDICATION_TAKEN = "activity.medication_taken"
EVENT_TYPE_ACTIVITY_MEDICATION_MISSED = "activity.medication_missed"
EVENT_TYPE_ACTIVITY_INACTIVITY = "activity.inactivity"
EVENT_TYPE_ACTIVITY_SEDENTARY = "activity.sedentary"
EVENT_TYPE_ACTIVITY_EXERCISE = "activity.exercise"
EVENT_TYPE_ACTIVITY_SUMMARY = "activity.summary"

# ==============================================================================
# HEALTH EVENT TYPES (prefix: "health")
# ==============================================================================

EVENT_TYPE_HEALTH_FALL = "health.fall"
EVENT_TYPE_HEALTH_STABILITY_EVENT = "health.stability_event"
EVENT_TYPE_HEALTH_HEART_RATE_ALERT = "health.heart_rate_alert"
EVENT_TYPE_HEALTH_MEDICATION_NON_COMPLIANCE = "health.medication_non_compliance"
EVENT_TYPE_HEALTH_BLOOD_PRESSURE = "health.blood_pressure"
EVENT_TYPE_HEALTH_BREATHING_RATE = "health.breathing_rate"
EVENT_TYPE_HEALTH_WELLNESS_SCORE = "health.wellness_score"
EVENT_TYPE_HEALTH_CARE_SCORE = "health.care_score"
EVENT_TYPE_HEALTH_SUMMARY = "health.summary"

# ==============================================================================
# STABILITY EVENT TYPES (prefix: "stability")
# ==============================================================================
# Dedicated fall risk assessment events

EVENT_TYPE_STABILITY_SCORE = "stability.score"
EVENT_TYPE_STABILITY_FALL_RISK = "stability.fall_risk"
EVENT_TYPE_STABILITY_COMPONENT_FALLS = "stability.component_falls"
EVENT_TYPE_STABILITY_COMPONENT_SLEEP = "stability.component_sleep"
EVENT_TYPE_STABILITY_COMPONENT_MOBILITY = "stability.component_mobility"
EVENT_TYPE_STABILITY_COMPONENT_BIOMETRICS = "stability.component_biometrics"
EVENT_TYPE_STABILITY_COMPONENT_EVENTS = "stability.component_events"
EVENT_TYPE_STABILITY_SUMMARY = "stability.summary"

# ==============================================================================
# SAFETY EVENT TYPES (prefix: "safety")
# ==============================================================================

EVENT_TYPE_SAFETY_WANDERING = "safety.wandering"
EVENT_TYPE_SAFETY_UNAUTHORIZED_ACCESS = "safety.unauthorized_access"
EVENT_TYPE_SAFETY_DEVICE_TAMPERING = "safety.device_tampering"
EVENT_TYPE_SAFETY_DOOR_LEFT_OPEN = "safety.door_left_open"
EVENT_TYPE_SAFETY_WINDOW_LEFT_OPEN = "safety.window_left_open"
EVENT_TYPE_SAFETY_SMOKE_DETECTED = "safety.smoke_detected"
EVENT_TYPE_SAFETY_CARBON_MONOXIDE = "safety.carbon_monoxide"
EVENT_TYPE_SAFETY_SUMMARY = "safety.summary"

# ==============================================================================
# SECURITY EVENT TYPES (prefix: "security")
# ==============================================================================

EVENT_TYPE_SECURITY_ALARM_ACTIVATED = "security.alarm_activated"
EVENT_TYPE_SECURITY_BREAK_IN = "security.break_in"
EVENT_TYPE_SECURITY_MOTION_DETECTED = "security.motion_detected"
EVENT_TYPE_SECURITY_DOOR_UNLOCKED = "security.door_unlocked"
EVENT_TYPE_SECURITY_GARAGE_OPENED = "security.garage_opened"
EVENT_TYPE_SECURITY_CAMERA_MOTION = "security.camera_motion"
EVENT_TYPE_SECURITY_SUMMARY = "security.summary"

# ==============================================================================
# IT INFRASTRUCTURE EVENT TYPES (prefix: "it")
# ==============================================================================

EVENT_TYPE_IT_DEVICE_OFFLINE = "it.device_offline"
EVENT_TYPE_IT_CONNECTIVITY_ISSUE = "it.connectivity_issue"
EVENT_TYPE_IT_GATEWAY_PROBLEM = "it.gateway_problem"
EVENT_TYPE_IT_DEVICE_BATTERY_LOW = "it.device_battery_low"
EVENT_TYPE_IT_FIRMWARE_UPDATE = "it.firmware_update"
EVENT_TYPE_IT_NETWORK_DEGRADED = "it.network_degraded"
EVENT_TYPE_IT_SUMMARY = "it.summary"

# ==============================================================================
# ENERGY EVENT TYPES (prefix: "energy")
# ==============================================================================

EVENT_TYPE_ENERGY_HIGH_CONSUMPTION = "energy.high_consumption"
EVENT_TYPE_ENERGY_HVAC_ISSUE = "energy.hvac_issue"
EVENT_TYPE_ENERGY_THERMOSTAT_ADJUSTMENT = "energy.thermostat_adjustment"
EVENT_TYPE_ENERGY_PEAK_DEMAND = "energy.peak_demand"
EVENT_TYPE_ENERGY_DEVICE_LEFT_ON = "energy.device_left_on"
EVENT_TYPE_ENERGY_SMART_PLUG_OFFLINE = "energy.smart_plug_offline"
EVENT_TYPE_ENERGY_SUMMARY = "energy.summary"

# ==============================================================================
# SOCIAL EVENT TYPES (prefix: "social")
# ==============================================================================

EVENT_TYPE_SOCIAL_VISITOR = "social.visitor"
EVENT_TYPE_SOCIAL_TOGETHER = "social.together"  # People together in same room (co-location)
EVENT_TYPE_SOCIAL_AWAY = "social.away"
EVENT_TYPE_SOCIAL_RETURN = "social.return"
EVENT_TYPE_SOCIAL_PHONE_CALL = "social.phone_call"
EVENT_TYPE_SOCIAL_MESSAGE_RECEIVED = "social.message_received"
EVENT_TYPE_SOCIAL_SUMMARY = "social.summary"

# ==============================================================================
# TASK EVENT TYPES (prefix: "task")
# ==============================================================================

EVENT_TYPE_TASK_ADDED = "task.added"
EVENT_TYPE_TASK_COMPLETED = "task.completed"
EVENT_TYPE_TASK_OVERDUE = "task.overdue"
EVENT_TYPE_TASK_REMINDER = "task.reminder"
EVENT_TYPE_TASK_SUMMARY = "task.summary"

# ==============================================================================
# HOME EVENT TYPES (prefix: "home")
# ==============================================================================

EVENT_TYPE_HOME_WATER_LEAK = "home.water_leak"
EVENT_TYPE_HOME_HVAC_FAILURE = "home.hvac_failure"
EVENT_TYPE_HOME_APPLIANCE_ISSUE = "home.appliance_issue"
EVENT_TYPE_HOME_MAINTENANCE_REQUIRED = "home.maintenance_required"
EVENT_TYPE_HOME_DAYLIGHT_CHANGE = "home.daylight_change"
EVENT_TYPE_HOME_SUMMARY = "home.summary"

# ==============================================================================
# CARE EVENT TYPES (prefix: "care")
# ==============================================================================

EVENT_TYPE_CARE_CHECK_IN = "care.check_in"
EVENT_TYPE_CARE_REMINDER = "care.reminder"
EVENT_TYPE_CARE_WELLNESS_CHECK = "care.wellness_check"
EVENT_TYPE_CARE_SUMMARY = "care.summary"

# ==============================================================================
# FAMILY EVENT TYPES (prefix: "family")
# ==============================================================================

EVENT_TYPE_FAMILY_NOTIFICATION = "family.notification"
EVENT_TYPE_FAMILY_ALERT = "family.alert"
EVENT_TYPE_FAMILY_SUMMARY = "family.summary"

# ==============================================================================
# ALERT EVENT TYPES (prefix: "alert")
# ==============================================================================

EVENT_TYPE_ALERT_CRITICAL = "alert.critical"
EVENT_TYPE_ALERT_WARNING = "alert.warning"
EVENT_TYPE_ALERT_INFO = "alert.info"
EVENT_TYPE_ALERT_SUMMARY = "alert.summary"

# ==============================================================================
# BATHROOM EVENT TYPES (prefix: "bathroom")
# ==============================================================================

EVENT_TYPE_BATHROOM_VISIT = "bathroom.visit"
EVENT_TYPE_BATHROOM_DURATION = "bathroom.duration"
EVENT_TYPE_BATHROOM_FREQUENCY = "bathroom.frequency"
EVENT_TYPE_BATHROOM_SUMMARY = "bathroom.summary"

# ==============================================================================
# MEDICATION EVENT TYPES (prefix: "medication")
# ==============================================================================

EVENT_TYPE_MEDICATION_TAKEN = "medication.taken"
EVENT_TYPE_MEDICATION_MISSED = "medication.missed"
EVENT_TYPE_MEDICATION_REMINDER = "medication.reminder"
EVENT_TYPE_MEDICATION_SUMMARY = "medication.summary"

# ==============================================================================
# MEALS EVENT TYPES (prefix: "meals")
# ==============================================================================

# ==============================================================================
# ASSESSMENT EVENT TYPES (prefix: "assessment")
# ==============================================================================
# On-demand clinical assessment results (e.g., GripAble Able-Assess)

EVENT_TYPE_ASSESSMENT_COMPLETED = "assessment.completed"
EVENT_TYPE_ASSESSMENT_GAIT_SPEED = "assessment.gait_speed"
EVENT_TYPE_ASSESSMENT_GRIP_STRENGTH = "assessment.grip_strength"
EVENT_TYPE_ASSESSMENT_CHAIR_STAND = "assessment.chair_stand"
EVENT_TYPE_ASSESSMENT_TUG = "assessment.tug"
EVENT_TYPE_ASSESSMENT_SUMMARY = "assessment.summary"


EVENT_TYPE_MEALS_PREPARED = "meals.prepared"
EVENT_TYPE_MEALS_CONSUMED = "meals.consumed"
EVENT_TYPE_MEALS_SKIPPED = "meals.skipped"
EVENT_TYPE_MEALS_SUMMARY = "meals.summary"


# ==============================================================================
# EVENT TYPE SCHEMA
# ==============================================================================
# Maps event_type prefix to presentation and routing properties.
# All events with the same prefix share these properties and are grouped together.

EVENT_TYPE_SCHEMA = {
    # Sleep Events (prefix: "sleep")
    "sleep": {
        "category": CATEGORY_WELLNESS,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Sleep",
            "icon": "moon",
            "color": "3d597c",  # Company secondary color (calming blue-gray)
            "weight": 15,
            "description": "Sleep quality and other insightful information."
        }
    },

    # Activity Events (prefix: "activity")
    "activity": {
        "category": CATEGORY_ACTIVITY,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Activities",
            "icon": "walking",
            "color": "694fee",  # Company primary color (energizing purple)
            "weight": 20,
            "description": "Physical or leisure activities."
        }
    },

    # Mobility Events (prefix: "mobility")
    "mobility": {
        "category": CATEGORY_ACTIVITY,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Mobility",
            "icon": "walking",
            "color": "694fee",  # Company primary color
            "weight": 22,  # Between Activities (20) and Meals (25)
            "description": "Physical movement and room transitions throughout the home."
        }
    },

    # Health Events (prefix: "health")
    # FOOTGUN: this prefix is org-visible with a WARNING default. Today's add_event()
    # emitters (health.fall, health.heart_rate_alert) are event/alert-driven and pass
    # an explicit criticality, so they only reach the org on a real concern. But any
    # NEW routine health.* event added via add_event() WITHOUT an explicit criticality
    # would auto-route to the org as a warning concern for EVERY location on every run
    # -- the same flooding bug that the "stability" prefix caused with stability.score.
    # If you add a routine/daily health.* add_event, pass criticality=CRITICALITY_INFO
    # (or route it through narrate(), which does not trigger org auto-routing).
    "health": {
        "category": CATEGORY_WELLNESS,
        "default_criticality": CRITICALITY_WARNING,
        "organizational_visibility": True,
        "presentation": {
            "title": "Wellness",
            "icon": "heart",
            "color": "694fee",  # Company primary color
            "weight": -5,
            "description": "Overall physical and mental health status."
        }
    },

    # Stability Events (prefix: "stability") - Dedicated fall risk assessment
    # organizational_visibility is False: stability.* events (e.g. the daily
    # stability.score line) fire for EVERY location on every report, regardless of
    # actual risk. Auto-routing them to the org flooded the Health & Wellness Report
    # with a "stability warning" concern for every location. Genuine org escalation
    # flows through the threshold-gated _evaluate_fall_focus_for_org() path, which
    # sends report_type="fall_focus" only when the score is actually concerning.
    "stability": {
        "category": CATEGORY_WELLNESS,
        "default_criticality": CRITICALITY_WARNING,
        "organizational_visibility": False,
        "presentation": {
            "title": "Stability & Fall Risk",
            "icon": "user-injured",
            "color": "D0021B",
            "weight": 10,
            "description": "Fall risk assessment."
        }
    },

    # Safety Events (prefix: "safety")
    "safety": {
        "category": CATEGORY_SAFETY,
        "default_criticality": CRITICALITY_CRITICAL,
        "organizational_visibility": True,
        "presentation": {
            "title": "Safety",
            "icon": "shield-alt",
            "color": "D0021B",
            "weight": -10,
            "description": "Safety-related events and concerns."
        }
    },

    # Security Events (prefix: "security")
    "security": {
        "category": CATEGORY_SECURITY,
        "default_criticality": CRITICALITY_WARNING,
        "organizational_visibility": True,
        "presentation": {
            "title": "Security",
            "icon": "lock",
            "color": "D0021B",
            "weight": -8,
            "description": "Security system events and alerts."
        }
    },

    # IT Events (prefix: "it")
    "it": {
        "category": CATEGORY_IT,
        "default_criticality": CRITICALITY_WARNING,
        "organizational_visibility": True,
        "presentation": {
            "title": "System",
            "icon": "server",
            "color": "787F84",
            "weight": 50,
            "description": "IT infrastructure and device connectivity."
        }
    },

    # Energy Events (prefix: "energy")
    "energy": {
        "category": CATEGORY_ENERGY,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Energy",
            "icon": "bolt",
            "color": "F5A623",
            "weight": 45,
            "description": "Energy consumption and HVAC status."
        }
    },

    # Social Events (prefix: "social")
    "social": {
        "category": CATEGORY_SOCIAL,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Social",
            "icon": "user-friends",
            "color": "694fee",  # Company primary color
            "weight": 40,
            "description": "Interactions with friends, family, or others."
        }
    },

    # Task Events (prefix: "task")
    "task": {
        "category": CATEGORY_TASK,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Today's Tasks",
            "icon": "clipboard-list-check",
            "color": "3d597c",  # Company secondary color
            "weight": 10,
            "description": "List of to-do items scheduled for today."
        }
    },

    # Home Events (prefix: "home")
    "home": {
        "category": CATEGORY_HOME,
        "default_criticality": CRITICALITY_WARNING,
        "organizational_visibility": True,
        "presentation": {
            "title": "Home",
            "icon": "home",
            "color": "3d597c",  # Company secondary color
            "weight": 35,
            "description": "Home maintenance and appliance status."
        }
    },

    # Care Events (prefix: "care")
    "care": {
        "category": CATEGORY_CARE,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Care",
            "icon": "hand-holding-heart",
            "color": "694fee",  # Company primary color
            "weight": 25,
            "description": "Care coordination and wellness checks."
        }
    },

    # Family Events (prefix: "family")
    "family": {
        "category": CATEGORY_CARE,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Family",
            "icon": "users",
            "color": "694fee",  # Company primary color
            "weight": 42,
            "description": "Family notifications and alerts."
        }
    },

    # Alert Events (prefix: "alert")
    "alert": {
        "category": CATEGORY_ALERT,
        "default_criticality": CRITICALITY_WARNING,
        "organizational_visibility": True,
        "presentation": {
            "title": "Today's Alerts",
            "icon": "comment-exclamation",
            "color": "D0021B",
            "weight": 0,
            "description": "Urgent notifications and reminders for the day."
        }
    },

    # Bathroom Events (prefix: "bathroom")
    "bathroom": {
        "category": CATEGORY_WELLNESS,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Bathroom",
            "icon": "toilet",
            "color": "3d597c",  # Company secondary color
            "weight": 35,
            "description": "Frequency and nature of bathroom visits."
        }
    },

    # Medication Events (prefix: "medication")
    "medication": {
        "category": CATEGORY_WELLNESS,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": True,
        "presentation": {
            "title": "Medication",
            "icon": "pills",
            "color": "3d597c",  # Company secondary color
            "weight": 30,
            "description": "List of medicines taken or due today."
        }
    },

    # Assessment Events (prefix: "assessment")
    "assessment": {
        "category": CATEGORY_WELLNESS,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": True,
        "presentation": {
            "title": "Functional Assessment",
            "icon": "hands",
            "color": "694fee",  # Company primary color
            "weight": 12,  # Between Stability (10) and Sleep (15)
            "description": "On-demand clinical health assessment results."
        }
    },

    # Meals Events (prefix: "meals")
    "meals": {
        "category": CATEGORY_WELLNESS,
        "default_criticality": CRITICALITY_INFO,
        "organizational_visibility": False,
        "presentation": {
            "title": "Meals",
            "icon": "utensils",
            "color": "694fee",  # Company primary color
            "weight": 25,
            "description": "Details of food and drink consumed."
        }
    },
}
