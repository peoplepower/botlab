#!/usr/bin/env python3
"""
Organization Report Data Generator
===================================

This tool generates synthetic location reports and sends them to an organization bot
to populate its cache with realistic test data.

Features:
- Creates 25 virtual locations with diverse scenarios
- Generates reports across all categories (wellness, IT, safety, energy)
- Includes mix of concerns, resolutions, celebrations, and updates
- Varies severity and days_active for realistic patterns
- Sends reports via 'report_to_org' datastream messages

Usage:
    python generate_test_reports.py -o <organization_id> -u <username> -p <password> [--count 25]
    python generate_test_reports.py -o <organization_id> -a <api_key> [--count 25]

Example:
    python generate_test_reports.py -o 12345 -u admin@example.com -p secret --count 25
"""

import json
import random
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from datetime import datetime

from api_utils import Color, add_auth_arguments, authenticate, send_datastream_message


# Datastream address matching runtime.json
DATASTREAM_ADDRESS = "report_to_org"

# Report constants (matching org.ppc.Bot/signals/report.py)
PRIORITY_CRITICAL = "critical"
PRIORITY_WARNING = "warning"
PRIORITY_INFO = "info"

SENTIMENT_CONCERN = "concern"
SENTIMENT_RESOLUTION = "resolution"
SENTIMENT_UPDATE = "update"
SENTIMENT_CELEBRATION = "celebration"
SENTIMENT_SUMMARY = "summary"

CATEGORY_WELLNESS = "wellness"
CATEGORY_IT = "it"
CATEGORY_SAFETY = "safety"
CATEGORY_ENERGY = "energy"

# Report scenarios by category
WELLNESS_SCENARIOS = [
    {
        "report_type": "stability",
        "priority": PRIORITY_CRITICAL,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "Fall risk detected - 3 near-falls in past 48 hours",
        "short_description": "Multiple stability events detected",
        "long_description": "Resident has experienced 3 near-fall events in the past 48 hours, with 2 occurring during nighttime bathroom visits. Fall risk assessment score has increased from 25 to 75.",
        "concerns": ["Nighttime falls", "Reduced balance", "Poor lighting"],
        "context": "Recent medication change may be affecting balance and coordination",
        "recommended_actions": ["Immediate wellness check", "Review medications", "Install night lights", "Consider PT evaluation"],
        "severity_rank": 92,
        "days_active": 2
    },
    {
        "report_type": "bathroom",
        "priority": PRIORITY_CRITICAL,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "Bathroom visits declined 67% over 3 days",
        "short_description": "Significant decline in bathroom activity",
        "long_description": "Daily bathroom visits have dropped from baseline of 6 visits/day to only 2 visits/day over the past 3 days. This pattern suggests possible dehydration or UTI risk.",
        "concerns": ["Dehydration risk", "Possible UTI", "Reduced fluid intake"],
        "context": "Could indicate illness, mobility issues, or cognitive decline",
        "recommended_actions": ["Call resident immediately", "Assess hydration status", "Schedule urgent wellness check", "Consider urinalysis"],
        "severity_rank": 88,
        "days_active": 3
    },
    {
        "report_type": "sleep",
        "priority": PRIORITY_WARNING,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "Sleep duration declined from 7.5 to 4.2 hours",
        "short_description": "Significant sleep disruption detected",
        "long_description": "Average nightly sleep has decreased by 3.3 hours over the past week. Frequent nighttime wakings (avg 6 per night) and early morning rising (4:30 AM vs usual 7:00 AM).",
        "concerns": ["Sleep deprivation", "Insomnia", "Early morning waking", "Restlessness"],
        "context": "May indicate pain, anxiety, depression, or medication side effects",
        "recommended_actions": ["Contact family to investigate cause", "Review sleep hygiene", "Consider sleep study", "Assess for pain/anxiety"],
        "severity_rank": 75,
        "days_active": 7
    },
    {
        "report_type": "social_isolation",
        "priority": PRIORITY_WARNING,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "No departures from home in 14 days",
        "short_description": "Extended period of social isolation",
        "long_description": "Resident has not left the home in 14 days, with only 2 visitor detections. Previous pattern showed 3-4 outings per week and regular family visits.",
        "concerns": ["Depression risk", "Social withdrawal", "Reduced mobility", "Cognitive decline"],
        "context": "Isolation can accelerate cognitive and physical decline",
        "recommended_actions": ["Wellness check-in call", "Connect with family", "Encourage social activities", "Assess mood and cognition"],
        "severity_rank": 68,
        "days_active": 14
    },
    {
        "report_type": "wellness",
        "priority": PRIORITY_INFO,
        "sentiment": SENTIMENT_CELEBRATION,
        "summary": "Sleep quality improved significantly over past week",
        "short_description": "Sleep patterns normalized",
        "long_description": "After implementing new sleep hygiene routine, resident's sleep has improved from 4.5 hours to 7.5 hours per night. Nighttime wakings reduced from 8 to 2 per night.",
        "concerns": [],
        "context": "Intervention successful - new routine working well",
        "recommended_actions": ["Continue current routine", "Send congratulations note"],
        "severity_rank": 15,
        "days_active": 7
    },
    {
        "report_type": "bathroom",
        "priority": PRIORITY_INFO,
        "sentiment": SENTIMENT_RESOLUTION,
        "summary": "Bathroom pattern normalized after hydration protocol",
        "short_description": "Bathroom activity returned to baseline",
        "long_description": "Following staff intervention and hydration protocol, bathroom visits have returned to normal baseline (6 visits/day). Resident reports feeling better.",
        "concerns": [],
        "context": "Issue resolved through proactive intervention",
        "recommended_actions": ["Continue monitoring", "Document success in care plan"],
        "severity_rank": 20,
        "days_active": 5
    }
]

