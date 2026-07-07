"""
Created on March 6, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter
"""

# Location property address for storing the location highlights JSON
HIGHLIGHTS_PROPERTY_NAME = "location_highlights"

# Element weights (order of display, lighter at top)
# These are fallback defaults; live order comes from the ppc.api.highlights.metadata system property.
WEIGHT_SLEEP = 0
WEIGHT_BATHROOM = 1
WEIGHT_SAFETY = 2
WEIGHT_OCCUPANCY = 3
WEIGHT_MEDICATION = 4
WEIGHT_DEVICES = 5

# Element IDs (match the weight order)
ELEMENT_ID_SLEEP = "sleep"
ELEMENT_ID_BATHROOM = "bathroom"
ELEMENT_ID_SAFETY = "safety"
ELEMENT_ID_OCCUPANCY = "occupancy"
ELEMENT_ID_MEDICATION = "medication"
ELEMENT_ID_DEVICES = "devices"

# Status values
PRIORITY_GRAY = 0  # Unavailable/unknown
PRIORITY_GREEN = 1  # Good/normal
PRIORITY_YELLOW = 2  # Warning/caution
PRIORITY_RED = 3  # Critical/alert