import unittest

import bot
import domain
import properties
import pytest
from localization import get_translations

from botengine_pytest import BotEnginePyTest

# Provides an fixture to include bot variables for regression tests
@pytest.mark.usefixtures("bot_variables")
@pytest.mark.usefixtures("organization_id")
class TestBot(unittest.TestCase):
    """ """

    def test_bot_run_init(self):
        """
        This test is to ensure that the botengine is initialized correctly with the correct organization
        :return:
        """
        # pytest.skip("[WIP]")
        botengine = BotEnginePyTest(
            {
                "time": 1687373406646,
                "trigger": 0,
                "source": 0,
                "organization": {
                    "organizationId": self.organization_id or 1,
                    "organizationName": "Test Organization",
                    "domainName": "pytest",
                    "brand": "caredaily",
                    "parentId": 0,
                    "features": "b,g,m,n,p",
                },
            },
            bot_variables=self.bot_variables,
        )

        bot.run(botengine)

        controller = bot.load_controller(botengine)
        assert controller is not None
        assert len(controller.organizations) == 1

    def test_bot_run_timer(self):
        """
        This test initializes a new bot instance with a trigger type of 64 (timer).
        :return:
        """
        botengine = BotEnginePyTest(
            {
                "time": 1687373406646,
                "trigger": BotEnginePyTest.TRIGGER_TIMER,
                "source": 0,
                "organization": {
                    "organizationId": self.organization_id or 1,
                    "organizationName": "Test Organization",
                    "domainName": "pytest",
                    "brand": "caredaily",
                    "parentId": 0,
                    "features": "b,g,m,n,p",
                },
            }
        )

        bot.run(botengine)

        controller = bot.load_controller(botengine)
        assert controller is not None
        assert len(controller.organizations) == 1

    def test_bot_run_datastream(self):
        """
        This test initializes a new bot instance with a trigger type of 256 (datastream) to remove
        a default system task `__people__` and ensures it is destroyed.
        :return:
        """
        botengine = BotEnginePyTest(
            {
                "time": 1687373406646,
                "trigger": BotEnginePyTest.TRIGGER_DATA_STREAM,
                "source": 0,
                "organization": {
                    "organizationId": self.organization_id or 1,
                    "organizationName": "Test Organization",
                    "domainName": "pytest",
                    "brand": "caredaily",
                    "parentId": 0,
                    "features": "b,g,m,n,p",
                },
                "dataStream": {
                    "feed": {"test_id": "test_feed"},
                    "address": "test",
                },
            }
        )

        bot.run(botengine)

        controller = bot.load_controller(botengine)
        assert controller is not None
        assert len(controller.organizations) == 1
