from devices.assessment.assessment import AssessmentDevice


class GripAbleDevice(AssessmentDevice):
    """GripAble Device Class

    GripAble Able-Assess is a functional health assessment platform that uses a sensor-based
    device to measure falls risk and functional capacity through standardized clinical assessments.

    https://www.able-care.co/solutions/able-assess/
    """

    # 4-Meter Gait Speed Test (seconds) - Measures walking speed over 4 meters to assess mobility and functional decline
    MEASUREMENT_NAME_4GS = "able.4GS"
    MEASUREMENT_NAME_GST = "able.GST"

    # At Risk flag - Indicates if the person is at risk based on the assessment results
    MEASUREMENT_NAME_AT_RISK = "able.atRisk"

    # Chair Stand Test (seconds) - Evaluates lower body strength and functional capacity through sit-to-stand repetitions
    MEASUREMENT_NAME_CST = "able.CST"

    # Single Maximum Grip Strength Test (kg) - Measures hand grip force as a biomarker for overall health and biological aging
    MEASUREMENT_NAME_SMGT = "able.SMGT"

    # Timed Up and Go Test (seconds) - Assesses mobility and fall risk by timing rise-walk-return sequence
    MEASUREMENT_NAME_TUG = "able.TUG"

    MEASUREMENT_PARAMETERS_LIST = [
        MEASUREMENT_NAME_4GS,
        MEASUREMENT_NAME_GST,
        MEASUREMENT_NAME_AT_RISK,
        MEASUREMENT_NAME_CST,
        MEASUREMENT_NAME_SMGT,
        MEASUREMENT_NAME_TUG,
    ]

    # List of Device Types this class is compatible with
    DEVICE_TYPES = [2009]

    def __init__(
        self,
        botengine,
        location_object,
        device_id,
        device_type,
        device_description,
        precache_measurements=True,
    ):
        AssessmentDevice.__init__(
            self,
            botengine,
            location_object,
            device_id,
            device_type,
            device_description,
            precache_measurements=precache_measurements,
        )

    def initialize(self, botengine):
        """
        Initialize
        :param botengine:
        :return:
        """
        AssessmentDevice.initialize(self, botengine)

    def get_device_type_name(self):
        """
        :return: the name of this device type in the given language, for example, "Entry Sensor"
        """
        # NOTE: Device type name
        return _("Grip-Able")

    def get_icon(self):
        """
        :return: the font icon name of this device type
        """
        return "hands"

    # ===========================================================================
    # Attributes
    # ===========================================================================
    def get_4gs(self, botengine=None):
        """
        Get the latest 4-Meter Gait Speed test result
        :param botengine:
        :return: gait speed time in seconds, or None
        """
        if GripAbleDevice.MEASUREMENT_NAME_4GS in self.measurements:
            return self.measurements[GripAbleDevice.MEASUREMENT_NAME_4GS][0][0]
        if GripAbleDevice.MEASUREMENT_NAME_GST in self.measurements:
            return self.measurements[GripAbleDevice.MEASUREMENT_NAME_GST][0][0]
        return None

    def did_update_4gs(self, botengine=None):
        """
        :return: True if the 4GS measurement was updated just now
        """
        return (
            GripAbleDevice.MEASUREMENT_NAME_4GS in self.last_updated_params
            or GripAbleDevice.MEASUREMENT_NAME_GST in self.last_updated_params
        )

    def get_at_risk(self, botengine=None):
        """
        Get the latest at-risk flag
        :param botengine:
        :return: at-risk value, or None
        """
        if GripAbleDevice.MEASUREMENT_NAME_AT_RISK in self.measurements:
            return self.measurements[GripAbleDevice.MEASUREMENT_NAME_AT_RISK][0][0]
        return None

    def did_update_at_risk(self, botengine=None):
        """
        :return: True if the at-risk measurement was updated just now
        """
        return GripAbleDevice.MEASUREMENT_NAME_AT_RISK in self.last_updated_params

    def get_cst(self, botengine=None):
        """
        Get the latest Chair Stand Test result
        :param botengine:
        :return: chair stand test time in seconds, or None
        """
        if GripAbleDevice.MEASUREMENT_NAME_CST in self.measurements:
            return self.measurements[GripAbleDevice.MEASUREMENT_NAME_CST][0][0]
        return None

    def did_update_cst(self, botengine=None):
        """
        :return: True if the CST measurement was updated just now
        """
        return GripAbleDevice.MEASUREMENT_NAME_CST in self.last_updated_params
    
    def get_smgt(self, botengine=None):
        """
        Get the latest Single Maximum Grip Strength Test result
        :param botengine:
        :return: left and right grip strength in kg, or None, None
        """
        smgt_right, smgt_left = None, None
        if f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left" in self.measurements:
            smgt_left = self.measurements[f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left"][0][0]
        if f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right" in self.measurements:
            smgt_right = self.measurements[f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right"][0][0]
        return smgt_left, smgt_right
    
    def did_update_smgt(self, botengine=None):
        """
        :return: True if the SMGT measurement was updated just now
        """
        return (
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left" in self.last_updated_params or
            f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right" in self.last_updated_params
        )

    def get_smgt_right(self, botengine=None):
        """
        Get the latest Single Maximum Grip Strength Test result
        :param botengine:
        :return: grip strength in kg, or None
        """
        if f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right" in self.measurements:
            return self.measurements[f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right"][0][0]
        return None

    def did_update_smgt_right(self, botengine=None):
        """
        :return: True if the SMGT measurement was updated just now
        """
        return f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.right" in self.last_updated_params
    
    def get_smgt_left(self, botengine=None):
        """
        Get the latest Single Maximum Grip Strength Test result
        :param botengine:
        :return: grip strength in kg, or None
        """
        if f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left" in self.measurements:
            return self.measurements[f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left"][0][0]
        return None

    def did_update_smgt_left(self, botengine=None):
        """
        :return: True if the SMGT measurement was updated just now
        """
        return f"{GripAbleDevice.MEASUREMENT_NAME_SMGT}.left" in self.last_updated_params

    def get_tug(self, botengine=None):
        """
        Get the latest Timed Up and Go test result
        :param botengine:
        :return: TUG time in seconds, or None
        """
        if GripAbleDevice.MEASUREMENT_NAME_TUG in self.measurements:
            return self.measurements[GripAbleDevice.MEASUREMENT_NAME_TUG][0][0]
        return None

    def did_update_tug(self, botengine=None):
        """
        :return: True if the TUG measurement was updated just now
        """
        return GripAbleDevice.MEASUREMENT_NAME_TUG in self.last_updated_params

