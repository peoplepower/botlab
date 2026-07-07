"""
Created on February 24, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter
"""

import unittest
from unittest.mock import patch

from signals.visitor import (  # type: ignore
    VISITORS_TIMESERIES_STATE_NAME
)
from signals.dailyreport import (  # type: ignore
    SECTION_ID_SOCIAL
)
from signals.report import (  # type: ignore
    EVENT_TYPE_SOCIAL_VISITOR
)

from intelligence.visitors.location_visitor_microservice import (
    DAILY_REPORT_VISITOR_ROLLOVER_THRESHOLD_MS
)

from locations.location import Location  # type: ignore
import utilities.utilities as utilities  # type: ignore

from botengine_pytest import BotEnginePyTest


class TestLocationVisitorMicroservice(unittest.TestCase):
    """Test cases for LocationVisitorMicroservice"""

    def setUp(self):
        """Set up test fixtures"""
        self.botengine = BotEnginePyTest({})
        self.location_object = Location(self.botengine, 0)
        self.location_object.initialize(self.botengine)
        self.location_object.new_version(self.botengine)

        # Get the microservice under test
        self.mut = self.location_object.intelligence_modules.get(
            "intelligence.visitors.location_visitor_microservice"
        )

    def test_initialization(self):
        """Test that microservice initializes with correct default state"""
        if self.mut is None:
            self.skipTest("Visitors microservice not loaded")

        self.assertIsNotNone(self.mut)

    def test_did_start_detecting_visitor(self):
        """Test visitor start detection signal handling"""
        if self.mut is None:
            self.skipTest("Visitors microservice not loaded")

        self.mut.did_start_detecting_visitor(self.botengine, content={"start_time_ms": self.botengine.get_timestamp()})

        visit = self.botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, timestamp_ms=self.botengine.get_timestamp())
        self.assertEqual(visit, {"event": "visitor"})

    def test_did_start_detecting_visitor_already_active(self):
        """Test that duplicate start signals are ignored"""
        if self.mut is None:
            self.skipTest("Visitors microservice not loaded")

        self.mut.did_start_detecting_visitor(self.botengine, content={"start_time_ms": self.botengine.get_timestamp()})
        
        self.botengine.set_timestamp(self.botengine.get_timestamp() + 1000)
        self.mut.did_start_detecting_visitor(self.botengine, content={"start_time_ms": self.botengine.get_timestamp()})
        visit_1 = self.botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, timestamp_ms=self.botengine.get_timestamp() - 1000)
        visit_2 = self.botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, timestamp_ms=self.botengine.get_timestamp())
        self.assertEqual(visit_1, {"event": "visitor"})
        self.assertEqual(visit_2, {"event": "visitor"})

    def test_did_stop_detecting_visitor(self):
        """Test visitor stop detection signal handling"""
        if self.mut is None:
            self.skipTest("Visitors microservice not loaded")
        
        # self.botengine.logging_service_names = ["visitors"] # Uncomment to enable logging

        # Set up active visitor state
        self.mut.did_start_detecting_visitor(self.botengine, content={"start_time_ms": self.botengine.get_timestamp()})
        self.botengine.add_timestamp(3600000)  # 1 hour later

        with patch("signals.trends.capture") as mock_capture:
            self.mut.did_stop_detecting_visitor(self.botengine, content={"start_time_ms": self.botengine.get_timestamp() - 3600000, "end_time_ms": self.botengine.get_timestamp()})

            visit = self.botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, timestamp_ms=self.botengine.get_timestamp() - 3600000)
            self.assertEqual(visit, {"event": "visitor", "end_time_ms": self.botengine.get_timestamp(), "duration_ms": 3600000})
            mock_capture.assert_called()

    def test_did_stop_detecting_visitor_not_active(self):
        """Test that stop signal is ignored when not active"""
        if self.mut is None:
            self.skipTest("Visitors microservice not loaded")

        self.mut.did_stop_detecting_visitor(self.botengine, content={"start_time_ms": self.botengine.get_timestamp(), "end_time_ms": self.botengine.get_timestamp()})

        visit = self.botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, timestamp_ms=self.botengine.get_timestamp())
        self.assertIsNone(visit)

    def test_did_stop_detecting_visitor_daily_report(self):
        """Test that stop signal is ignored when not active"""
        if self.mut is None:
            self.skipTest("Visitors microservice not loaded")

        # self.botengine.logging_service_names = ["visitors"] # Uncomment to enable logging
        
        start_time_ms = self.botengine.get_timestamp()
        self.mut.did_start_detecting_visitor(self.botengine, content={"start_time_ms": start_time_ms, "number_of_visitors": 2})
        
        self.botengine.add_timestamp(3600000)  # 1 hour later

        with patch("signals.report.add_event") as mock_capture:
            self.mut.did_stop_detecting_visitor(self.botengine, content={"start_time_ms": start_time_ms, "end_time_ms": self.botengine.get_timestamp()})

            visit = self.botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, timestamp_ms=start_time_ms)
            self.assertEqual(visit, {"event": "visitor", "number_of_visitors": 2, "end_time_ms": self.botengine.get_timestamp(), "duration_ms": 3600000})
            mock_capture.assert_called()
            mock_capture.assert_called_with(
                self.botengine,
                self.location_object,
                event_type=EVENT_TYPE_SOCIAL_VISITOR,
                comment="2 people spent 1 hour visiting between 12:00 PM and 1:00 PM",
                timestamp_override_ms=None,
                identifier=f"visitor_event_{start_time_ms}",
            )
        for i in range(1,3):
            # Test report entry updates previous entry if within DAILY_REPORT_VISITOR_ROLLOVER_THRESHOLD_MS milliseconds
            self.botengine.add_timestamp(DAILY_REPORT_VISITOR_ROLLOVER_THRESHOLD_MS)

            next_start_time_ms = self.botengine.get_timestamp()

            self.mut.did_start_detecting_visitor(self.botengine, content={"start_time_ms": next_start_time_ms})

            self.botengine.add_timestamp(3600000)  # 1 hour later
            with patch("signals.report.add_event") as mock_capture:
                self.mut.did_stop_detecting_visitor(self.botengine, content={"start_time_ms": next_start_time_ms, "end_time_ms": self.botengine.get_timestamp()})

                visit = self.botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, timestamp_ms=next_start_time_ms)
                self.assertEqual(visit, {"event": "visitor", "end_time_ms": self.botengine.get_timestamp(), "duration_ms": 3600000})

                start_dt = self.mut.parent.get_local_datetime_from_timestamp(self.botengine, start_time_ms)
                end_dt = self.mut.parent.get_local_datetime_from_timestamp(self.botengine, self.botengine.get_timestamp())
                comment = _("between {} and {}").format(  # noqa: F821 # type: ignore
                    utilities.strftime(start_dt, "%-I:%M %p"),
                    utilities.strftime(end_dt, "%-I:%M %p"),
                )
                mock_capture.assert_called()
                mock_capture.assert_called_with(
                    self.botengine,
                    self.location_object,
                    event_type=EVENT_TYPE_SOCIAL_VISITOR,
                    comment="2 people spent {} hours visiting {}".format(i+1, comment),
                    timestamp_override_ms=None,
                    identifier=f"visitor_event_{start_time_ms}",
                )
        
        # Test that a new report entry is created if the next visit starts after DAILY_REPORT_VISITOR_ROLLOVER_THRESHOLD_MS milliseconds
        self.botengine.add_timestamp(DAILY_REPORT_VISITOR_ROLLOVER_THRESHOLD_MS + 1000)
        
        start_time_ms = self.botengine.get_timestamp()
        self.mut.did_start_detecting_visitor(self.botengine, content={"start_time_ms": start_time_ms})
        
        self.botengine.add_timestamp(3600000)  # 1 hour later

        with patch("signals.report.add_event") as mock_capture:
            self.mut.did_stop_detecting_visitor(self.botengine, content={"start_time_ms": start_time_ms, "end_time_ms": self.botengine.get_timestamp()})

            visit = self.botengine.get_state(VISITORS_TIMESERIES_STATE_NAME, timestamp_ms=start_time_ms)
            self.assertEqual(visit, {"event": "visitor", "end_time_ms": self.botengine.get_timestamp(), "duration_ms": 3600000})
            mock_capture.assert_called()
            mock_capture.assert_called_with(
                self.botengine,
                self.location_object,
                event_type=EVENT_TYPE_SOCIAL_VISITOR,
                comment="Spent 1 hour visiting between 4:30 PM and 5:30 PM",
                timestamp_override_ms=None,
                identifier=f"visitor_event_{start_time_ms}",
            )



if __name__ == "__main__":
    unittest.main()
