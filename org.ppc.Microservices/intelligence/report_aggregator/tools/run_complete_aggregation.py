#!/usr/bin/env python3
"""
Complete Organization Report Testing Workflow
==============================================

This script runs the complete testing workflow:
1. Clear existing cache
2. Generate synthetic test reports
3. Trigger master report generation
4. Display summary and next steps

Usage:
    python run_complete_test.py -o <organization_id> -u <username> -p <password> [--count 25]
    python run_complete_test.py -o <organization_id> -a <api_key> [--count 25]

Example:
    python run_complete_test.py -o 12345 -u admin@example.com -p secret --count 25
"""

import sys
import time
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from datetime import datetime

from api_utils import Color, add_auth_arguments, authenticate
from clear_report_cache import clear_report_cache
from generate_test_reports import generate_test_reports
from trigger_master_report import trigger_master_report


def print_header(title):
    """Print formatted section header."""
    print(f"\n{'='*70}")
    print(f"{title.center(70)}")
    print(f"{'='*70}\n")


def run_complete_workflow(server, app_key, organization_id, location_count=25):
    """
    Run complete testing workflow.

    :param server: Server URL
    :param app_key: API key
    :param organization_id: Organization ID
    :param location_count: Number of virtual locations
    """
    start_time = time.time()

    print_header("ORGANIZATION REPORT TESTING WORKFLOW")
    print(f"Organization ID: {organization_id}")
    print(f"Virtual Locations: {location_count}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: Clear cache
    print_header("STEP 1: CLEAR EXISTING CACHE")
    print("Clearing any existing test data from organization cache...")
    print()

    try:
        clear_report_cache(server, app_key, organization_id, auto_confirm=True)
    except Exception as e:
        print(f"{Color.RED}Error clearing cache: {e}{Color.END}")
        print("Continuing anyway...")

    print()
    time.sleep(1)

    # Step 2: Generate test reports
    print_header("STEP 2: GENERATE TEST REPORTS")
    print(f"Generating {location_count} virtual locations with diverse scenarios...")
    print()

    try:
        success_count, error_count = generate_test_reports(server, app_key, organization_id, location_count)
    except Exception as e:
        print(f"{Color.RED}Error generating reports: {e}{Color.END}")
        return

    print()
    time.sleep(2)

    # Step 3: Trigger master report
    print_header("STEP 3: TRIGGER MASTER REPORT")
    print("Requesting organization to generate master report...")
    print()

    try:
        trigger_master_report(server, app_key, organization_id)
    except Exception as e:
        print(f"{Color.RED}Error triggering report: {e}{Color.END}")
        return

    print()

    # Summary
    elapsed_time = time.time() - start_time
    print_header("WORKFLOW COMPLETE")
    print(f"{Color.GREEN}All steps completed in {elapsed_time:.1f} seconds{Color.END}")
    print()
    print("What happened:")
    print(f"  1. Cleared organization {organization_id} cache")
    print(f"  2. Generated {location_count} virtual locations")
    print(f"  3. Sent diverse test reports to organization")
    print(f"  4. Triggered master report generation")
    print()
    print("What's happening now:")
    print("  - Organization bot is processing reports")
    print("  - Rules engine is filtering and sorting")
    print("  - Report builder is creating deterministic structure")
    print("  - LLM is enhancing text section-by-section")
    print("  - Persona reports (wellness, tech) being extracted")
    print("  - Emails being prepared for administrators")
    print()
    print("Expected completion: 30-60 seconds")
    print()
    print("Next steps:")
    print("  1. Check organization bot logs for processing status")
    print("  2. Check admin email for delivered reports")
    print(f"  3. Review generated data: test_reports_org_{organization_id}.json")
    print("  4. Verify report structure and LLM enhancements")
    print()


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    parser = ArgumentParser(
        description='Run complete organization report testing workflow',
        formatter_class=RawDescriptionHelpFormatter
    )
    add_auth_arguments(parser)
    parser.add_argument(
        '--count',
        type=int,
        default=25,
        help='Number of virtual locations to create (default: 25)'
    )

    args, _ = parser.parse_known_args()
    server, app_key, organization_id = authenticate(args)

    if organization_id is None:
        print(f"{Color.RED}Error: Organization ID is required (-o){Color.END}")
        sys.exit(1)

    try:
        run_complete_workflow(server, app_key, organization_id, args.count)
    except KeyboardInterrupt:
        print(f"\n\n{Color.RED}Workflow interrupted by user{Color.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n{Color.RED}Workflow failed: {e}{Color.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
