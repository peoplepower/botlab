#!/usr/bin/env python
# encoding: utf-8
'''
Created on January 4, 2019

@author: David Moss
'''

from enum import Enum

class TrendsReportTestCase(Enum):
    GENERATE_REPORT = 1
    GENERATE_REPORT_NO_LLM = 2

    def content(self) -> dict:
        if self == TrendsReportTestCase.GENERATE_REPORT:
            return {
                "test_case": "generate_report",
            }
        elif self == TrendsReportTestCase.GENERATE_REPORT_NO_LLM:
            return {
                "test_case": "generate_report",
                "disable_llm": True,
            }
        return {}



# Data Stream Address
DATASTREAM_ADDRESS = "trends_report_run_test"

DATASTREAM_CONTENT = TrendsReportTestCase.GENERATE_REPORT_NO_LLM.content()


# input function behaves differently in Python 2.x and 3.x. And there is no raw_input in 3.x.
if hasattr(__builtins__, 'raw_input'):
    input=raw_input

import requests
import sys
import json
import logging

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter

# Requests session
session = None

def main(argv=None):

    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)
        
    parser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter)
    
    parser.add_argument("-u", "--username", dest="username", help="Admin Username")
    parser.add_argument("-p", "--password", dest="password", help="Admin Password")
    parser.add_argument("-s", "--server", dest="server", help="Base server URL (app.peoplepowerco.com)")
    parser.add_argument("-o", "--organization", dest="organization_id", help="Organization ID")
    parser.add_argument("-a", "--api_key", dest="apikey", help="Admin User's API key instead of a username/password")
    parser.add_argument("--httpdebug", dest="httpdebug", action="store_true", help="HTTP debug logger output");
    
    # Process arguments
    args, unknown = parser.parse_known_args()
    
    # Extract the arguments
    username = args.username
    password = args.password
    server = args.server
    httpdebug = args.httpdebug
    app_key = args.apikey
    organization_id = args.organization_id

    if organization_id is not None:
        organization_id = int(organization_id)
        print(Color.BOLD + "Organization ID: {}".format(organization_id) + Color.END)

    # Define the bot server
    if not server:
        server = "https://app.peoplepowerco.com"
    
    if "http" not in server:
        server = "https://" + server

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
        app_key, user_info = _login(server, username, password)

    send_datastream_message(server, app_key, organization_id, DATASTREAM_ADDRESS, DATASTREAM_CONTENT)
    print("Done!")

def send_datastream_message(server, app_key, organization_id, address, content):
    http_headers = {"API_KEY": app_key, "Content-Type": "application/json"}
    
    params = {
              "address": address,
              "scope": 2,
              "organizationId": organization_id
              }
    
    body = {
        "feed": content
        }
    print("Sending datastream message to {} with address '{}' and content:".format(server, address))
    print("Body: " + json.dumps(body, indent=2, sort_keys=True))
    print("Server: " + server)
    
    r = requests.post(server + "/cloud/appstore/stream", params=params, data=json.dumps(body), headers=http_headers)
    j = json.loads(r.text)
    _check_for_errors(j)
    print(str(r.text))


def _session():
    """
    Retrieve the current HTTP session
    :return: Requests session
    """
    global session
    if session is None:
        session = requests.Session()
        session.headers.update({
            'Content-Type': 'application/json'
        })

    return session


def _login(server, username, password, cache_api_key=True):
    """Get an Bot API key and User Info by login with a username and password"""
    if not username:
        username_hint = 'Admin email address: '

        if hasattr(__builtins__, 'raw_input'):
            username = raw_input(username_hint)
        else:
            username = input(username_hint)

    if not password:
        import getpass
        password = getpass.getpass('Password: ')

    try:
        import pickle
        import requests
        import os

        type = "admin"

        fixed_server = server.replace("http://", "").replace("https://", "").split(".")[0]

        filename = "{}.{}.{}".format(username, fixed_server, type)

        get_app_key = False
        if cache_api_key:
            if os.path.isfile(filename):
                try:
                    with open(filename, 'rb') as f:
                        key = pickle.load(f)

                    params = {
                        "keyType": 11,
                        "expiry": -1
                    }

                    http_headers = {"API_KEY": key, "Content-Type": "application/json"}
                    r = _session().get(server + "/cloud/json/loginByKey", params=params, headers=http_headers)
                    j = json.loads(r.text)

                    if j['resultCode'] == 0:
                        app_key = j['key']

                        with open(filename, 'wb') as f:
                            pickle.dump(app_key, f)

                        get_app_key = True
                except ValueError:
                    # Can't unpickle the local file.
                    # This happens as we switch back to Python 2.7 from Python 3.7.
                    pass

        if not get_app_key:
            params = {
                "username": username
            }
            params['keyType'] = 11

            # login by username and password
            http_headers = {"PASSWORD": password, "Content-Type": "application/json"}
            r = requests.get(server + "/cloud/json/login", params=params, headers=http_headers)
            j = json.loads(r.text)
            if j['resultCode'] == 17:
                passcode = input('Type in the passcode you received on your phone: ')
                passcode = passcode.upper()
                params['expiry'] = -1
                http_headers['passcode'] = passcode
                r = _session().get(server + "/cloud/json/login", params=params, headers=http_headers)
                j = json.loads(r.text)

                if j['resultCode'] == 0:
                    app_key = j['key']
                    if cache_api_key:
                        with open(filename, 'wb') as f:
                            pickle.dump(app_key, f)
            else:
                app_key = j['key']

            _check_for_errors(j)

        # get user info
        http_headers = {"API_KEY": app_key, "Content-Type": "application/json"}
        r = requests.get(server + "/cloud/json/user", headers=http_headers)
        j = json.loads(r.text)
        try:
            _check_for_errors(j)
        except Exception as e:
            print("Couldn't download user info: {}".format(json.dumps(j, indent=2, sort_keys=True)))
            exit(-1)

        return app_key, j

    except BotError as e:
        sys.stderr.write("Error: " + e.msg)
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




