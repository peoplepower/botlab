"""
Created on February 8, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: AI Chief of Staff Implementation

Location Daily Heartbeat Microservice
=====================================

WHY:
Provide proactive "all OK" reports to organization administrators, ensuring
visibility into locations that are operating normally. Prevents information
gaps where only problems are reported.

WHAT:
This microservice sends daily summary reports to the organization when NO
critical events or concerns have been reported today. It provides:
- Wellness score aggregate
- Stability score aggregate
- Device online count
- Last activity timestamp
- "All systems normal" confirmation

Ensures organizations know about silent locations (good news = no news).

HOW:
- Set daily timer at 6:00 AM (location timezone)
- When timer fires: Check if any critical org reports sent today
- If no critical reports: Send daily heartbeat with summary data
- Include wellness/stability scores, device counts, activity timestamp
- Use SENTIMENT_SUMMARY (neutral/informational) priority
- Reset daily tracking state

Architecture Notes:
- Location-level microservice (runs at each location)
- Integrates with signals.report for org reporting
- Checks state for report_sent_today flag
- Lightweight class variables (single boolean flag)
"""

import utilities.utilities as utilities  # type: ignore

from intelligence.intelligence import Intelligence  # type: ignore

import signals.report as report  # type: ignore
import properties  # type: ignore

# Timer reference
TIMER_REFERENCE_DAILY_HEARTBEAT = "DAILY_HEARTBEAT"

# Daily heartbeat target hour (6 AM local time)
DAILY_HEARTBEAT_HOUR = 6


