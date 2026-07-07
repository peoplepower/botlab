
from botengine_pytest import BotEnginePyTest

from organization.organization import Organization
import utilities.utilities as utilities

class TestOrganizationSettingsMicroservice():


    def test_organization_settings_initialization(self):

        botengine = BotEnginePyTest({})
        # Clear out any previous tests
        botengine.reset()

        # Initialize the organization
        organization_object = Organization(botengine, 0)

        organization_object.new_version(botengine)
        organization_object.initialize(botengine)

        mut = organization_object.intelligence_modules["intelligence.organization_settings.organization_settings_microservice"]
        assert mut is not None