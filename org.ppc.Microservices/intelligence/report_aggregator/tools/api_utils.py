#!/usr/bin/env python3
"""
Shared API utilities for report aggregator tools.

Extracted from moorings_park_run_test.py pattern for reuse across all tools.
Handles authentication, session management, datastream messaging, and error handling.
"""

import json
import logging
import requests
import sys


# Requests session
session = None


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


def add_auth_arguments(parser):
    """Add standard authentication arguments to an argument parser."""
    parser.add_argument("-u", "--username", dest="username", help="Admin Username")
    parser.add_argument("-p", "--password", dest="password", help="Admin Password")
    parser.add_argument("-s", "--server", dest="server", help="Base server URL (app.peoplepowerco.com)")
    parser.add_argument("-o", "--organization", dest="organization_id", help="Organization ID")
    parser.add_argument("-a", "--api_key", dest="apikey", help="Admin User's API key instead of a username/password")
    parser.add_argument("--httpdebug", dest="httpdebug", action="store_true", help="HTTP debug logger output")


def setup_server(server):
    """Normalize the server URL."""
    if not server:
        server = "https://app.peoplepowerco.com"
    if "http" not in server:
        server = "https://" + server
    return server


def setup_http_debug():
    """Enable HTTP debugging output."""
    try:
        import http.client as http_client
    except ImportError:
        import httplib as http_client
        http_client.HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


def _session():
    """
    Retrieve the current HTTP session.
    :return: Requests session
    """
    global session
    if session is None:
        session = requests.Session()
        session.headers.update({
            'Content-Type': 'application/json'
        })
    return session


def login(server, username, password, cache_api_key=True):
    """
    Get an API key and User Info by logging in with a username and password.

    :param server: Server URL
    :param username: Admin username/email
    :param password: Admin password
    :param cache_api_key: Whether to cache the API key locally
    :return: Tuple of (app_key, user_info)
    """
    if not username:
        username = input('Admin email address: ')

    if not password:
        import getpass
        password = getpass.getpass('Password: ')

    try:
        import pickle
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
                    pass

        if not get_app_key:
            params = {
                "username": username,
                "keyType": 11
            }

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

        # Get user info
        http_headers = {"API_KEY": app_key, "Content-Type": "application/json"}
        r = requests.get(server + "/cloud/json/user", headers=http_headers)
        j = json.loads(r.text)
        try:
            _check_for_errors(j)
        except Exception:
            print("Couldn't download user info: {}".format(json.dumps(j, indent=2, sort_keys=True)))
            exit(-1)

        return app_key, j

    except BotError as e:
        sys.stderr.write("Error: " + e.msg)
        sys.stderr.write("\nCreate an account on " + server + " and use it to sign in")
        sys.stderr.write("\n\n")
        raise e


def send_datastream_message(server, app_key, organization_id, address, content):
    """
    Send a datastream message to an organization bot.

    :param server: Server URL
    :param app_key: API key
    :param organization_id: Organization ID
    :param address: Datastream address
    :param content: Message content dict
    """
    http_headers = {"API_KEY": app_key, "Content-Type": "application/json"}

    params = {
        "address": address,
        "scope": 2,
        "organizationId": organization_id
    }

    body = {
        "feed": content
    }

    r = requests.post(server + "/cloud/appstore/stream", params=params, data=json.dumps(body), headers=http_headers)
    j = json.loads(r.text)
    _check_for_errors(j)
    return j


def _check_for_errors(json_response):
    """Check some JSON response for BotEngine errors."""
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


def authenticate(args):
    """
    Common authentication flow from parsed CLI arguments.

    :param args: Parsed argparse namespace with username, password, server, apikey, httpdebug, organization_id
    :return: Tuple of (server, app_key, organization_id)
    """
    server = setup_server(args.server)

    if args.httpdebug:
        setup_http_debug()

    organization_id = args.organization_id
    if organization_id is not None:
        organization_id = int(organization_id)
        print(Color.BOLD + "Organization ID: {}".format(organization_id) + Color.END)

    app_key = args.apikey
    if app_key is None:
        app_key, user_info = login(server, args.username, args.password)

    return server, app_key, organization_id
