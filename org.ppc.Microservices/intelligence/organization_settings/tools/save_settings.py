#!/usr/bin/env python
# encoding: utf-8
'''
Created on June 19, 2016

@author: David Moss
'''

datastream_address = "save_settings"

setting_name = "tou_schedule"

setting_value = {
    "summer_weekday_morning_medium_schedule": "0 0 6 ? MAY-OCT MON-FRI *",
    "summer_weekday_morning_medium_tier": 1,
    "summer_weekday_morning_medium_description": "Summer Morning Shoulder - Starting 6:00 AM Monday-Friday; May-October.",

    "summer_weekday_high_schedule": "0 0 13 ? MAY-OCT MON-FRI *",
    "summer_weekday_high_tier": 2,
    "summer_weekday_high_description": "Summer Peak Pricing - Starting 1:00 PM Monday-Friday; May-October.",

    "summer_weekday_evening_medium_schedule": "0 0 18 ? MAY-OCT MON-FRI *",
    "summer_weekday_evening_medium_tier": 1,
    "summer_weekday_evening_medium_description": "Summer Evening Shoulder - Starting 6:00 PM Monday-Friday; May-October.",

    "summer_weekday_low_schedule": "0 0 23 ? MAY-OCT MON-FRI *",
    "summer_weekday_low_tier": 0,
    "summer_weekday_low_description": "Summer Off-Peak Pricing - Starting 11:00 PM Monday-Friday; May-October.",


    "summer_weekend_medium_schedule": "0 0 6 ? MAY-OCT SAT,SUN *",
    "summer_weekend_medium_tier": 1,
    "summer_weekend_medium_description": "Summer Weekend Daytime Pricing - Starting 6:00 AM Saturday and Sunday; May-October.",

    "summer_weekend_low_schedule": "0 0 23 ? MAY-OCT SAT,SUN *",
    "summer_weekend_low_tier": 0,
    "summer_weekend_low_description": "Summer Weekend Off-Peak Pricing - Starting 11:00 PM Saturday and Sunday; May-October.",


    "winter_weekday_morning_medium_schedule": "0 0 5 ? NOV-APR MON-FRI *",
    "winter_weekday_morning_medium_tier": 1,
    "winter_weekday_morning_medium_description": "Winter Morning Shoulder - Starting 5:00 AM Monday-Friday; November-April.",

    "winter_weekday_high_schedule": "0 0 6 ? NOV-APR MON-FRI *",
    "winter_weekday_high_tier": 2,
    "winter_weekday_high_description": "Winter Peak Pricing - Starting 6:00 AM Monday-Friday; November-April.",

    "winter_weekday_afternoon_medium_schedule": "0 0 10 ? NOV-APR MON-FRI *",
    "winter_weekday_afternoon_medium_tier": 1,
    "winter_weekday_afternoon_description": "Winter Afternoon Shoulder - Starting 10:00 AM Monday-Friday; November-April.",

    "winter_weekday_low_schedule": "0 0 23 ? NOV-APR MON-FRI *",
    "winter_weekday_low_tier": 0,
    "winter_weekday_low_description": "Winter Off-Peak Pricing - Starting 11:00 PM Monday-Friday; November-April.",


    "winter_weekend_medium_schedule": "0 0 6 ? NOV-APR SAT,SUN *",
    "winter_weekend_medium_tier": 1,
    "winter_weekend_medium_description": "Winter Weekend Daytime Pricing - Starting 6:00 AM Saturday and Sunday; November-April.",

    "winter_weekend_low_schedule": "0 0 23 ? NOV-APR SAT,SUN *",
    "winter_weekend_low_tier": 0,
    "winter_weekend_low_description": "Winter Weekend Off-Peak Pricing - Starting 11:00 PM Saturday and Sunday; November-April."
}


import requests
import sys
import json
import threading
import time
import logging

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter


