
from botengine_pytest import BotEnginePyTest

from organization.organization import Organization
import utilities.utilities as utilities

class TestBillingPerSubMicroservice():


    def test_billing_per_sub_initialization(self):

        botengine = BotEnginePyTest({})
        # Clear out any previous tests
        botengine.reset()

        # Initialize the organization
        organization_object = Organization(botengine, 0)

        organization_object.new_version(botengine)
        organization_object.initialize(botengine)

        mut = organization_object.intelligence_modules["intelligence.billing_per_sub.organization_billing_microservice"]
        assert mut is not None