
from botengine_pytest import BotEnginePyTest

from organization.organization import *
import utilities.utilities as utilities

import unittest
from unittest.mock import MagicMock, patch

class TestOrganization(unittest.TestCase):

    def test_organization_constructor(self):
        # Initial setup
        botengine = BotEnginePyTest({})
        mut = Organization(botengine, 0)

        assert mut is not None
        # Organization ID
        assert mut.organization_id == 0
        assert mut.born_on == botengine.get_timestamp()
        assert mut.organization_domain_name == None
        assert mut.organization_descriptive_name == None
        assert mut.microservices == {}