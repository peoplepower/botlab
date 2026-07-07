"""
Created on July 2, 2021

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Edward Liu
"""


# Location Access Levels
LOCATION_ACCESS_NONE = 0
LOCATION_ACCESS_READ = 10
LOCATION_ACCESS_CONTROL = 20
LOCATION_ACCESS_ADMIN = 30

# Alert Texting Categories
ALERT_CATEGORY_NOALERTS = 0
ALERT_CATEGORY_RESIDENT = 1
ALERT_CATEGORY_SUPPORTER = 2
ALERT_CATEGORY_SOCIALONLY = 3

# User Roles
ROLE_TYPE_DEFAULT = 0
ROLE_TYPE_CARE_RECIPIENT = 1
ROLE_TYPE_PRIMARY_FAMILY_CAREGIVER = 2
ROLE_TYPE_SECONDARY_FAMILY_CAREGIVER = 3
ROLE_TYPE_PROFESSIONAL_CAREGIVER = 4
ROLE_TYPE_PHYSICIAN = 6

# Gender
GENDER_UNKNOWN = 0
GENDER_MALE = 1
GENDER_FEMALE = 2
GENDER_OTHER = 3

# Accessibility Bitmask
ACCESSIBILITY_NONE = 0
ACCESSIBILITY_VISUAL_IMPAIRMENT = 1
ACCESSIBILITY_HEARING_IMPAIRMENT = 2
ACCESSIBILITY_MOBILITY_IMPAIRMENT = 4
ACCESSIBILITY_COMMUNICATION_IMPAIRMENT = 8
ACCESSIBILITY_PHYSICAL_IMPAIRMENT = 16
ACCESSIBILITY_COGNITIVE_IMPAIRMENT = 32

# Email Status
EMAIL_STATUS_OK = 0
EMAIL_STATUS_HARD_BOUNCE = 1
EMAIL_STATUS_SPAM_COMPLAINT = 2
EMAIL_STATUS_BAD_ADDRESS = 3
EMAIL_STATUS_SPAM_NOTIFICATION = 4

# Phone Type
PHONE_TYPE_UNKNOWN = 0
PHONE_TYPE_CELL = 1
PHONE_TYPE_HOME = 2
PHONE_TYPE_WORK = 3
PHONE_TYPE_OFFICE = 4

# Residency
RESIDENCY_UNKNOWN = 0
RESIDENCY_RESIDENT = 1
RESIDENCY_ONSITE_COMMUNITY_STAFF = 2
RESIDENCY_LIVES_NEARBY = 3
RESIDENCY_LIVES_REMOTELY = 4

# SMS Status
SMS_STATUS_UNKNOWN = 0
SMS_STATUS_VERIFIED_YES = 1
SMS_STATUS_VERIFIED_PROBABLY = 2
SMS_STATUS_VERIFIED_NO = 3

