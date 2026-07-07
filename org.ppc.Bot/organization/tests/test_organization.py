import unittest

from organization.organization import Organization

from botengine_pytest import BotEnginePyTest


class TestOrganization(unittest.TestCase):
    def test_organization_constructor(self):
        # Initial setup
        botengine = BotEnginePyTest({})
        mut = Organization(botengine, 0)

        assert mut is not None
        # Organization ID
        assert mut.organization_id == 0
        assert mut.born_on == botengine.get_timestamp()
        assert mut.organization_domain_name is None
        assert mut.organization_descriptive_name is None
        assert mut.intelligence_modules == {}
