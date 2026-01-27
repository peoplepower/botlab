'''
Created on March 20, 2020

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
'''

from analytics.analytics import Analytics

# Mixpanel HTTP Timeout in seconds
MIXPANEL_HTTP_TIMEOUT_S = 2

# Distinct ID variable
VARIABLE_DISTINCT_ID = "-distinctid-"

class MixPanelAnalytics(Analytics):
    """
    Mixpanel-specific implementation of analytics.

    You can replace this implementation to point to your own analytics service, and it will continue to
    work throughout the entire microservices framework.

    See mixpanel documentation at: https://mixpanel.github.io/mixpanel-python/

    To use in your bot:  First include 'mixpanel' in pip_install or pip_install_remotely in your structure.json file.

        import analytics
        analytics.get_analytics(botengine).track(botengine, event_name, properties=None)


    Or to make a generalized microservice that may or may not have an analytics.py file implemented in the base class:

        import importlib
        try:
            analytics = importlib.import_module('analytics')
            analytics.get_analytics(botengine).track(botengine, event_name, properties=None)

        except ImportError:
            botengine.get_logger().warn("Unable to import analytics module")

    Or another method, leveraging the com.ppc.Bot/locations/location.py object:

        location_object.track(..)

    """
    def __init__(self, botengine):
        """
        :param token:
        :param request_timeout:
        """
        Analytics.__init__(self, botengine)

        import domain
        import mixpanel

        # Mixpanel Object
        self.mp = mixpanel.Mixpanel(domain.MIXPANEL_TOKEN, consumer=mixpanel.BufferedConsumer(request_timeout=MIXPANEL_HTTP_TIMEOUT_S))

        # Total number of events tracked on this execution, never saved so always 0 on the next execution
        self.total = 0

    def track(self, botengine, event_name, properties=None):
        """
        Track an event. This is for a mixpanel-specific implementation.
        This will buffer your events and flush them to the server altogether at the end of all bot executions,
        and before variables get saved.

        :param botengine: BotEngine environment
        :param event_name: (string) A name describing the event
        :param properties: (dict) Additional data to record; keys should be strings and values should be strings, numbers, or booleans
        """
        self.total += 1
        botengine.get_logger().info("Analytics: Tracking {} => {}".format(self.total, event_name))
        self.mp.track(self._get_distinct_id(botengine), event_name, properties)


    def people_set(self, botengine, properties_dict):
        """
        Set some key/value attributes for this user
        :param botengine: BotEngine environment
        :param properties_dict: Dictionary of key/value pairs to track
        """
        self.total += 1
        botengine.get_logger().debug("analytics.py: Setting user info - {}".format(properties_dict))
        self.mp.people_set(self._get_distinct_id(botengine), properties_dict)


    def people_increment(self, botengine, properties_dict):
        """
        Adds numerical values to properties of a people record. Nonexistent properties on the record default to zero. Negative values in properties will decrement the given property.
        :param botengine: BotEngine environment
        :param properties_dict: Dictionary of key/value pairs. The value is numeric, either positive or negative. Default record is 0. The value will increment or decrement the property by that amount.
        """
        self.total += 1
        botengine.get_logger().info("Analytics: Incrementing user info - {}".format(properties_dict))
        self.mp.people_increment(self._get_distinct_id(botengine), properties_dict)

    def people_unset(self, botengine, properties_list):
        """
        Delete a property from a user
        :param botengine: BotEngine
        :param properties_dict: Key/Value dictionary pairs to remove from a people record.
        """
        self.total += 1
        botengine.get_logger().info("Analytics: Removing user info - {}".format(properties_list))
        self.mp.people_unset(self._get_distinct_id(botengine), properties_list)

    def flush(self, botengine):
        """
        Required. Implement the mechanisms to flush your analytics.
        :param botengine: BotEngine
        """
        if self.total > 0:
            try:
                self._sync_user(botengine)
                self.mp._consumer._consumer._request_timeout = MIXPANEL_HTTP_TIMEOUT_S
                self.mp._consumer.flush()

            except Exception as e:
                import traceback
                botengine.get_logger().error(str(e) + "; " + traceback.format_exc())

        self.total = 0

    def _sync_user(self, botengine):
        """
        Sync the user account information
        :param botengine: BotEngine environment
        """
        import domain

        anonymize = False
        if hasattr(domain, "ANONYMIZE_ANALYTICS"):
            anonymize = domain.ANONYMIZE_ANALYTICS

        if anonymize:
            self.mp.people_set(self._get_distinct_id(botengine), {
                'location_id': botengine.get_location_id()
            })

        else:
            self.mp.people_set(self._get_distinct_id(botengine), {
                'location_id': botengine.get_location_id(),
                '$first_name': botengine.get_location_name(),
                '$last_name': ""
            })

    def _get_distinct_id(self, botengine):
        """
        Get the distinct ID for this user
        :param botengine:
        :return: distinct ID
        """
        distinct_id = botengine.load_variable(VARIABLE_DISTINCT_ID)
        if distinct_id is None:
            distinct_id = botengine.get_location_id()
            botengine.save_variable(VARIABLE_DISTINCT_ID, distinct_id, required_for_each_execution=True)

        return distinct_id