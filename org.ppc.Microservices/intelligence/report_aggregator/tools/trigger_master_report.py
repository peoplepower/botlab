#!/usr/bin/env python3
"""
Trigger Master Report Generation Tool
======================================

This tool sends a datastream message to an organization bot to trigger
the generation of a master report, which will then be emailed to administrators.

Usage:
    python trigger_master_report.py -o <organization_id> -u <username> -p <password>
    python trigger_master_report.py -o <organization_id> -a <api_key>

Example:
    python trigger_master_report.py -o 12345 -u admin@example.com -p secret
    python trigger_master_report.py -o 12345 -a ABCDEF123456 -s sbox.peoplepowerco.com
"""

import json
import sys

from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter

from api_utils import add_auth_arguments, authenticate, send_datastream_message, Color


# Datastream address matching runtime.json
DATASTREAM_ADDRESS = "generate_master_report"


def trigger_master_report(server, app_key, organization_id):
    """
    Trigger master report generation for an organization.

    :param server: Server URL
    :param app_key: API key
    :param organization_id: Organization ID
    """
    content = {
        "force_generation": True,
        "include_weekly_synthesis": False,
        "trigger_source": "cli_tool"
    }

    print(f"\n{Color.BOLD}Triggering master report generation...{Color.END}")
    print(f"  Server: {server}")
    print(f"  Organization: {organization_id}")
    print(f"  Address: {DATASTREAM_ADDRESS}")
    print(f"  Content: {json.dumps(content, indent=2)}")
    print()

    send_datastream_message(server, app_key, organization_id, DATASTREAM_ADDRESS, content)

    print(f"{Color.GREEN}Done!{Color.END} Master report generation triggered.")
    print()
    print("Organization bot will:")
    print("  1. Load cached reports from locations")
    print("  2. Run rules engine preprocessing")
    print("  3. Build deterministic report structure")
    print("  4. Enhance text with LLM (section-by-section)")
    print("  5. Extract persona reports (wellness, tech)")
    print("  6. Email reports to administrators")
    print()
    print(f"Expected processing time: 30-60 seconds")
    print(f"Check organization bot logs for status updates")
    print()


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    parser = ArgumentParser(
        description='Trigger master report generation for an organization',
        formatter_class=RawDescriptionHelpFormatter
    )
    add_auth_arguments(parser)

    args, unknown = parser.parse_known_args()
    server, app_key, organization_id = authenticate(args)

    if organization_id is None:
        print(f"{Color.RED}Error: Organization ID is required (-o){Color.END}")
        sys.exit(1)

    trigger_master_report(server, app_key, organization_id)


if __name__ == "__main__":
    sys.exit(main())
