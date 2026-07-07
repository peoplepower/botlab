"""
Created on February 24, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

Location Visitor Microservice - Consolidates visitor data from multiple detection
sources (radar, motion sensors) and manages trends, dashboard service cards,
and daily report entries.

@author: Destry Teeter
"""

import signals.dailyreport as dailyreport  # type: ignore
import signals.dashboard as dashboard  # type: ignore
import signals.report as report  # type: ignore
import signals.services as services  # type: ignore
import signals.analytics as analytics  # type: ignore
import signals.trends as trends  # type: ignore
from signals.visitor import (  # type: ignore
    VISITORS_TIMESERIES_STATE_NAME,
)
import utilities.utilities as utilities  # type: ignore
from intelligence.intelligence import Intelligence  # type: ignore

# Daily Report Rollover threshold
DAILY_REPORT_VISITOR_ROLLOVER_THRESHOLD_MS = utilities.ONE_MINUTE_MS * 30

class LocationVisitorMicroservice(Intelligence):
    """
    Consolidated visitor tracking microservice that:
    - Receives visitor detection signals from radar/motion microservices
    - Maintains a timeseries state for visitor events
    - Manages trends capture for visitor/together durations
    - Generates daily report entries
    - Updates dashboard service cards
    - Sends visitor alerts when enabled
    
    Visitor Event structure: {
      "start_time_ms": int,
      "end_time_ms": int|None,
      "device_id": str|None,
      "device_description": str|None,
      "device_goal_id": str|None,
      "event": "visitor"|"together",
      "duration_ms": int|None,
      "source": "radar"|"motion"|"manual"|"ml"|None
    }
    """

    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param botengine: BotEngine environment
        :param parent: Parent object, either a location or a device object.
        """
        Intelligence.__init__(self, botengine, parent)

        # Deprecated: using timeseries states to track active visits.
        self.visitor_events = []
        self.visitor_active = False
        self.together_active = False
        self.visitor_start_ms = None
        self.together_start_ms = None
        self.daily_visitor_duration_ms = 0
        self.daily_together_duration_ms = 0
        self.visitor_count_today = 0
        self.visitor_detection_available = False

    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        return

    def destroy(self, botengine):
        """
        This device or object is getting permanently deleted - it is no longer in the user's account.
        :param botengine: BotEngine environment
        """
        for trend_id in [
            "trend.visitor",
            "trend.visitor_count",
            "trend.visitor_number_of_people",
            "trend.together",
            "trend.together_count",
            "trend.together_number_of_people",
        ]:
            trends.remove_trend(
                botengine, location_object=self.parent, trend_id=trend_id
            )
        return

    def new_version(self, botengine):
        """
        Upgraded to a new bot version
        :param botengine: BotEngine environment
        """
        return
        
    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Message Received
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Content of the message
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    def _get_previous_visits(self, botengine, visit, start_time_ms):
        """
        Get the most recent previous visit event that matches the current visit event type and device_id, if any.
        :param botengine: BotEngine environment
        :param visit: Current visit event dictionary
        :param start_time_ms: Start time of the current visit event
        :return: Tuple of (previous_visits, previous_visit_start_time_ms) or (None, None) if no previous visit found within the rollover threshold
        """

        previous_visit_start_time_ms = None
        previous_visits = []
        visits = botengine.get_timeseries_state(VISITORS_TIMESERIES_STATE_NAME, start_time_ms - utilities.ONE_HOUR_MS * 12, end_timestamp_ms=start_time_ms)
        for visit_start_time_ms in sorted(list(visits.keys()), reverse=True):
            if visit_start_time_ms == start_time_ms:
                continue
            v = visits[visit_start_time_ms]
            if (
                v.get("event") == visit.get("event") 
                and v.get("device_id") == visit.get("device_id")
            ):
                if v.get("end_time_ms") is None:
                    continue
                time_diff = abs((previous_visit_start_time_ms or start_time_ms) - v["end_time_ms"])
                if time_diff > DAILY_REPORT_VISITOR_ROLLOVER_THRESHOLD_MS:
                    continue
                botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                    "|_get_previous_visits() Found previous visit within rollover threshold: {}".format(
                        v
                    )
                )
                previous_visit_start_time_ms = min(previous_visit_start_time_ms, visit_start_time_ms) if previous_visit_start_time_ms is not None else visit_start_time_ms
                previous_visits.append(v)

        return previous_visits or None, previous_visit_start_time_ms

    # =========================================================================
    # Signal Handlers - Receives visitor signals
    # =========================================================================

    def did_start_detecting_visitor(self, botengine, content):
        """
        Signal received that 2 or more people are reliably detected in the home.

        Expected content: {
            "start_time_ms": int,
            "event": "visitor"|"together",
            "number_of_visitors": int,
            "device_ids": list|None,
            "source": "radar"|"motion"|"manual"|"ml"|None
        }
        :param botengine: BotEngine environment
        :param content: Content dictionary
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">did_start_detecting_visitor()"
        )
        if "start_time_ms" not in content:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "<did_start_detecting_visitor() Missing 'start_time_ms': {}".format(
                    content
                )
            )
            return

        if content["start_time_ms"] is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "<did_start_detecting_visitor() 'start_time_ms' is None: {}".format(
                    content
                )
            )
            return
        
        start_time_ms = content["start_time_ms"]
        device_ids = content.get("device_ids")
        source = content.get("source")
        event = content.get("event", "visitor")
        number_of_visitors = content.get("number_of_visitors")

        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|did_start_detecting_visitor() Starting '{}' at {} from source '{}' with device_ids='{}', number_of_visitors={}".format(
                event,
                start_time_ms,
                source,
                device_ids,
                number_of_visitors,
            )
        )
        visit = botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, start_time_ms)

        if visit is None:
            visit = {}
        
        if device_ids:
            visit["device_ids"] = list(set(device_ids + visit.get("device_ids", [])))
            visit["devices"] = []
            for device_id in visit["device_ids"]:
                device_object = self.parent.devices.get(device_id)
                if device_object:
                    visit["devices"].append({
                        "device_id": device_id,
                        "description": device_object.description,
                        "goal_id": device_object.goal_id
                    })
                    break
        if source:
            visit["source"] = source
        visit["event"] = event
        if number_of_visitors is not None:
            visit["number_of_visitors"] = max(number_of_visitors, visit.get("number_of_visitors", 0))

        self.parent.set_location_property_separately(
            botengine, 
            VISITORS_TIMESERIES_STATE_NAME, 
            visit, 
            timestamp_ms=start_time_ms
        )

        previous_visits, previous_visit_start_time_ms = self._get_previous_visits(botengine, visit, start_time_ms)
        daily_report_timestamp = previous_visit_start_time_ms or start_time_ms
        self._add_daily_report_entry(botengine, daily_report_timestamp, visit, previous_visits)

        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<did_start_detecting_visitor()"
        )

    def did_stop_detecting_visitor(self, botengine, content):
        """
        Signal received that 1 or fewer people are currently detected in the home.
        Expected content: {
            "start_time_ms": int,
            "end_time_ms": int|None, If not provided entry will be removed
        }
        :param botengine: BotEngine environment
        :param content: Content dictionary
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">did_stop_detecting_visitor()"
        )

        if "start_time_ms" not in content:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "<did_stop_detecting_visitor() Missing 'start_time_ms': {}".format(
                    content
                )
            )
            return

        if content["start_time_ms"] is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "<did_stop_detecting_visitor() 'start_time_ms' is None: {}".format(
                    content
                )
            )
            return
        
        start_time_ms = content["start_time_ms"]
        end_time_ms = content.get("end_time_ms")

        # Get existing visit state
        visit = botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, start_time_ms)
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|did_stop_detecting_visitor() Stopping visitor event '{}' at {} with end_time_ms={}".format(
            visit,
            start_time_ms,
            end_time_ms,
        ))

        if visit is None:
            # Check if the latest visit is finished, if not assume this is the end signal for the most recent visit without a start_time_ms and use that visit for analytics and reporting. This handles cases where the start signal did not include a timestamp or the timestamp was not saved correctly.
            if (
                start_time_ms == botengine.get_timestamp()
                and VISITORS_TIMESERIES_STATE_NAME in self.parent.location_properties.get("timeseries_properties", {})
            ):
                start_time_ms = self.parent.location_properties["timeseries_properties"][VISITORS_TIMESERIES_STATE_NAME]
                if start_time_ms:
                    visit = botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, start_time_ms)
                    if visit is None or "end_time_ms" in visit:
                        botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                            "<did_stop_detecting_visitor() [deprecation_warning] No open visit found for start_time_ms={}.".format(
                                start_time_ms
                            )
                        )
                        return
                else:
                    # New event, continue
                    botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                        "|did_stop_detecting_visitor() [deprecation_warning] Handled new event: {}".format(
                            content
                        )
                    )
                    visit = {
                        "event": "visitor"
                    }
            else:
                botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                    "<did_stop_detecting_visitor() No existing visit found for start_time_ms={}".format(
                        start_time_ms
                    )
                )
                return
        
        if end_time_ms is None:
            botengine.delete_state(VISITORS_TIMESERIES_STATE_NAME, start_time_ms)

            self._remove_daily_report_entry(botengine, visit)
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                "<did_stop_detecting_visitor() No 'end_time_ms' provided, entry removed for start_time_ms={}".format(
                    start_time_ms
                )
            )
            return
        visit["end_time_ms"] = end_time_ms
        visit["duration_ms"] = end_time_ms - start_time_ms

        previous_visits, previous_visit_start_time_ms = self._get_previous_visits(botengine, visit, start_time_ms)
        daily_report_timestamp = previous_visit_start_time_ms or start_time_ms

        analytics.track(botengine, self.parent, "visit_complete", properties={**visit})
        self._capture_visitor_trend(botengine, visit)
        self._add_daily_report_entry(botengine, daily_report_timestamp, visit, previous_visits)

        self.parent.set_location_property_separately(
            botengine, 
            VISITORS_TIMESERIES_STATE_NAME, 
            visit, 
            timestamp_ms=start_time_ms
        )

        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<did_stop_detecting_visitor()"
        )

    # =========================================================================
    # Integration Methods
    # =========================================================================

    def _capture_visitor_trend(self, botengine, visit):
        """
        Capture visitor duration trend.
        :param botengine: BotEngine environment
        :param visit: Visitor event dictionary
        """
        duration_ms = visit.get("duration_ms")
        if duration_ms is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "|_capture_visitor_trend() Missing 'duration_ms' in visit: {}".format(
                    visit
                )
            )
            return
        event = visit.get("event", "visitor")
        number_of_visitors = visit.get("number_of_visitors")
        if event in ["visitor"]:
            # Capture visitor duration trend
            trends.capture(
                botengine,
                location_object=self.parent,
                trend_id="trend.visitor",
                value=duration_ms,
                display_value=lambda x: _("{} minutes").format(  # noqa: F821 # type: ignore
                    int(round(x / 1000 / 60.0, 0))
                ),
                title=_("Visitors"),  # noqa: F821 # type: ignore
                comment=_(  # noqa: F821 # type: ignore
                    "Time multiple people were detected somewhere in the living space."
                ),
                icon="user-friends",
                units="ms",
                window=30,
                once=False,
                trend_category=trends.TREND_CATEGORY_SOCIAL,
                operation=trends.OPERATION_TYPE_ACCUMULATE,
                related_services=None,
                min_value=0,
                max_value=86400000,
            )
            # Capture visitor count trend
            trends.capture(
                botengine,
                location_object=self.parent,
                trend_id="trend.visitor_count",
                value=1,
                display_value=lambda x: _("{} visits").format(int(x)),  # noqa: F821 # type: ignore
                title=_("Visitor Count"),  # noqa: F821 # type: ignore
                comment=_("Number of visitor events detected today."),  # noqa: F821 # type: ignore
                icon="user-plus",
                units="count",
                window=30,
                once=False,
                trend_category=trends.TREND_CATEGORY_SOCIAL,
                operation=trends.OPERATION_TYPE_ACCUMULATE,
                related_services=None,
                min_value=0,
                max_value=100,
            )
            # Optionally capture number of visitors if provided by the detection source
            if number_of_visitors is not None:
                trends.capture(
                    botengine,
                    location_object=self.parent,
                    trend_id="trend.visitor_number_of_people",
                    value=number_of_visitors,
                    display_value=lambda x: _("{} visitors").format(int(x)),  # noqa: F821 # type: ignore
                    title=_("Number of Visitors"),  # noqa: F821 # type: ignore
                    comment=_("Number of visitors detected today, including residents and family members."),  # noqa: F821 # type: ignore
                    icon="user-plus",
                    units="count",
                    window=30,
                    once=False,
                    trend_category=trends.TREND_CATEGORY_SOCIAL,
                    operation=trends.OPERATION_TYPE_AVERAGE,
                    related_services=None,
                    min_value=0,
                    max_value=10,
                )
        if event == "together":
            # Capture together duration trend
            trends.capture(
                botengine,
                location_object=self.parent,
                trend_id="trend.together",
                value=duration_ms,
                display_value=lambda x: _("{} minutes").format(  # noqa: F821 # type: ignore
                    int(round(x / 1000 / 60.0, 0))
                ),
                title=_("Socially Together"),  # noqa: F821 # type: ignore
                comment=_("Time multiple people were together."),  # noqa: F821 # type: ignore
                icon="people-arrows",
                units="ms",
                window=30,
                once=False,
                trend_category=trends.TREND_CATEGORY_SOCIAL,
                operation=trends.OPERATION_TYPE_ACCUMULATE,
                related_services=None,
                min_value=0,
                max_value=86400000,
            )
            # Capture together count trend
            trends.capture(
                botengine,
                location_object=self.parent,
                trend_id="trend.together_count",
                value=1,
                display_value=lambda x: _("{} visits").format(int(x)),  # noqa: F821 # type: ignore
                title=_("Together Count"),  # noqa: F821 # type: ignore
                comment=_("Number of together events detected today."),  # noqa: F821 # type: ignore
                icon="user-plus",
                units="count",
                window=30,
                once=False,
                trend_category=trends.TREND_CATEGORY_SOCIAL,
                operation=trends.OPERATION_TYPE_ACCUMULATE,
                related_services=None,
                min_value=0,
                max_value=100,
            )
            # Optionally capture number of people together if provided by the detection source
            if number_of_visitors is not None:
                trends.capture(
                    botengine,
                    location_object=self.parent,
                    trend_id="trend.together_number_of_people",
                    value=number_of_visitors,
                    display_value=lambda x: _("{} people").format(int(x)),  # noqa: F821 # type: ignore
                    title=_("Number of People Together"),  # noqa: F821 # type: ignore
                    comment=_("Number of people detected together today."),  # noqa: F821 # type: ignore
                    icon="people-arrows",
                    units="count",
                    window=30,
                    once=False,
                    trend_category=trends.TREND_CATEGORY_SOCIAL,
                    operation=trends.OPERATION_TYPE_AVERAGE,
                    related_services=None,
                    min_value=0,
                    max_value=10,
                )

    def _add_daily_report_entry(self, botengine, timestamp, visit, previous_visits=None):
        """
        Add an entry to the daily report for visitor events.
        :param botengine: BotEngine environment
        :param visit: Visit json object containing event details
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">_add_daily_report_entry()"
        )
        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(
            "|_add_daily_report_entry() timestamp={} visit={} previous_visits={}".format(timestamp, visit, previous_visits)
        )
        parts = []
        event_type = visit.get("event")
        devices = visit.get("devices")
        duration_ms = visit.get("duration_ms")
        end_timestamp = visit.get("end_time_ms")
        number_of_visitors = visit.get("number_of_visitors")

        start_dt = self.parent.get_local_datetime_from_timestamp(botengine, timestamp)
        end_dt = self.parent.get_local_datetime_from_timestamp(botengine, end_timestamp)
        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(
            "|_add_daily_report_entry() start_dt={} end_dt={}".format(start_dt, end_dt)
        )

        if previous_visits:
            for previous_visit in previous_visits:
                previous_duration_ms = previous_visit.get("duration_ms", 0)
                previous_number_of_visitors = previous_visit.get("number_of_visitors")
                if previous_duration_ms:
                    duration_ms = (duration_ms or 0) + previous_duration_ms
                if previous_number_of_visitors:
                    number_of_visitors = max(number_of_visitors or 0, previous_number_of_visitors)

        if number_of_visitors is not None:
            if number_of_visitors == 1:
                parts.append(_("1 person").format(  # noqa: F821 # type: ignore
                ))
            else:
                parts.append(_("{} people").format(  # noqa: F821 # type: ignore
                    number_of_visitors,  
                ))
        if duration_ms is not None:
            duration_minutes = int(round(duration_ms / 1000 / 60.0, 0)) % 60
            duration_hours = int(round(duration_ms / 1000 / 60.0 / 60.0, 0))
            if duration_hours > 0:
                if duration_hours == 1:
                    parts.append(_("spent 1 hour"))  # noqa: F821 # type: ignore
                else:
                    parts.append(_("spent {} hours").format(duration_hours))  # noqa: F821 # type: ignore
                if duration_minutes > 0:
                    if duration_minutes == 1:
                        parts.append(_("and 1 minute"))  # noqa: F821 # type: ignore
                    else:
                        parts.append(_("and {} minutes").format(duration_minutes))  # noqa: F821 # type: ignore
            else:
                if duration_minutes > 0:
                    if duration_minutes == 1:
                        parts.append(_("spent 1 minute"))  # noqa: F821 # type: ignore
                    else:
                        parts.append(_("spent {} minutes").format(duration_minutes))  # noqa: F821 # type: ignore

        parts.append(
            _("together")   # noqa: F821 # type: ignore
            if event_type == "together" 
            else _("visiting")  # noqa: F821 # type: ignore
        )
        
        if devices:
            parts.append(_("in {}").format(utilities.list_to_string([device["description"] for device in devices])))  # noqa: F821 # type: ignore

        if duration_ms is not None:
            parts.append(_("between {} and {}").format(  # noqa: F821 # type: ignore
                utilities.strftime(start_dt, "%-I:%M %p"),
                utilities.strftime(end_dt, "%-I:%M %p"),
            ))
        else:
            parts.append(_("at {}").format(utilities.strftime(start_dt, "%-I:%M %p")))  # noqa: F821 # type: ignore

        parts[0] = parts[0].capitalize()
        comment = " ".join(parts)

        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|_add_daily_report_entry() Adding daily report entry with comment: {}".format(comment)
        )
        dailyreport.add_entry(
            botengine,
            self.parent,
            dailyreport.SECTION_ID_SOCIAL,
            comment=comment,
            identifier="visitor_event_{}".format(timestamp),
            include_timestamp=True,
        )
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<_add_daily_report_entry()"
        )