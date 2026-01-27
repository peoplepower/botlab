#!/usr/bin/env python
# encoding: utf-8
'''
Created on June 19, 2016

@author: David Moss
'''

datastream_address = "get_settings"


# input function behaves differently in Python 2.x and 3.x. And there is no raw_input in 3.x.
if hasattr(__builtins__, 'raw_input'):
    input=raw_input

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
    
    parser.add_argument("-u", "--username", dest="username", help="Username")
    parser.add_argument("-p", "--password", dest="password", help="Password")
    parser.add_argument("-o", "--organization_id", dest="organization_id", help="Organization ID")
    parser.add_argument("-a", "--apikey", dest="user_key", help="User API Key")
    parser.add_argument("-s", "--server", dest="server", help="Base server URL (app.peoplepowerco.com)")
    parser.add_argument("--httpdebug", dest="httpdebug", action="store_true", help="HTTP debug logger output");
    
    # Process arguments
    args = parser.parse_args()
    
    # Extract the arguments
    username = args.username
    password = args.password
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

    send_datastream_message(server, app_key, datastream_address, None, args.organization_id)

        
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
        username = raw_input('Email address: ')

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
            passcode = raw_input('Type in the passcode you received on your phone: ')

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







    

