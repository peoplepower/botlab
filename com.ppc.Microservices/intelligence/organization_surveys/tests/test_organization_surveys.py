
import os
import json
from botengine_pytest import BotEnginePyTest

from locations.location import Location

from intelligence.organization_surveys.location_organization_surveys_microservice import (
    LocationOrganizationSurveysMicroservice
)


class TestOrganizationSurveysMicroservice():

    def test_organization_surveys_initialization(self):
        botengine = BotEnginePyTest({})

        botengine.reset()

        location = Location(botengine, 0)

        location.new_version(botengine)
        location.initialize(botengine)

        mut = location.intelligence_modules["intelligence.organization_surveys.location_organization_surveys_microservice"]
        assert mut is not None

    def test_organization_surveys_answered(self):
        botengine = BotEnginePyTest({})

        botengine.reset()
        # botengine.logging_service_names = ["organization_surveys"]

        location = Location(botengine, 0)

        location.new_version(botengine)
        location.initialize(botengine)

        mut = location.intelligence_modules["intelligence.organization_surveys.location_organization_surveys_microservice"]
        assert mut is not None

        # Load answer data from /data/answers-successful_aging_connections.json

        dir_name = os.path.dirname(os.path.abspath(__file__))
        file_name = 'input-successful_aging_connections.json'
        with open(os.path.join(dir_name, "data", file_name), "r") as f:
            input_json = json.load(f)
        assert input_json is not None

        mut.survey_answered(botengine, user_id=123, survey=input_json)
        assert False


