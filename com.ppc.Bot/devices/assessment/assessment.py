from devices.device import Device


class AssessmentDevice(Device):
    """Assessment Device Class

    Base class for assessment devices that provide on-demand health assessments and measurements. This class can be extended to create specific assessment devices with standardized measurement parameters and device types.
    """

    def __init__(
        self,
        botengine,
        location_object,
        device_id,
        device_type,
        device_description,
        precache_measurements=True,
    ):
        Device.__init__(
            self,
            botengine,
            location_object,
            device_id,
            device_type,
            device_description,
            precache_measurements=precache_measurements,
        )