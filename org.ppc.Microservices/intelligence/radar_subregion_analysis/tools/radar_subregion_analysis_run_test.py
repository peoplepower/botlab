#!/usr/bin/env python
# encoding: utf-8
"""
Created on May 4, 2026

@author: Destry Teeter

CLI launcher for the radar_subregion_analysis organization microservice.

Sends a `radar_subregion_analysis_run` datastream message scoped to a specific
organization, telling the org bot to compile and email the radar subregion PDF.

Examples:
    python radar_subregion_analysis_run_test.py \\
        -u admin@example.com -p 'pw' -o 1234 --email destry@caredaily.ai

    python radar_subregion_analysis_run_test.py \\
        -a $APP_KEY -o 1234 --email destry@caredaily.ai --email ops@caredaily.ai
"""

import json
import logging
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import requests

# Data Stream Address
DATASTREAM_ADDRESS = "radar_subregion_analysis_run"

session = None


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    parser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument("-u", "--username", dest="username", help="Admin Username")
    parser.add_argument("-p", "--password", dest="password", help="Admin Password")
    parser.add_argument(
        "-s",
        "--server",
        dest="server",
        help="Base server URL (e.g. app.peoplepowerco.com)",
    )
    parser.add_argument(
        "-o",
        "--organization",
        dest="organization_id",
        help="Organization ID",
    )
    parser.add_argument(
        "-a",
        "--api_key",
        dest="apikey",
        help="Admin User's API key instead of a username/password",
    )
    parser.add_argument(
        "--email",
        dest="emails",
        action="append",
        default=[],
        help="Recipient email address (repeat for multiple)",
    )
    parser.add_argument(
        "--name",
        dest="analysis_name",
        default="Radar Subregion Analysis",
        help="Display name for the analysis",
    )
    parser.add_argument(
        "--httpdebug",
        dest="httpdebug",
        action="store_true",
        help="HTTP debug logger output",
    )

    args, _ = parser.parse_known_args()

    username = args.username
    password = args.password
    server = args.server or "https://app.peoplepowerco.com"
    if "http" not in server:
        server = "https://" + server
    httpdebug = args.httpdebug
    app_key = args.apikey
    organization_id = args.organization_id

    if not args.emails:
        sys.stderr.write(
            "Error: at least one --email is required to deliver the report.\n"
        )
        sys.exit(2)

    if organization_id is None:
        sys.stderr.write("Error: --organization is required.\n")
        sys.exit(2)
    organization_id = int(organization_id)
    print(Color.BOLD + f"Organization ID: {organization_id}" + Color.END)

    if httpdebug:
        try:
            import http.client as http_client
        except ImportError:
            import httplib as http_client  # type: ignore
        http_client.HTTPConnection.debuglevel = 1
        logging.basicConfig()
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True

    if app_key is None:
        app_key, _ = _login(server, username, password)

    content = {
        "email_addresses": args.emails,
        "analysis_name": args.analysis_name,
    }

    send_datastream_message(
        server, app_key, organization_id, DATASTREAM_ADDRESS, content
    )
    print("Done!")


def send_datastream_message(server, app_key, organization_id, address, content):
    http_headers = {"API_KEY": app_key, "Content-Type": "application/json"}

    params = {
        "address": address,
        "scope": 2,
        "organizationId": organization_id,
    }
    body = {"feed": content}
    print(
        f"Sending datastream message to {server} with address '{address}' and content:"
    )
    print("Body: " + json.dumps(body, indent=2, sort_keys=True))
    print("Server: " + server)

    r = requests.post(
        server + "/cloud/appstore/stream",
        params=params,
        data=json.dumps(body),
        headers=http_headers,
    )
    j = json.loads(r.text)
    _check_for_errors(j)
    print(str(r.text))


def _session():
    global session
    if session is None:
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
    return session


def _login(server, username, password, cache_api_key=True):
    """Get a Bot API key by logging in with a username and password."""
    if not username:
        username = input("Admin email address: ")
    if not password:
        import getpass

        password = getpass.getpass("Password: ")

    import os
    import pickle

    fixed_server = server.replace("http://", "").replace("https://", "").split(".")[0]
    filename = f"{username}.{fixed_server}.admin"

    app_key = None
    if cache_api_key and os.path.isfile(filename):
        try:
            with open(filename, "rb") as f:
                key = pickle.load(f)
            params = {"keyType": 11, "expiry": -1}
            http_headers = {"API_KEY": key, "Content-Type": "application/json"}
            r = _session().get(
                server + "/cloud/json/loginByKey",
                params=params,
                headers=http_headers,
            )
            j = json.loads(r.text)
            if j.get("resultCode") == 0:
                app_key = j["key"]
                with open(filename, "wb") as f:
                    pickle.dump(app_key, f)
        except (ValueError, OSError):
            app_key = None

    if app_key is None:
        params = {"username": username, "keyType": 11}
        http_headers = {"PASSWORD": password, "Content-Type": "application/json"}
        r = requests.get(
            server + "/cloud/json/login", params=params, headers=http_headers
        )
        j = json.loads(r.text)
        if j.get("resultCode") == 17:
            passcode = input(
                "Type in the passcode you received on your phone: "
            ).upper()
            params["expiry"] = -1
            http_headers["passcode"] = passcode
            r = _session().get(
                server + "/cloud/json/login", params=params, headers=http_headers
            )
            j = json.loads(r.text)
            if j.get("resultCode") == 0:
                app_key = j["key"]
                if cache_api_key:
                    with open(filename, "wb") as f:
                        pickle.dump(app_key, f)
        else:
            app_key = j.get("key")
        _check_for_errors(j)

    http_headers = {"API_KEY": app_key, "Content-Type": "application/json"}
    r = requests.get(server + "/cloud/json/user", headers=http_headers)
    j = json.loads(r.text)
    _check_for_errors(j)
    return app_key, j


def _check_for_errors(json_response):
    if not json_response:
        raise BotError("No response from the server!", -1)
    if json_response.get("resultCode", 0) > 0:
        msg = json_response.get(
            "resultCodeMessage", json_response.get("resultCodeDesc", "Unknown error!")
        )
        raise BotError(msg, json_response["resultCode"])
    json_response.pop("resultCode", None)


class BotError(Exception):
    def __init__(self, msg, code):
        super().__init__(msg)
        self.msg = msg
        self.code = code

    def __str__(self):
        return self.msg


class Color:
    BOLD = "\033[1m"
    END = "\033[0m"


if __name__ == "__main__":
    sys.exit(main())
