"""
Created on February 24, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter
"""

import unittest
from unittest.mock import MagicMock


class TestVisitorSignals(unittest.TestCase):
    """Test cases for visitor signal functions"""

    def setUp(self):
        """Set up test fixtures"""
        self.botengine = MagicMock()
        self.botengine.get_timestamp.return_value = 1708819200000
        self.botengine.get_logger.return_value = MagicMock()

        self.location_object = MagicMock()

    def test_did_start_detecting_visitor_sends_datastream(self):
        """Test that did_start_detecting_visitor sends datastream message"""
        from signals.visitor.visitor import did_start_detecting_visitor

        did_start_detecting_visitor(self.botengine, self.location_object, start_time_ms=self.botengine.get_timestamp(), event="visitor", number_of_visitors=2, device_ids=["device1", "device2"], source="radar")

        self.location_object.distribute_datastream_message.assert_called_once()
        call_args = self.location_object.distribute_datastream_message.call_args
        self.assertEqual(call_args[0][1], "did_start_detecting_visitor")
        self.assertEqual(call_args[1]["content"]["start_time_ms"], 1708819200000)
        self.assertEqual(call_args[1]["content"]["event"], "visitor")
        self.assertEqual(call_args[1]["content"]["number_of_visitors"], 2)
        self.assertEqual(call_args[1]["content"]["device_ids"], ["device1", "device2"])
        self.assertEqual(call_args[1]["internal"], True)
        self.assertEqual(call_args[1]["external"], False)

    def test_did_stop_detecting_visitor_sends_datastream(self):
        """Test that did_stop_detecting_visitor sends datastream message"""
        from signals.visitor.visitor import did_stop_detecting_visitor

        did_stop_detecting_visitor(self.botengine, self.location_object, start_time_ms=1708819200000, end_time_ms=1708819200000)

        self.location_object.distribute_datastream_message.assert_called_once()
        call_args = self.location_object.distribute_datastream_message.call_args
        self.assertEqual(call_args[0][1], "did_stop_detecting_visitor")
        self.assertEqual(call_args[1]["content"]["start_time_ms"], 1708819200000)
        self.assertEqual(call_args[1]["content"]["end_time_ms"], 1708819200000)
        self.assertEqual(call_args[1]["internal"], True)
        self.assertEqual(call_args[1]["external"], False)


if __name__ == "__main__":
    unittest.main()
