#!/usr/bin/env python3
"""
Clear Organization Report Cache Tool
=====================================

This tool clears an organization's report cache, allowing you to start fresh
with new test data.

Actions performed:
- Sends 'clear_report_cache' datastream message to organization bot
- Organization will clear its cached reports
- Report variables (master, wellness, tech) are preserved

Usage:
    python clear_report_cache.py -o <organization_id> -u <username> -p <password>
    python clear_report_cache.py -o <organization_id> -a <api_key>

Example:
    python clear_report_cache.py -o 12345 -u admin@example.com -p secret
    python clear_report_cache.py -o 12345 -a ABCDEF123456 -s sbox.peoplepowerco.com
"""

import json
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from datetime import datetime

from api_utils import Color, add_auth_arguments, authenticate, send_datastream_message


# Datastream address matching runtime.json
DATASTREAM_ADDRESS = "clear_report_cache"


def clear_report_cache(server, app_key, organization_id, auto_confirm=False):
    """
    Clear report cache for an organization.

    :param server: Server URL
    :param app_key: API key
    :param organization_id: Organization ID
    :param auto_confirm: Skip confirmation prompt (for automated workflows)
    """
    print(f"\n{Color.BOLD}Clear Organization Report Cache{Color.END}")
    print(f"  Organization ID: {organization_id}")
    print(f"  Action: Clear cached reports (preserving generated reports)")
    print()

    if not auto_confirm:
        print(f"{Color.YELLOW}WARNING: This will clear ALL cached reports from locations{Color.END}")
        print("  (Generated master reports will be preserved)")
        print()
        response = input("Are you sure you want to continue? (yes/no): ")

        if response.lower() not in ['yes', 'y']:
            print(f"\n{Color.RED}Operation cancelled{Color.END}")
            return

    content = {
        "clear_cache": True,
        "preserve_reports": True,
        "timestamp_ms": int(datetime.now().timestamp() * 1000),
        "trigger_source": "cli_tool"
    }

    print()
    print("Sending datastream message:")
    print(json.dumps({"address": DATASTREAM_ADDRESS, "content": content}, indent=2))
    print()

    send_datastream_message(server, app_key, organization_id, DATASTREAM_ADDRESS, content)

    print(f"{Color.GREEN}Done!{Color.END} Cache clear message sent.")
    print()
    print("Organization bot will:")
    print("  1. Clear 'org_report_cache' state variable")
    print("  2. Reset report counter to 0")
    print("  3. Preserve report variables (master, wellness, tech)")
    print("  4. Log cache clear event")
    print()


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    parser = ArgumentParser(
        description='Clear report cache for an organization',
        formatter_class=RawDescriptionHelpFormatter
    )
    add_auth_arguments(parser)

    args, _ = parser.parse_known_args()
    server, app_key, organization_id = authenticate(args)

    if organization_id is None:
        print(f"{Color.RED}Error: Organization ID is required (-o){Color.END}")
        sys.exit(1)

    clear_report_cache(server, app_key, organization_id)


if __name__ == "__main__":
    sys.exit(main())
