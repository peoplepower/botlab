import json
import unittest

import utilities.utilities as utilities
from devices.assessment import GripAbleDevice as Device
from locations.location import Location

from botengine_pytest import BotEnginePyTest


class TestGripAbleDevice(unittest.TestCase):
    def test_device_grip_able(self):
        botengine = BotEnginePyTest({})
        # Clear out any previous tests
        botengine.reset()

        # Initialize the location
        location_object = Location(botengine, 0)

        device_id = "A"
        device_type = Device.DEVICE_TYPES[0]
        device_desc = "Grip-Able"

        mut = Device(
            botengine, location_object, device_id, device_type, device_desc
        )

        assert mut.location_object == location_object
        assert mut.device_id == device_id
        assert mut.device_type == device_type
        assert mut.description == device_desc