IT_SCENARIOS = [
    {
        "report_type": "device_offline",
        "priority": PRIORITY_CRITICAL,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "Gateway offline for 3 days - complete monitoring loss",
        "short_description": "Gateway communication failure",
        "long_description": "Primary gateway device has been offline for 72 hours, resulting in complete loss of monitoring for 12 connected sensors. Last communication: 2025-01-01 06:00:00.",
        "concerns": ["No monitoring data", "Safety risk", "Connectivity loss", "Hardware failure suspected"],
        "context": "Complete blind spot for this location - cannot detect emergencies",
        "recommended_actions": ["Dispatch technician immediately", "Check power and network", "Test gateway replacement", "Verify ISP service"],
        "severity_rank": 95,
        "days_active": 3
    },
    {
        "report_type": "battery_low",
        "priority": PRIORITY_WARNING,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "Motion sensor battery at 8% - replacement needed",
        "short_description": "Critical battery level detected",
        "long_description": "Bedroom motion sensor battery has dropped to 8% and will likely fail within 48-72 hours. Sensor provides critical fall detection coverage.",
        "concerns": ["Imminent sensor failure", "Coverage gap risk", "Replacement logistics"],
        "context": "This sensor monitors primary living space - critical for safety",
        "recommended_actions": ["Schedule battery replacement visit", "Notify maintenance team", "Order replacement batteries", "Plan backup coverage"],
        "severity_rank": 72,
        "days_active": 2
    },
    {
        "report_type": "connectivity",
        "priority": PRIORITY_WARNING,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "WiFi connectivity intermittent - 15 disconnects in 24h",
        "short_description": "Network stability issues",
        "long_description": "Gateway experiencing frequent WiFi disconnections (15 events in past 24 hours). Average downtime per disconnect: 5-8 minutes. May indicate ISP or router issues.",
        "concerns": ["Data gaps", "Delayed alerts", "Network instability", "Possible ISP problem"],
        "context": "Intermittent connectivity affects alert timeliness",
        "recommended_actions": ["Contact ISP to check line quality", "Test router replacement", "Check for interference", "Consider cellular backup"],
        "severity_rank": 65,
        "days_active": 1
    },
    {
        "report_type": "infrastructure",
        "priority": PRIORITY_INFO,
        "sentiment": SENTIMENT_CELEBRATION,
        "summary": "Gateway back online after firmware update",
        "short_description": "Connectivity restored successfully",
        "long_description": "Gateway that was offline for 48 hours is now back online and functioning normally. Remote firmware update resolved the issue. All sensors reconnected successfully.",
        "concerns": [],
        "context": "Remote troubleshooting successful - no site visit needed",
        "recommended_actions": ["Monitor for 48 hours to ensure stability", "Document fix in maintenance log"],
        "severity_rank": 25,
        "days_active": 2
    },
    {
        "report_type": "device_offline",
        "priority": PRIORITY_INFO,
        "sentiment": SENTIMENT_RESOLUTION,
        "summary": "Door sensor reconnected after battery replacement",
        "short_description": "Sensor back online and communicating",
        "long_description": "Front door sensor that was offline for 5 days is now operational after maintenance visit and battery replacement. Testing confirms proper operation.",
        "concerns": [],
        "context": "Scheduled maintenance completed successfully",
        "recommended_actions": ["Update battery replacement schedule", "Note for annual review"],
        "severity_rank": 18,
        "days_active": 5
    }
]

