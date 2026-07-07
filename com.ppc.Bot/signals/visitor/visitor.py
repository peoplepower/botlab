"""
Created on February 24, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

Visitor detection signals for broadcasting visitor events to microservices.

@author: Destry Teeter
"""

VISITORS_TIMESERIES_STATE_NAME = "visitors"

def did_start_detecting_visitor(botengine, location_object, start_time_ms, event="visitor", number_of_visitors=2, device_ids=None, source=None):
    """
    Signal throughout all microservices that 2 or more people are reliably detected in the home.
    Microservices can implement: did_start_detecting_visitor(self, botengine)

    :param botengine: BotEngine environment
    :param location_object: Location object
    :param start_time_ms: Timestamp of the event in milliseconds (defaults to current time if not provided)
    :param event: Optional event identifier ("visitor" or "together")
    :param device_ids: Optional list of device IDs associated with the detection
    :param source: Optional source identifier ("radar", "motion", "manual", "ml")
    """
    content = {
        "start_time_ms": start_time_ms,
        "event": event,
        "number_of_visitors": number_of_visitors,
        "source": source,
    }
    if device_ids:
        content["device_ids"] = device_ids
    content = {k: v for k, v in content.items() if v is not None}
    location_object.distribute_datastream_message(
        botengine, "did_start_detecting_visitor", content=content, internal=True, external=False
    )

def did_stop_detecting_visitor(botengine, location_object, start_time_ms, end_time_ms):
    """
    Signal throughout all microservices that 1 or fewer people are currently detected in the home.
    Microservices can implement: did_stop_detecting_visitor(self, botengine)

    :param botengine: BotEngine environment
    :param location_object: Location object
    :param start_time_ms: Timestamp of the event in milliseconds (defaults to current time if not provided)
    :param end_time_ms: Timestamp of the event in milliseconds (defaults to current time if not provided)
    :param source: Optional source identifier ("radar", "motion", "manual", "ml")
    """
    content = {
        "start_time_ms": start_time_ms,
        "end_time_ms": end_time_ms,
    }
    content = {k: v for k, v in content.items() if v is not None}
    location_object.distribute_datastream_message(
        botengine, "did_stop_detecting_visitor", content=content, internal=True, external=False
    )