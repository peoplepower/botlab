'''
Created on March 13, 2021

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
'''

import bot

from intelligence.intelligence import Intelligence
import utilities.utilities as utilities

# Data request reference
DATA_REQUEST_LOCATIONS_REFERENCE = "locations"
DATA_REQUEST_DEVICES_REFERENCE = "devices"


class OrganizationBillingMicroservice(Intelligence):
    """
    Organization Billing Microservice
    
    This microservice calculates billing information for subscribers within an organization based on
    active billable devices. It provides automated invoice calculation capabilities by identifying
    and counting devices that should be included in billing.
    
    Purpose:
    This microservice exists to support multi-tenant billing scenarios where organizations need to
    track and bill their subscribers based on the number of active devices. It automates the process
    of counting billable devices across all locations within an organization and can generate
    billing reports or trigger invoice calculations.
    
    How It Works:
    1. Receives a data stream message to trigger invoice calculation via the 'calculate_invoice' address
    2. Requests comprehensive data about all locations and devices within the organization
    3. Asynchronously processes the device data to identify billable devices based on:
       - Device type (cameras, gateways, and other billable device types)
       - Recent activity (devices must have been online within the past 3 weeks)
    4. Counts the total number of billable devices across all locations
    5. Generates a billing report that can be emailed to administrators
    
    Billable Device Types:
    - Type 31: Camera devices
    - Type 32: Gateway devices
    - Type 36: Advanced camera devices
    - Type 37: Advanced gateway devices
    - Type 10031: Enterprise camera devices
    - Type 40: Other billable devices
    
    Data Stream Interactions:
    - Listens for 'calculate_invoice' messages to trigger billing calculations
    - Uses async data requests to gather location and device information
    
    Tools:
    The /tools directory contains command-line utilities to interact with this microservice:
    - calculate_invoice.py: Sends a data stream message to trigger invoice calculation for an organization
    
    Usage Example:
    python calculate_invoice.py --admin_username admin@example.com --admin_password pass -o 123 -s app.peoplepowerco.com
    
    Notes:
    - This microservice operates at the organization level (scope 2)
    - Device activity is measured by the 'measure_time' field
    - Devices are only billable if they were active within the past 3 weeks
    - Results can be emailed to administrators for review
    """

    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, like an Organization
        """
        Intelligence.__init__(self, botengine, parent)

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
        :param from_bot_id: Sender Bot ID
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    def schedule_fired(self, botengine, schedule_id):
        """
        The bot executed on a hard coded schedule specified by our runtime.json file
        :param botengine: BotEngine environment
        :param schedule_id: Schedule ID that is executing from our list of runtime schedules
        """
        botengine.get_logger().error("organization_billing_microservice.schedule_fired(schedule_id={})".format(schedule_id))
        return

    def timer_fired(self, botengine, argument):
        """
        The bot's intelligence timer fired
        :param botengine: Current botengine environment
        :param argument: Argument applied when setting the timer
        """
        botengine.get_logger().info("Timer fired!")

        botengine.get_organization_locations(self.parent.organization_id)

    def async_data_request_ready(self, botengine, reference, content):
        """
        Data request ready
        
        IMPORTANT: This method executes in an asynchronous environment where you are NOT allowed to:
        - Set timers or alarms
        - Manage class variables that persist across executions
        - Perform other stateful operations

        To return to a synchronous environment where you can use timers and manage state, call:
        botengine.async_execute_again_in_n_seconds(seconds)
        
        :param botengine:
        :param reference:
        :param content:
        :return:
        """
        if reference == DATA_REQUEST_LOCATIONS_REFERENCE:
            botengine.get_logger().error("LOCATIONS organization_billing_microservice.async_data_request_ready(reference={}, content={})".format(reference, content))

        elif reference == DATA_REQUEST_DEVICES_REFERENCE:
            botengine.get_logger().error("DEVICES organization_billing_microservice.async_data_request_ready(reference={}, content={})".format(reference, content))

            BILLABLE_DEVICE_TYPES = [31, 32, 36, 37, 10031, 40]

            billable_devices = 0
            for location_id in content:
                for device_id in content[location_id]:
                    focused_device = content[location_id][device_id]
                    if focused_device['deviceType'] in BILLABLE_DEVICE_TYPES:
                        if focused_device['measureTime'] != "":
                            # See that the device was online sometime in at least the past 3 weeks
                            if focused_device['measureTime'] > botengine.get_timestamp() - utilities.ONE_WEEK_MS * 3:
                                botengine.get_logger().info("Billable device: {}".format(focused_device))
                                billable_devices += 1

            botengine.get_logger().info("TOTAL BILLABLE DEVICES: {}".format(billable_devices))
            botengine.email_admins(
                email_subject="Invoice Test", 
                email_content="TOTAL BILLABLE DEVICES: {}".format(billable_devices), 
                email_addresses=["dmoss@peoplepowerco.com"])

    def calculate_invoice(self, botengine, content):
        """
        Calculate the invoice
        :param botengine:
        :param content:
        :return:
        """
        botengine.get_logger().error("organization_billing_microservice.calculate_invoice(content={}) - requesting locations via data request".format(content))


        botengine.request_data(type=botengine.DATA_REQUEST_TYPE_LOCATIONS,
                               reference=DATA_REQUEST_LOCATIONS_REFERENCE)

        botengine.request_data(type=botengine.DATA_REQUEST_TYPE_DEVICES,
                               reference=DATA_REQUEST_DEVICES_REFERENCE)