SAFETY_SCENARIOS = [
    {
        "report_type": "water_leak",
        "priority": PRIORITY_CRITICAL,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "Water leak detected in bathroom - immediate action required",
        "short_description": "Active water leak in progress",
        "long_description": "Bathroom water sensor has detected continuous moisture for 45 minutes. Likely leak from toilet, sink, or pipes. Risk of water damage and mold.",
        "concerns": ["Property damage", "Mold risk", "Slip hazard", "Structural damage"],
        "context": "Active emergency requiring immediate response",
        "recommended_actions": ["Emergency maintenance dispatch", "Contact resident", "Shut off water if needed", "Document for insurance"],
        "severity_rank": 98,
        "days_active": 0
    },
    {
        "report_type": "temperature_alert",
        "priority": PRIORITY_CRITICAL,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "Temperature dropped to 55F - heating system failure",
        "short_description": "Dangerously cold indoor temperature",
        "long_description": "Indoor temperature has dropped from 72F to 55F over 12 hours. Outside temperature is 28F. Heating system appears to have failed. Risk of hypothermia for elderly resident.",
        "concerns": ["Hypothermia risk", "Heating system failure", "Health emergency", "Pipe freeze risk"],
        "context": "Critical safety issue in winter conditions",
        "recommended_actions": ["Emergency HVAC service", "Check on resident immediately", "Provide space heater if needed", "Consider temporary relocation"],
        "severity_rank": 96,
        "days_active": 0
    },
    {
        "report_type": "temperature_alert",
        "priority": PRIORITY_WARNING,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "High temperature detected - 88F for 6 hours",
        "short_description": "Excessive indoor heat",
        "long_description": "Indoor temperature has been above 85F for past 6 hours, reaching 88F. AC appears to be malfunctioning. Risk of heat-related illness for elderly resident.",
        "concerns": ["Heat stress risk", "AC malfunction", "Dehydration risk", "Cognitive impairment risk"],
        "context": "Elderly residents vulnerable to heat-related illness",
        "recommended_actions": ["HVAC service call", "Wellness check", "Ensure hydration", "Provide fans if available"],
        "severity_rank": 78,
        "days_active": 0
    },
    {
        "report_type": "water_leak",
        "priority": PRIORITY_INFO,
        "sentiment": SENTIMENT_RESOLUTION,
        "summary": "Water leak resolved - plumbing repair completed",
        "short_description": "Leak fixed, no further moisture detected",
        "long_description": "Bathroom leak has been repaired by maintenance team. Water sensor shows no moisture for past 48 hours. Area cleaned and dried. No mold detected.",
        "concerns": [],
        "context": "Emergency response successful - no lasting damage",
        "recommended_actions": ["Continue monitoring for 1 week", "Schedule follow-up inspection"],
        "severity_rank": 22,
        "days_active": 3
    }
]

