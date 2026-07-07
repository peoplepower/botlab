'''
Created on January 13, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter
'''

from intelligence.intelligence import Intelligence
import utilities.utilities as utilities
import signals.questions as questions

class LocationOrganizationSurveysMicroservice(Intelligence):
    """
    
    """
    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, either a location or a device object.
        """
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        pass

    def timer_fired(self, botengine, argument):
        """
        The bot's intelligence timer fired
        :param botengine: Current botengine environment
        :param argument: Argument applied when setting the timer
        """
        pass

    def language_updated(self, botengine, language):
        """
        The location's preferred language has been updated.
        Please translate any Synthetic API state variables and history that may be exposed in user experiences.
        :param botengine: BotEngine environment
        :param language: New language identifier, i.e. 'en'
        """
        pass

    def survey_answered(self, botengine, user_id, survey):
        """
        The survey was answered
        :param botengine: BotEngine environment
        :param user_id: User ID that answered the survey
        :param survey: Survey data dictionary containing locationId, userId, and survey JSON
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">survey_answered()"
        )
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|survey_answered() user_id={} survey={}".format(user_id, survey)
        )
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<survey_answered()"
        )
        pass

    def organization_surveys_post_notification(self, botengine, content):
        """
        Post a notification to the organization surveys
        :param botengine: BotEngine environment
        :param content: Content dictionary containing survey key, user id, role, send to user, and notification category
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">organization_surveys_post_notification()"
        )
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|organization_surveys_post_notification() content={}".format(content)
        )
        try:
            survey_key = content["survey_key"]
            user_id = content.get("user_id")
            send_to_user = content.get("send_to_user")
            notification_category = content.get("notification_category")
            botengine.start_answering_survey(
                location_id=self.parent.location_id, 
                survey_key=survey_key, 
                user_id=user_id, 
                send_to_user=send_to_user, 
                notification_category=notification_category
            )
        except Exception as e:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                "|organization_surveys_post_notification() error={}".format(e)
            )
            return
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<organization_surveys_post_notification()")