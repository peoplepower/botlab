'''
Created on February 4, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter
'''

from intelligence.intelligence import Intelligence
import utilities.utilities as utilities
import properties
import signals.zendesk as zendesk


class LocationZendeskMicroservice(Intelligence):
    """
    Coordinate ZenDesk user status from cloud to location properties
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

    def destroy(self, botengine):
        """
        This device or object is getting permanently deleted - it is no longer in the user's account.
        :param botengine: BotEngine environment
        """
        return

    def new_version(self, botengine):
        """
        Upgraded to a new bot version
        :param botengine: BotEngine environment
        """
        return

    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Message Received
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Content of the message
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    def zendesk_status(self, botengine, content):
        """
        Update ZenDesk user status property
        :param botengine: BotEngine environment
        :param content: Content of the message
        """
        user_id = botengine.get_input_user_id()
        if user_id is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "<zendesk_status() Missing userId in input"
            )
            return
        status = content.get("status")

        if user_id is None or status is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "<zendesk_status() Missing userId or status: {}".format(content)
            )
            return

        zendesk_user_status_property_key = zendesk.USER_STATUS_LOCATION_PROPERTIES_KEY_PREFIX + str(user_id)
        self.parent.set_location_property(botengine, zendesk_user_status_property_key, status)

        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<zendesk_status() user_id={} status={}".format(user_id, status)
        )