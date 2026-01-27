"""
Created on March 20, 2020

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""

import json
import traceback

import bundle  # type: ignore
import domain
import requests
from analytics.analytics import Analytics  # type: ignore

# Variable name for tracking people
AMPLITUDE_USER_PROPERTIES_VARIABLE_NAME = "amplitude_user"

# HTTP timeout
AMPLITUDE_HTTP_TIMEOUT_S = 2


class AmplitudeAnalytics(Analytics):
    def __init__(self, botengine):
        """
        :param token:
        :param request_timeout:
        """
        Analytics.__init__(self, botengine)

        # Cache that isn't saved in non-volatile memory, so it's always [] on each new execution.
        self.cache = []

        # Total events tracked, always 0 on each new execution
        self.total = 0

    def track(self, botengine, event_name, properties=None):
        """
        Track an event.
        This will buffer your events and flush them to the server altogether at the end of all bot executions,
        and before variables get saved.

        :param botengine: BotEngine environment
        :param event_name: (string) A name describing the event
        :param properties: (dict) Additional data to record; keys should be strings and values should be strings, numbers, or booleans
        """
        if botengine.is_test_location():
            return

        self.total += 1
        botengine.get_logger().info(
            "Analytics: Tracking {} => {}".format(self.total, event_name)
        )

        if properties is None:
            properties = {}

        location_id = (
            self.parent.location_id
            if hasattr(self.parent, "location_id")
            else botengine.get_location_id()
        )
        organization_id = (
            self.parent.organization_id
            if hasattr(self.parent, "organization_id")
            else botengine.get_organization_id()
        )

        properties["locationId"] = location_id
        properties["organizationId"] = organization_id

        self.cache.append(
            {
                "user_id": self._get_user_id(botengine),
                "device_id": self._get_device_id(botengine),
                "event_id": self.total,
                "time": botengine.get_timestamp(),
                "event_type": event_name,
                "event_properties": properties,
                "user_properties": {
                    "locationId": location_id,
                    "organizationId": organization_id,
                },
            }
        )

    def people_set(self, botengine, properties_dict):
        """
        Set some key/value attributes for this user
        :param botengine: BotEngine environment
        :param properties_dict: Dictionary of key/value pairs to track
        """
        if botengine.is_test_location():
            return

        self.total += 1
        botengine.get_logger().debug(
            "analytics.py: Setting user info - {}".format(properties_dict)
        )

        focused_properties = botengine.load_variable(
            AMPLITUDE_USER_PROPERTIES_VARIABLE_NAME
        )
        if focused_properties is None:
            focused_properties = properties_dict
        focused_properties.update(properties_dict)
        focused_properties["locationId"] = botengine.get_location_id()
        focused_properties["organizationId"] = botengine.get_organization_id()
        botengine.save_variable(
            AMPLITUDE_USER_PROPERTIES_VARIABLE_NAME,
            focused_properties,
            required_for_each_execution=False,
        )

        self.cache.append(
            {
                "user_id": self._get_user_id(botengine),
                "device_id": self._get_device_id(botengine),
                "event_id": self.total,
                "time": botengine.get_timestamp(),
                "user_properties": focused_properties,
            }
        )

    def people_increment(self, botengine, properties_dict):
        """
        Adds numerical values to properties of a people record. Nonexistent properties on the record default to zero. Negative values in properties will decrement the given property.
        :param botengine: BotEngine environment
        :param properties_dict: Dictionary of key/value pairs. The value is numeric, either positive or negative. Default record is 0. The value will increment or decrement the property by that amount.
        """
        if botengine.is_test_location():
            return

        self.total += 1
        botengine.get_logger().info(
            "Analytics: Incrementing user info - {}".format(properties_dict)
        )

        focused_properties = botengine.load_variable(
            AMPLITUDE_USER_PROPERTIES_VARIABLE_NAME
        )

        if focused_properties is None:
            focused_properties = properties_dict

        for p in properties_dict:
            if p not in focused_properties:
                focused_properties[p] = 0
            focused_properties[p] += properties_dict[p]

        focused_properties["locationId"] = botengine.get_location_id()
        focused_properties["organizationId"] = botengine.get_organization_id()
        botengine.save_variable(
            AMPLITUDE_USER_PROPERTIES_VARIABLE_NAME,
            focused_properties,
            required_for_each_execution=False,
        )

        self.cache.append(
            {
                "user_id": self._get_user_id(botengine),
                "device_id": self._get_device_id(botengine),
                "event_id": self.total,
                "time": botengine.get_timestamp(),
                "user_properties": focused_properties,
            }
        )

    def people_unset(self, botengine, properties_list):
        """
        Delete a property from a user
        :param botengine: BotEngine
        :param properties_dict: Key/Value dictionary pairs to remove from a people record.
        """
        if botengine.is_test_location():
            return

        self.total += 1
        botengine.get_logger().info(
            "Analytics: Removing user info - {}".format(properties_list)
        )

        focused_properties = botengine.load_variable(
            AMPLITUDE_USER_PROPERTIES_VARIABLE_NAME
        )

        if focused_properties is None:
            # Nothing to unset
            return

        for p in properties_list:
            if p in focused_properties:
                del focused_properties[p]

        focused_properties["locationId"] = botengine.get_location_id()
        focused_properties["organizationId"] = botengine.get_organization_id()
        botengine.save_variable(
            AMPLITUDE_USER_PROPERTIES_VARIABLE_NAME,
            focused_properties,
            required_for_each_execution=False,
        )

        self.cache.append(
            {
                "user_id": self._get_user_id(botengine),
                "device_id": self._get_device_id(botengine),
                "event_id": self.total,
                "time": botengine.get_timestamp(),
                "user_properties": focused_properties,
            }
        )

    def flush(self, botengine):
        """
        Required. Implement the mechanisms to flush your analytics.
        :param botengine: BotEngine
        """
        if botengine.is_test_location():
            botengine.get_logger().debug(
                "Analytics: This test location will not record analytics."
            )
            return

        if self.total > 0:

            token = None
            for cloud_address in domain.AMPLITUDE_TOKENS:
                if cloud_address in bundle.CLOUD_ADDRESS:
                    token = domain.AMPLITUDE_TOKENS[cloud_address]

            if token is None:
                # Nothing to do
                botengine.get_logger().info(
                    "analytics_amplitude.flush(): No analytics token for {}".format(
                        bundle.CLOUD_ADDRESS
                    )
                )
                return

            if token == "":
                # Nothing to do
                botengine.get_logger().info(
                    "analytics_amplitude.flush(): No analytics token for {}".format(
                        bundle.CLOUD_ADDRESS
                    )
                )
                return

            http_headers = {"Content-Type": "application/json"}

            body = {"api_key": token, "events": self.cache}

            url = "https://api.amplitude.com/2/httpapi"

            try:
                requests.post(
                    url,
                    headers=http_headers,
                    data=json.dumps(body),
                    timeout=AMPLITUDE_HTTP_TIMEOUT_S,
                )

            except self._requests.HTTPError:
                self.get_logger().error("Generic HTTP error calling POST " + url)

            except self._requests.ConnectionError:
                self.get_logger().error("Connection HTTP error calling POST " + url)

            except self._requests.Timeout:
                self.get_logger().error(
                    str(AMPLITUDE_HTTP_TIMEOUT_S)
                    + " second HTTP Timeout calling POST "
                    + url
                )

            except self._requests.TooManyRedirects:
                self.get_logger().error(
                    "Too many redirects HTTP error calling POST " + url
                )

            except Exception:
                self.get_logger().error("Generic HTTP exception calling POST " + url)

            except Exception as e:
                botengine.get_logger().error(str(e) + "; " + traceback.format_exc())

        self.total = 0
        self.cache = []
        botengine.get_logger().info("Amplitude: Flushed()")

    def _get_user_id(self, botengine):
        """
        Generate an Amplitude User ID
        To us, this user ID will always have a "bot_" prefix, followed by the bot instance ID.
        :return:
        """
        return "bot_{}".format(botengine.bot_instance_id)

    def _get_device_id(self, botengine):
        """
        Get the Device ID
        :param botengine:
        :return:
        """
        return botengine.get_bundle_id()