ENERGY_SCENARIOS = [
    {
        "report_type": "hvac",
        "priority": PRIORITY_WARNING,
        "sentiment": SENTIMENT_CONCERN,
        "summary": "HVAC runtime increased 45% - possible inefficiency",
        "short_description": "Abnormal HVAC energy usage",
        "long_description": "HVAC system has been running 45% more than baseline for past week. Energy consumption up 32%. Possible causes: filter clog, refrigerant leak, aging compressor.",
        "concerns": ["Energy waste", "System wear", "Filter maintenance overdue", "Possible equipment failure"],
        "context": "Inefficient operation increases costs and failure risk",
        "recommended_actions": ["Schedule HVAC inspection", "Replace air filter", "Check for leaks", "Consider efficiency upgrade"],
        "severity_rank": 58,
        "days_active": 7
    },
    {
        "report_type": "energy",
        "priority": PRIORITY_INFO,
        "sentiment": SENTIMENT_CELEBRATION,
        "summary": "Energy consumption down 18% after thermostat optimization",
        "short_description": "Significant energy savings achieved",
        "long_description": "Following smart thermostat installation and schedule optimization, energy consumption has decreased 18% while maintaining comfort. Projected annual savings: $240.",
        "concerns": [],
        "context": "Successful efficiency upgrade - positive ROI",
        "recommended_actions": ["Document savings", "Consider replicating at other locations", "Share success story"],
        "severity_rank": 12,
        "days_active": 14
    }
]

ALL_SCENARIOS = {
    CATEGORY_WELLNESS: WELLNESS_SCENARIOS,
    CATEGORY_IT: IT_SCENARIOS,
    CATEGORY_SAFETY: SAFETY_SCENARIOS,
    CATEGORY_ENERGY: ENERGY_SCENARIOS
}


def generate_virtual_locations(count=25):
    """Generate virtual locations with diverse names."""
    first_names = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry",
                   "Iris", "Jack", "Karen", "Leo", "Mary", "Nathan", "Olivia", "Paul",
                   "Quinn", "Rachel", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xavier", "Yolanda"]
    last_names = ["Anderson", "Brown", "Chen", "Davis", "Evans", "Foster", "Garcia", "Hill",
                  "Ivanov", "Jones", "Kim", "Lee", "Miller", "Nguyen", "O'Brien", "Patel",
                  "Quinn", "Rodriguez", "Smith", "Taylor", "Upton", "Vargas", "Williams", "Xavier", "Young"]

    locations = []
    for i in range(count):
        location_id = 1000000 + i + 1
        first = first_names[i % len(first_names)]
        last = last_names[i % len(last_names)]
        locations.append({
            "location_id": location_id,
            "location_name": f"{first} {last}",
            "apartment": f"Apt {100 + i}"
        })

    return locations


def generate_report_from_scenario(scenario, location, timestamp_ms, report_id):
    """Convert scenario template to full report."""
    report = {
        "location_id": location["location_id"],
        "location_name": location["location_name"],
        "timestamp_ms": timestamp_ms,
        "report_id": report_id,
        "resident_name": location["location_name"],
        **scenario
    }
    return report