class LocationDailyHeartbeatMicroservice(Intelligence):
    """
    Daily Heartbeat Microservice

    Sends daily "all OK" summary reports to organization when no critical
    events have been reported.
    """

    def __init__(self, botengine, parent):
        """
        Initialize the microservice

        :param botengine: BotEngine environment
        :param parent: Parent location object
        """
        Intelligence.__init__(self, botengine, parent)

        # Track if critical report sent today (prevents duplicate heartbeats)
        self.critical_report_sent_today = False

    def initialize(self, botengine):
        """
        Initialize the microservice

        :param botengine: BotEngine environment
        """
        if (
            self.parent.devices
            and not self.is_timer_running(
                botengine, reference=TIMER_REFERENCE_DAILY_HEARTBEAT
            )
            and botengine.TRIGGER_TIMER not in botengine.all_trigger_types
            and botengine.TRIGGER_DATA_STREAM not in botengine.all_trigger_types
        ):
            # Ensure daily timer is always running
            self._set_daily_timer(botengine)

    def destroy(self, botengine):
        """
        Destroy the microservice

        :param botengine: BotEngine environment
        """
        return

    def new_version(self, botengine):
        """
        New bot version detected - initialize new class variables if needed

        :param botengine: BotEngine environment
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">new_version() Daily Heartbeat Microservice")

        # Initialize critical_report_sent_today if not exists
        if not hasattr(self, "critical_report_sent_today"):
            self.critical_report_sent_today = False

        logger.info("<new_version()")

    # ===========================================================================
    # Event Handlers
    # ===========================================================================

    def timer_fired(self, botengine, argument):
        """
        Timer fired - check if heartbeat should be sent

        :param botengine: BotEngine environment
        :param argument: Timer argument
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        if argument == TIMER_REFERENCE_DAILY_HEARTBEAT:
            logger.info(">timer_fired() Daily heartbeat check")

            # Check if critical report was sent today
            if not self.critical_report_sent_today:
                logger.info(
                    "|timer_fired() No critical reports today - sending heartbeat"
                )
                self._send_daily_heartbeat(botengine)
            else:
                logger.info(
                    "|timer_fired() Critical report sent today - skipping heartbeat"
                )

            # Reset daily flag
            self.critical_report_sent_today = False

            # Set timer for tomorrow
            self._set_daily_timer(botengine)

            logger.info("<timer_fired()")

    def datastream_updated(self, botengine, address, content):
        """
        Datastream message received

        Listen for report_sent_to_org signal to track critical reports.

        :param botengine: BotEngine environment
        :param address: Data stream address
        :param content: Data stream content
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        if address == "report_sent_to_org":
            # Check if report was critical/warning priority
            priority = content.get("priority")
            if priority in [report.PRIORITY_CRITICAL, report.PRIORITY_WARNING]:
                logger.debug(
                    "|datastream_updated() Critical report sent, will skip heartbeat today"
                )
                self.critical_report_sent_today = True

    # ===========================================================================
    # Core Logic
    # ===========================================================================

    def _set_daily_timer(self, botengine):
        """
        Set daily timer for 6 AM local time

        :param botengine: BotEngine environment
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        # Calculate milliseconds until 6 AM local time today/tomorrow
        midnight_tonight_ms = self.parent.timezone_aware_datetime_to_unix_timestamp(
            botengine, self.parent.get_midnight_tonight(botengine)
        )
        next_run_ms = midnight_tonight_ms + (
            DAILY_HEARTBEAT_HOUR * utilities.ONE_HOUR_MS
        )

        delay_ms = next_run_ms - botengine.get_timestamp()

        logger.info(f"|_set_daily_timer() Setting timer for {delay_ms}ms from now")

        self.start_timer_ms(
            botengine,
            delay_ms,
            reference=TIMER_REFERENCE_DAILY_HEARTBEAT,
            argument=TIMER_REFERENCE_DAILY_HEARTBEAT,
        )

    def _send_daily_heartbeat(self, botengine):
        """
        Send daily "all OK" heartbeat report to organization

        :param botengine: BotEngine environment
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_send_daily_heartbeat()")
        report_service = self.parent.intelligence_modules.get(
            "intelligence.reports.location_reports_microservice"
        )
        if report_service is None:
            logger.warning("|_send_daily_heartbeat() Report service not available")
            return

        try:
            # Gather summary data
            wellness_score = self._get_wellness_score(botengine)
            stability_score = self._get_stability_score(botengine)
            devices_online = self._count_devices_online(botengine)
            last_activity_ms = self._get_last_activity_timestamp(botengine)

            # Build context
            context = {
                "wellness_score": wellness_score,
                "stability_score": stability_score,
                "devices_online": devices_online,
                "total_devices": len(self.parent.devices),
                "last_activity_ms": last_activity_ms,
            }

            # Build summary message
            summary_parts = []
            summary_parts.append(
                f"Daily operational summary for {self.parent.get_location_name(botengine)}"
            )

            if wellness_score is not None:
                summary_parts.append(f"Wellness: {wellness_score}%")

            if stability_score is not None:
                summary_parts.append(f"Stability: {stability_score}%")

            if devices_online is not None:
                summary_parts.append(
                    f"Devices: {devices_online}/{len(self.parent.devices)} online"
                )

            summary = " | ".join(summary_parts)

            # Build scores from available data
            org_scores = {k: v for k, v in {
                "wellness_score": wellness_score,
                "stability_score": stability_score,
            }.items() if v is not None}

            # Send report to organization
            logger.info(f"|_send_daily_heartbeat() Sending heartbeat: {summary}")

            report.send_org_report(
                botengine,
                self.parent,
                priority=report.PRIORITY_INFO,
                report_type="daily_summary",
                sentiment=report.SENTIMENT_SUMMARY,
                summary=summary,
                short_description=summary,
                context=context,
                recommended_action="No action required. All systems operating normally.",
                scores=org_scores if org_scores else None,
            )

            logger.info("|_send_daily_heartbeat() Heartbeat sent successfully")

        except Exception as e:
            logger.error(f"|_send_daily_heartbeat() Error sending heartbeat: {e}")
            import traceback

            logger.error(traceback.format_exc())

        logger.info("<_send_daily_heartbeat()")

    def _get_wellness_score(self, botengine):
        """
        Get aggregated wellness score from location

        :param botengine: BotEngine environment
        :return: Wellness score (0-100) or None
        """
        # Check if location has wellness_score attribute or state
        if hasattr(self.parent, "wellness_score"):
            return self.parent.wellness_score

        # Try to get from state variable
        wellness_score = self.parent.get_location_property(botengine, "wellness_score")

        return wellness_score

    def _get_stability_score(self, botengine):
        """
        Get aggregated stability score from location

        :param botengine: BotEngine environment
        :return: Stability score (0-100) or None
        """
        # Check if location has stability_score attribute or state
        if hasattr(self.parent, "stability_score"):
            return self.parent.stability_score

        # Try to get from state variable
        stability_score = self.parent.get_location_property(
            botengine, "stability_score"
        )

        return stability_score

    def _count_devices_online(self, botengine):
        """
        Count number of devices currently online

        A device is considered online if it has recent measurements
        (within last 24 hours).

        :param botengine: BotEngine environment
        :return: Number of online devices
        """
        if not self.parent.devices:
            return 0

        online_count = 0
        now_ms = botengine.get_timestamp()
        offline_threshold_ms = 24 * utilities.ONE_HOUR_MS

        for device_id, device in self.parent.devices.items():
            # Check if device has recent measurement
            if hasattr(device, "last_updated_ms"):
                if (
                    device.last_updated_ms
                    and (now_ms - device.last_updated_ms) < offline_threshold_ms
                ):
                    online_count += 1
            elif hasattr(device, "measurements_timestamp"):
                if (
                    device.measurements_timestamp
                    and (now_ms - device.measurements_timestamp) < offline_threshold_ms
                ):
                    online_count += 1

        return online_count

    def _get_last_activity_timestamp(self, botengine):
        """
        Get timestamp of most recent device activity

        :param botengine: BotEngine environment
        :return: Timestamp in milliseconds or None
        """
        if not self.parent.devices:
            return None

        latest_timestamp = 0

        for device_id, device in self.parent.devices.items():
            device_timestamp = 0

            if hasattr(device, "last_updated_ms") and device.last_updated_ms:
                device_timestamp = device.last_updated_ms
            elif (
                hasattr(device, "measurements_timestamp")
                and device.measurements_timestamp
            ):
                device_timestamp = device.measurements_timestamp

            if device_timestamp > latest_timestamp:
                latest_timestamp = device_timestamp

        return latest_timestamp if latest_timestamp > 0 else None
