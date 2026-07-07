from devices.entry.entry import EntryDevice
from devices.gateway.gateway import GatewayDevice
from devices.motion.motion import MotionDevice
from locations.location import Location

from botengine_pytest import BotEnginePyTest
import unittest

class TestZendeskIntelligence(unittest.TestCase):
    def test_zendesk_initialization(self):
        botengine = BotEnginePyTest({})

        location_object = Location(botengine, 0)

        location_object.initialize(botengine)
        location_object.new_version(botengine)

        mut = location_object.intelligence_modules[
            "intelligence.zendesk.location_zendesk_microservice"
        ]
        assert mut is not None