class User:
    """
    The User class tracks information about an individual user associated with this location.
    """

    def __init__(self, botengine, user_id):
        """
        User constructor. Not all user fields are available to bots - especially contact information.
        https://iotapps.docs.apiary.io/reference/locations/location-users

        It is expected that a controlling object (location.py) will initialize the information for this user.

        :param botengine: BotEngine environment
        :param user_id: User ID
        """
        # User id
        self.user_id = user_id

        # This is set with the location
        self.location_object = None

        # First name
        self.first_name = ""

        # Last name
        self.last_name = ""

        # Role (users.user.ROLE_TYPE_*)
        self.role = None

        # Role ID (administrative roles, see Admin Get Roles API)
        self.role_id = None

        # Location Access (users.user.LOCATION_ACCESS_*)
        self.location_access = None

        # Alert Category (users.user.ALERT_CATEGORY_*)
        self.alert_category = None

        # Preferred language (string, e.g., "en")
        self.language = None

        # Accessibility (bitmask of users.user.ACCESSIBILITY_*)
        self.accessibility = None

        # Birth date (ISO 8601 date string: YYYY-MM-DD)
        self.birth_date = None

        # Call order (integer)
        self.call_order = None

        # Email status (users.user.EMAIL_STATUS_*)
        self.email_status = None

        # Email verified (boolean)
        self.email_verified = None

        # Gender (users.user.GENDER_*)
        self.gender = None

        # Phone channels (list of phone channels, e.g., {"mms": True, "sms": True, "voice": True})
        self.phone_channels = None

        # Phone type (users.user.PHONE_TYPE_*)
        self.phone_type = None

        # Residency (users.user.RESIDENCY_*)
        self.residency = None

        # SMS status (users.user.SMS_STATUS_*)
        self.sms_status = None

    def initialize(self, botengine):
        """
        Initialize this object

        NOTE: YOU CANNOT CHANGE THE CLASS NAME OF A MICROSERVICE AT THIS TIME.
        Microservice changes will be identified through different 'module' names only. If you change the class name, it is currently ignored.
        This can be revisited in future architecture changes, noted below.

        The correct behavior is to create the object, then initialize() it every time you want to use it in a new bot execution environment
        """

    def new_version(self, botengine):
        """
        New version deployed
        :param botengine:
        :return:
        """
        if not hasattr(self, "role"):
            self.role = None
        if not hasattr(self, "role_id"):
            self.role_id = None
        if not hasattr(self, "accessibility"):
            self.accessibility = None
        if not hasattr(self, "birth_date"):
            self.birth_date = None
        if not hasattr(self, "call_order"):
            self.call_order = None
        if not hasattr(self, "email_status"):
            self.email_status = None
        if not hasattr(self, "email_verified"):
            self.email_verified = None
        if not hasattr(self, "gender"):
            self.gender = None
        if not hasattr(self, "phone_channels"):
            self.phone_channels = None
        if not hasattr(self, "phone_type"):
            self.phone_type = None
        if not hasattr(self, "residency"):
            self.residency = None
        if not hasattr(self, "sms_status"):
            self.sms_status = None
        return

    def destroy(self, botengine):
        """
        This user object is getting destroyed
        :param botengine:
        :return:
        """
        return

    def user_role_updated(
        self,
        botengine,
        location_id,
        user_id,
        role,
        previous_role,
        category,
        previous_category,
        location_access,
        previous_location_access,
        residency,
        previous_residency,
    ):
        """
        A user changed roles
        :param botengine: BotEngine environment
        :param location_id: Location ID
        :param user_id: User ID that changed
        :param role: ROLE_TYPE_* Application-layer agreed upon role integer which may auto-configure location_access and alert category
        :param previous_role: User's previous role, if any
        :param category: ALERT_CATEGORY_* User's current alert/communications category (1=resident; 2=supporter)
        :param previous_category: User's previous category, if any
        :param location_access: LOCATION_ACCESS_* User's current access to the location
        :param previous_location_access: User's previous access to the location, if any
        :param residency: RESIDENCY_* User's current residency status
        :param previous_residency: User's previous residency status, if any
        :return:
        """
        return

    def is_birthday_upcoming(self, botengine, threshold_days=7):
        """
        Check if the user's birthday is upcoming within the specified threshold
        :param botengine: BotEngine environment
        :param threshold_days: Number of days to check for upcoming birthday
        :return: True if birthday is upcoming, False otherwise
        """
        from datetime import datetime, timedelta

        if not self.birth_date:
            return False

        # Get current date in the botengine timezone
        current_date = self.location_object.get_local_datetime(botengine)

        # Parse birth date
        birth_date_obj = self.location_object.timezone_aware_datetime(botengine, datetime.strptime(self.birth_date, "%Y-%m-%d"))
        this_year_birthday = birth_date_obj.replace(year=current_date.year)

        # If birthday has already occurred this year, check next year's birthday
        if this_year_birthday < current_date:
            this_year_birthday = this_year_birthday.replace(year=current_date.year + 1)

        # Calculate days until birthday
        days_until_birthday = (this_year_birthday - current_date).days

        return days_until_birthday <= threshold_days
    
    def next_birthday_timestamp_ms(self, botengine):
        """
        Get the timestamp of the user's next birthday in milliseconds
        :param botengine: BotEngine environment
        :return: Timestamp of next birthday in milliseconds, or None if birth date is not set
        """
        from datetime import datetime

        if not self.birth_date:
            return None

        # Get current date in the botengine timezone
        current_date = self.location_object.get_local_datetime(botengine)

        # Parse birth date
        birth_date_obj = self.location_object.timezone_aware_datetime(botengine, datetime.strptime(self.birth_date, "%Y-%m-%d"))
        this_year_birthday = birth_date_obj.replace(year=current_date.year)

        # If birthday has already occurred this year, check next year's birthday
        if this_year_birthday < current_date:
            this_year_birthday = this_year_birthday.replace(year=current_date.year + 1)

        # Return timestamp in milliseconds
        return int(this_year_birthday.timestamp() * 1000)
    
    def full_name(self):
        """
        Get the user's full name by combining first and last name
        :return: Full name string
        """
        return f"{self.first_name} {self.last_name}".strip()