def main(argv=None):

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)
        
    parser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter)
    
    parser.add_argument("--admin_username", dest="admin_username", help="Username")
    parser.add_argument("--admin_password", dest="admin_password", help="Password")
    parser.add_argument("-o", "--organization_id", dest="organization_id", help="Organization ID")
    parser.add_argument("-a", "--apikey", dest="user_key", help="User API Key")
    parser.add_argument("-s", "--server", dest="server", help="Base server URL (app.peoplepowerco.com)")
    parser.add_argument("--httpdebug", dest="httpdebug", action="store_true", help="HTTP debug logger output");
    
    # Process arguments
    args, dump = parser.parse_known_args()
    
    # Extract the arguments
    username = args.admin_username
    password = args.admin_password
    server = args.server
    httpdebug = args.httpdebug
    app_key = args.user_key
    
    # Define the bot server
    if not server:
        server = "https://app.peoplepowerco.com"
    
    if "http" not in server:
        server = "https://" + server

    if  args.organization_id is None:
        print(Color.BOLD + Color.RED + "Please pass in an organization ID with -o <org id>\n\n" + Color.END)
        return

    # HTTP Debugging
    if httpdebug:
        try:
            import http.client as http_client
                
        except ImportError:
            # Python 2
            import httplib as http_client
            http_client.HTTPConnection.debuglevel = 1
                    
        # You must initialize logging, otherwise you'll not see debug output.
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    # Login to your user account
    if app_key is None:
        app_key = _login(server, username, password, admin=True)

    content = setting_value
    content['address'] = setting_name

    send_datastream_message(server, app_key, datastream_address, content, args.organization_id)

        
def send_datastream_message(server, app_key, address, content, organization_id):
    http_headers = {"API_KEY": app_key, "Content-Type": "application/json"}
    
    params = {
              "address": address,
              "scope": 2,
              "organizationId": organization_id
              }
    
    body = {
        "feed": content
        }
    
    print("Body: " + json.dumps(body, indent=2, sort_keys=True))
    print("Server: " + server)
    
    r = requests.post(server + "/cloud/appstore/stream", params=params, data=json.dumps(body), headers=http_headers)
    j = json.loads(r.text)
    _check_for_errors(j)


def _login(server, username, password, admin=False):
    """
    Login and obtain an API key
    :param server: Server address
    :param username: Username
    :param password: Password
    :return: API Key
    """
    global _https_proxy
    import pickle
    import os

    if not username:
        username = input('Email address: ')

    if not password:
        import getpass
        password = getpass.getpass()

    try:
        import requests

        type = "user"
        if admin:
            type = "admin"

        fixed_server = server.replace("http://", "").replace("https://", "").split(".")[0]

        filename = "{}.{}.{}".format(username, fixed_server, type)

        if os.path.isfile(filename):
            with open(filename, 'rb') as f:
                key = pickle.load(f)

            params = {
                "keyType": 0
            }

            if admin:
                params['keyType'] = 11
                params['expiry'] = 2

            http_headers = {"API_KEY": key, "Content-Type": "application/json"}
            r = requests.get(server + "/cloud/json/loginByKey", params=params, headers=http_headers)
            j = json.loads(r.text)

            if j['resultCode'] == 0:
                key = j['key']

                with open(filename, 'wb') as f:
                    pickle.dump(key, f)

                return key

        params = {
            "username": username
        }

        if admin:
            params['keyType'] = 11

        http_headers = {"PASSWORD": password, "Content-Type": "application/json"}
        r = requests.get(server + "/cloud/json/login", params=params, headers=http_headers)
        j = json.loads(r.text)

        if j['resultCode'] == 17:
            passcode = input('Type the passcode you received on your phone: ')

            passcode = passcode.upper()

            params['expiry'] = 2
            http_headers['passcode'] = passcode
            r = requests.get(server + "/cloud/json/login", params=params, headers=http_headers)
            j = json.loads(r.text)

            if j['resultCode'] == 0:
                key = j['key']

                with open(filename, 'wb') as f:
                    pickle.dump(key, f)

        _check_for_errors(j)

        return j['key']

    except BotError as e:
        sys.stderr.write("BotEngine Error: " + e.msg)
        sys.stderr.write("\nCreate an account on " + server + " and use it to sign in")
        sys.stderr.write("\n\n")
        raise e
    
    

def _check_for_errors(json_response):
    """Check some JSON response for BotEngine errors"""
    if not json_response:
        raise BotError("No response from the server!", -1)
    
    if json_response['resultCode'] > 0:
        msg = "Unknown error!"
        if 'resultCodeMessage' in json_response.keys():
            msg = json_response['resultCodeMessage']
        elif 'resultCodeDesc' in json_response.keys():
            msg = json_response['resultCodeDesc']
        raise BotError(msg, json_response['resultCode'])

    del(json_response['resultCode'])
    
    
    
class BotError(Exception):
    """BotEngine exception to raise and log errors."""
    def __init__(self, msg, code):
        super(BotError).__init__(type(self))
        self.msg = msg
        self.code = code
    def __str__(self):
        return self.msg
    def __unicode__(self):
        return self.msg

#===============================================================================
# Color Class for CLI
#===============================================================================
class Color:
    """Color your command line output text with Color.WHATEVER and Color.END"""
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


if __name__ == "__main__":
    sys.exit(main())







    

