from locations.location import Location

from botengine_pytest import BotEnginePyTest

import unittest

import pytest
from signals.zendesk import (
    request_customer_support,
    USER_STATUS_LOCATION_PROPERTIES_KEY_PREFIX,
    USER_STATUS_NOT_FOUND,
    USER_STATUS_RELEASED,
    USER_STATUS_SUSPENDED,
)


class TestZendesk(unittest.TestCase):
    def test_zendesk(self):
        botengine = BotEnginePyTest({})

        # botengine.logging_service_names = ["zendesk"]  # Uncomment to see logging

        # Initialize the location
        location_object = Location(botengine, 0)

        location_object.initialize(botengine)
        location_object.new_version(botengine)

        zendesk_service = location_object.intelligence_modules.get(
            "intelligence.zendesk.location_zendesk_microservice"
        )
        if zendesk_service is None:
            pytest.skip("No zendesk service in bot bundle")
        
        # Simulate a trigger that would cause a ticket to be created
        request_customer_support(
            botengine,
            location_object,
            ticket_type=botengine.TICKET_TYPE_INCIDENT,
            ticket_priority=botengine.TICKET_PRIORITY_URGENT,
            user_id=123,
            subject="Test Zendesk Ticket",
            comment="This is a test ticket created by the test_zendesk unit test."
        )
        assert botengine.customer_support_body['user_id'] == 123
        
        botengine.customer_support_body = None

        # User is suspended in Zendesk, so ticket should not be created
        botengine.inputs["userId"] = 123
        zendesk_service.zendesk_status(botengine, {"status": USER_STATUS_SUSPENDED})

        # Simulate a trigger that would cause a ticket to be excluded
        request_customer_support(
            botengine,
            location_object,
            ticket_type=botengine.TICKET_TYPE_INCIDENT,
            ticket_priority=botengine.TICKET_PRIORITY_URGENT,
            user_id=123,
            subject="Test Zendesk Ticket",
            comment="This is a test ticket created by the test_zendesk unit test.",
        )
        assert botengine.customer_support_body is None

        # User is released in Zendesk, so ticket should be created
        zendesk_service.zendesk_status(botengine, {"status": USER_STATUS_RELEASED})

        # Simulate a trigger that would cause a ticket to be created
        request_customer_support(
            botengine,
            location_object,
            ticket_type=botengine.TICKET_TYPE_INCIDENT,
            ticket_priority=botengine.TICKET_PRIORITY_URGENT,
            user_id=123,
            subject="Test Zendesk Ticket",
            comment="This is a test ticket created by the test_zendesk unit test.",
        )
        assert botengine.customer_support_body['user_id'] == 123
