'''
Created on March 27, 2019

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
'''

import bot

from intelligence.intelligence import Intelligence

class OrganizationSettingsMicroservice(Intelligence):
    """
    Organization Settings Microservice
    
    This microservice manages global settings across an entire organization, providing a centralized
    configuration management system for multi-location deployments. It enables administrators to
    define, distribute, and maintain consistent settings across all bot instances within an organization.
    
    Purpose:
    This microservice exists to solve the challenge of managing configuration settings across multiple
    locations and bot instances within a single organization. Rather than configuring each location
    individually, administrators can define settings once at the organization level and have them
    automatically distributed to all relevant bot instances.
    
    How It Works:
    1. Stores organization-wide settings in a dictionary keyed by setting address
    2. Receives data stream messages to save, delete, or retrieve settings
    3. Validates requests to ensure they originate from trusted sources (not from other bots)
    4. Distributes settings changes to all bot instances in the organization via data stream messages
    5. Persists settings using admin content storage for durability
    
    Security:
    This microservice includes security checks to prevent unauthorized bots from modifying
    organization-wide settings. Settings can only be saved or deleted by direct requests,
    not by other bot instances (enforced via from_bot_id checks).
    
    Data Stream Interactions:
    - 'save_settings': Saves a new setting or updates an existing one. Content must include 'address'.
    - 'delete_settings': Removes a setting by address. Content must include 'address'.
    - 'get_settings': Delivers all current settings to a requesting bot instance.
    
    Setting Storage:
    - Settings are stored in self.settings dictionary with address as the key
    - Settings are persisted via botengine.set_admin_content() for durability
    - Settings are distributed to all bots using scope=1 (organization-wide)
    
    Tools:
    The /tools directory contains command-line utilities to interact with this microservice:
    - save_settings.py: Saves or updates an organization setting (includes example TOU schedule)
    - delete_settings.py: Removes an organization setting by address
    - get_settings.py: Retrieves all current organization settings
    
    Usage Example:
    python save_settings.py --admin_username admin@example.com --admin_password pass -o 123 -s app.peoplepowerco.com
    python get_settings.py --admin_username admin@example.com --admin_password pass -o 123 -s app.peoplepowerco.com
    python delete_settings.py --admin_username admin@example.com --admin_password pass -o 123 -s app.peoplepowerco.com
    
    Common Use Cases:
    - Time-of-use (TOU) rate schedules for energy management
    - Organization-wide operational parameters
    - Feature flags and configuration toggles
    - Shared thresholds and limits
    
    Notes:
    - This microservice operates at the organization level (scope 2)
    - Settings are automatically synchronized across all bot instances
    - Admin-level authentication is required to modify settings
    """

    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, like an Organization
        """
        Intelligence.__init__(self, botengine, parent)

        # Organization global settings
        self.settings = {}

    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        return

    def destroy(self, botengine):
        """
        This device or object is getting permanently deleted - it is no longer in the user's account.
        :param botengine: BotEngine environment
        """
        return

    def question_answered(self, botengine, question):
        """
        The user answered a question
        :param botengine: BotEngine environment
        :param question: Question object
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

    def schedule_fired(self, botengine, schedule_id):
        """
        The bot executed on a hard coded schedule specified by our runtime.json file
        :param botengine: BotEngine environment
        :param schedule_id: Schedule ID that is executing from our list of runtime schedules
        """
        return

    def timer_fired(self, botengine, argument):
        """
        The bot's intelligence timer fired
        :param botengine: Current botengine environment
        :param argument: Argument applied when setting the timer
        """
        botengine.get_logger().info("Timer fired!")

        botengine.get_organization_locations(self.parent.organization_id)

    def save_settings(self, botengine, content, from_bot_id):
        """
        Save new global settings
        https://presence.atlassian.net/wiki/spaces/BOTS/pages/672792625/save+settings+Save+global+organization+settings+Data+Stream+Message
        :param botengine:
        :param content:
        :param from_bot_id:
        :return:
        """
        if 'address' not in content:
            botengine.get_logger().error("organization_settings_microservice: save_settings has no 'address': {}".format(content))
            return

        if from_bot_id is not None:
            botengine.get_logger().error("organization_settings_microservice: Security warning. Bot {} attempted to save_settings in the organization".format(from_bot_id))
            return

        address = content['address']
        del(content['address'])
        settings = content

        self.settings[address] = settings
        botengine.get_logger().info("organization_settings_microservice: save_settings saved {}".format(address))

        # Distribute the settings to all bots in this organization
        botengine.send_datastream_message(address, settings, scope=1)
        botengine.set_admin_content(self.parent.organization_id, address, settings)


    def delete_settings(self, botengine, content, from_bot_id):
        """
        Delete a global setting
        https://presence.atlassian.net/wiki/spaces/BOTS/pages/672923661/delete+settings+Delete+global+organization+settings+Data+Stream+Message
        :param botengine:
        :param content:
        :param from_bot_id:
        :return:
        """
        if 'address' not in content:
            botengine.get_logger().error("organization_settings_microservice: save_settings has no 'address': {}".format(content))
            return

        if from_bot_id is not None:
            botengine.get_logger().error("organization_settings_microservice: Security warning. Bot {} attempted to save_settings in the organization".format(from_bot_id))
            return

        if content['address'] in self.settings:
            botengine.get_logger().info("organization_settings_microservice: {} deleted".format(content['address']))
            del(self.settings[content['address']])
            botengine.delete_admin_content(self.parent.organization_id, content['address'])

        else:
            botengine.get_logger().warning("organization_settings_microservice: {} cannot be deleted because it doesn't exist in our settings".format(content['address']))

    def get_settings(self, botengine, content, bot_id):
        """
        Deliver settings to the bot that sent this request
        https://presence.atlassian.net/wiki/spaces/BOTS/pages/672923669/get+settings+Get+global+organization+settings+Data+Stream+Message
        :param botengine:
        :param content:
        :param from_bot_id:
        :return:
        """
        import json
        botengine.get_logger().info("Settings include: \n{}".format(json.dumps(self.settings, sort_keys=True)))

        if bot_id is not None:
            botengine.get_logger().info("organization_settings_microservice: Delivering settings to {}".format(bot_id))

            for setting in self.settings:
                botengine.send_datastream_message(setting, self.settings[setting], bot_instance_list=[bot_id], scope=1)

        else:
            botengine.get_logger().warning("organization_settings_microservice: get_settings requested, but missing a bot_id to deliver to")