def generate_test_reports(server, app_key, organization_id, location_count=25):
    """
    Generate comprehensive test reports for an organization and send them
    via datastream messages.

    :param server: Server URL
    :param app_key: API key
    :param organization_id: Organization ID
    :param location_count: Number of virtual locations to create
    """
    print("\n" + "=" * 70)
    print("ORGANIZATION REPORT DATA GENERATOR")
    print("=" * 70)
    print(f"Organization ID: {organization_id}")
    print(f"Virtual Locations: {location_count}")
    print("=" * 70 + "\n")

    # Generate virtual locations
    locations = generate_virtual_locations(location_count)
    print(f"Generated {len(locations)} virtual locations")

    # Generate reports
    reports = []
    current_time = int(datetime.now().timestamp() * 1000)
    report_counter = 0

    for i, location in enumerate(locations):
        num_reports = random.randint(1, 3)

        for _ in range(num_reports):
            category = random.choice(list(ALL_SCENARIOS.keys()))
            scenarios = ALL_SCENARIOS[category]
            scenario = random.choice(scenarios)

            hours_ago = random.randint(1, 48)
            timestamp_ms = current_time - (hours_ago * 60 * 60 * 1000)

            report_id = f"test_report_{organization_id}_{report_counter:04d}"
            report_counter += 1

            report = generate_report_from_scenario(scenario, location, timestamp_ms, report_id)

            report["days_active"] = max(0, scenario["days_active"] + random.randint(-1, 2))
            report["severity_rank"] = max(0, min(100, scenario["severity_rank"] + random.randint(-5, 5)))

            reports.append(report)

    print(f"Generated {len(reports)} reports across all categories")

    # Show category breakdown
    category_counts = {}
    priority_counts = {}
    sentiment_counts = {}

    for report in reports:
        cat = None
        for category, scenarios in ALL_SCENARIOS.items():
            if any(s["report_type"] == report["report_type"] for s in scenarios):
                cat = category
                break
        if cat:
            category_counts[cat] = category_counts.get(cat, 0) + 1

        priority_counts[report["priority"]] = priority_counts.get(report["priority"], 0) + 1
        sentiment_counts[report["sentiment"]] = sentiment_counts.get(report["sentiment"], 0) + 1

    print("\nReport Breakdown:")
    print("  Categories:")
    for cat, count in sorted(category_counts.items()):
        print(f"    - {cat}: {count}")
    print("  Priorities:")
    for pri, count in sorted(priority_counts.items()):
        print(f"    - {pri}: {count}")
    print("  Sentiments:")
    for sent, count in sorted(sentiment_counts.items()):
        print(f"    - {sent}: {count}")

    # Send reports via datastream
    print("\n" + "=" * 70)
    print("SENDING DATASTREAM MESSAGES")
    print("=" * 70 + "\n")

    success_count = 0
    error_count = 0

    for i, report in enumerate(reports, 1):
        if i <= 3 or i == len(reports):
            print(f"[{i}/{len(reports)}] Sending report from {report['location_name']}:")
            print(f"  Type: {report['report_type']}")
            print(f"  Priority: {report['priority']}")
            print(f"  Sentiment: {report['sentiment']}")
            print(f"  Summary: {report['summary'][:60]}...")
        elif i == 4:
            print(f"[...sending {len(reports) - 4} more reports...]")

        try:
            send_datastream_message(server, app_key, organization_id, DATASTREAM_ADDRESS, report)
            success_count += 1
        except Exception as e:
            error_count += 1
            if i <= 3 or i == len(reports):
                print(f"  {Color.RED}Error: {e}{Color.END}")

    print()
    print("=" * 70)
    print(f"{Color.GREEN}Sent {success_count}/{len(reports)} reports to org {organization_id}{Color.END}")
    if error_count > 0:
        print(f"{Color.RED}Failed: {error_count} reports{Color.END}")
    print("Organization cache should now contain diverse test data")
    print("Ready to generate master report")
    print("=" * 70 + "\n")

    # Save reports to JSON file for reference
    output_file = f"test_reports_org_{organization_id}.json"
    with open(output_file, 'w') as f:
        json.dump({
            "organization_id": organization_id,
            "generated_at": datetime.now().isoformat(),
            "location_count": len(locations),
            "report_count": len(reports),
            "sent_count": success_count,
            "error_count": error_count,
            "locations": locations,
            "reports": reports,
            "stats": {
                "by_category": category_counts,
                "by_priority": priority_counts,
                "by_sentiment": sentiment_counts
            }
        }, f, indent=2)

    print(f"Test data saved to: {output_file}")
    print()

    return success_count, error_count


def main(argv=None):
    if argv is None:
        argv = sys.argv
    else:
        sys.argv.extend(argv)

    parser = ArgumentParser(
        description='Generate synthetic test reports for an organization',
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

    generate_test_reports(server, app_key, organization_id, args.count)


if __name__ == "__main__":
    sys.exit(main())
