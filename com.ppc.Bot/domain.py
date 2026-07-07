'''
Created on May 25, 2017

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
'''

import utilities.utilities as utilities


############### BRANDING AND ORGANIZATION ###############
# Organization short name, which allows us to send emails to this organization's administrators
ORGANIZATION_SHORT_NAME = ""

# NOTE: Name of the service
SERVICE_NAME = ""

# True if this is a free service, to deactivate specific paid features without forking microservice packages
FREE_SERVICE = False

# Name of the pack of products people can purchase
PACK_NAME = ""

# URL to purchase the pack of products
PACK_PURCHASE_URL = ""

# Notification case-sensitive brand, which can be different from the organization short name. 
# Use this to force a specific branded template.
ORGANIZATION_BRAND = ""

# Default language for this brand
DEFAULT_LANGUAGE = 'en'

# Default timezone for this brand
DEFAULT_TIMEZONE = 'US/Pacific'

# The model IDs that define the available bundle of devices in our pack for this service.
PACK_INSTALLATION_MODEL_IDS = ["gateway", "devGateway"]

# Automatic tagging for people who run this service.
ADD_TAGS = ["family_internal"]
REMOVE_TAGS = ["family_release", "family_free"]

############### ORGANIZATION ADMIN MONITORING ###############
# True to allow for monitoring by organizational administrators via email alerts
ALLOW_ADMINISTRATIVE_MONITORING = True

# Email addresses to alert before the emergency call center.
# If this is None or not defined, then all organization admins will be contacted when admin monitoring is enabled.
ADMIN_EMAIL_ADDRESSES = []

# Don't contact admins before this hour of the day
DO_NOT_CONTACT_ADMINS_BEFORE_RELATIVE_HOUR = 6.0

# Don't contact admins after this hour of the day
DO_NOT_CONTACT_ADMINS_AFTER_RELATIVE_HOUR = 22.0

# Timezone admins are in
ADMIN_DEFAULT_TIMEZONE = "US/Pacific"

# Command Center URLs
COMMAND_CENTER_URLS = {
    "app.peoplepowerco.com": "",
    "sboxall.peoplepowerco.com": ""
}

# Blog Url
BLOG_URL = ""

############### PROFESSIONAL MONITORING ###############
# Professional Monitoring Subscription Name
PROFESSIONAL_MONITORING_SUBSCRIPTION_NAME = ""

# Professional Monitoring Callback Number
PROFESSIONAL_MONITORING_CALLBACK_NUMBER = ""


############### CONFIGURATION ###############
# User facing modes. { "MODE": "User Facing Name" }
USER_FACING_MODES = {
    "HOME": "OFF",
    "AWAY": "AWAY",
    "STAY": "STAY",
    "TEST": "TEST"
}

############### ANALYTICS ###############
# MixPanel token
MIXPANEL_TOKEN = None 

# Amplitude tokens
AMPLITUDE_TOKENS = {
    "app.peoplepowerco.com": "",
    "sboxall.peoplepowerco.com": ""
}


############### APP DOWNLOAD ###############
# Since this bot is leveraged by multiple brands,
# set these properties as organization properties on the server 
# for the top-level organization.

# Promote mobile app download via SMS
RECOMMEND_APP_VIA_SMS = False

# iOS download URL - set to None because SMS's containing URLs are blocked
APP_IOS_URL = None 

# Android download URL - set to None because SMS's containing URLs are blocked
APP_ANDROID_URL = None 

# iOS App Store name (used when APP_IOS_URL is not available for SMS invites)
APP_IOS_STORE_NAME = None

# Android Play Store name (used when APP_ANDROID_URL is not available for SMS invites)
APP_ANDROID_STORE_NAME = None

# Ask for a rating when a user replies that we did a good job.
APP_ASK_FOR_RATING_ON_APPSTORE = False

############### CUSTOMER SUPPORT ###############
# Customer support calendar scheduling and assisted connect URL
CS_SCHEDULE_URL = None # 

# Customer support help desk URL
CS_HELPDESK_URL = None

# Customer support email
CS_EMAIL_ADDRESS = ""

# Customer support phone number
CS_PHONE_NUMBER = None

# After creating a new location and firing up the bot for the first time, how long do we wait before suggesting a virtual install session?
CS_VIRTUAL_CONNECT_SMS_DELAY_MS = utilities.ONE_HOUR_MS * 4

############### OPEN AI ###############

# OpenAI Organization ID
OPEN_AI_ORGANIZATIONS = {
    "app.peoplepowerco.com": "",
    "sboxall.peoplepowerco.com": ""
}

############### INTREX ###############

# Bundle-level default mapping of an Intrex deactivationOptionName to its alert classification: "real" or "false_alarm".
# The enum of options is configurable on the Intrex platform; organization properties override this.
# Used by the intrex microservice to keep staff-confirmed false alarms out of existing trend metrics.
INTREX_DEACTIVATION_OPTIONS = {
    "Emergency": "real",
}
