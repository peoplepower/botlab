'''
Created on December 10, 2024

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Konstantin Manyankin
'''
from devices.button.button_mpers import MobileButtonDevice


class IntrexButtonDevice(MobileButtonDevice):
    """
    Intrex Community Wearable Device
    """

    # Measurement names for Intrex-specific features
    MEASUREMENT_NAME_LOCATION = 'location'

    MEASUREMENT_PARAMETERS_LIST = [
        MEASUREMENT_NAME_LOCATION,
        MobileButtonDevice.MEASUREMENT_NAME_STEPS,
        MobileButtonDevice.MEASUREMENT_NAME_FALL_STATUS,
        MobileButtonDevice.MEASUREMENT_NAME_BUTTON_STATUS
    ]

    # List of Device Types this class is compatible with
    DEVICE_TYPES = [2031]

    def __init__(self, botengine, location_object, device_id, device_type, device_description, precache_measurements=True):
        """
        Constructor
        :param botengine:
        :param device_id:
        :param device_type:
        :param device_description:
        :param precache_measurements:
        """
        MobileButtonDevice.__init__(self, botengine, location_object, device_id, device_type, device_description,
                                   precache_measurements=precache_measurements)


    def get_device_type_name(self):
        """
        :return: the name of this device type in the given language, for example, "Entry Sensor"
        """
        # NOTE: Abstract device type name, doesn't show up in end user documentation
        return _("Intrex Community Wearable")  # noqa: F821 # type: ignore
    
    
    def did_location_change(self, botengine=None):
        """
        Did the location change?
        :param botengine:
        :return: True if the location changed
        """
        if self.MEASUREMENT_NAME_LOCATION in self.measurements:
            if self.MEASUREMENT_NAME_LOCATION in self.last_updated_params:
                return True

        return False

    def get_location(self, botengine=None):
        """
        Get the location of the device based on the last location measurement received
        :param botengine:
        :return: Location of the device; None if it doesn't exist
        """
        if self.MEASUREMENT_NAME_LOCATION in self.measurements:
            return self.measurements[self.MEASUREMENT_NAME_LOCATION][0][0]

        return None

    def get_location_timestamp(self, botengine=None):
        """
        Get the timestamp of the last location measurement received
        :param botengine:
        :return: Timestamp of the last location measurement in ms; None if it doesn't exist
        """
        if self.MEASUREMENT_NAME_LOCATION in self.measurements:
            return self.measurements[self.MEASUREMENT_NAME_LOCATION][0][1]

        return None