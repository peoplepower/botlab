"""
Created on February 8, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: AI Chief of Staff Implementation

Location Device Health Microservice
===================================

WHY:
Provide proactive infrastructure monitoring by detecting device offline/online
transitions and reporting concerns to organization administrators. Enables
rapid response to connectivity issues before they impact care delivery.

WHAT:
This microservice monitors device health by tracking online/offline status.
When devices go offline for more than 1 hour, it sends CONCERN reports.
When devices come back online, it sends RESOLUTION reports with lifecycle
tracking (previous_report_id).

Key Features:
- Hourly polling to detect offline devices
- Immediate detection of devices coming back online
- Lifecycle tracking: CONCERN → RESOLUTION with report_id linking
- Context includes offline duration, device type, last measurement
- Prevents duplicate concerns for same device

HOW:
- Set hourly timer to check device status
- Track offline_concerns{device_id: {report_id, offline_since_ms}}
- When device offline > 1 hour: Send CONCERN with new report_id
- When device back online: Send RESOLUTION with previous_report_id
- Clear concern from tracking after resolution sent

Architecture Notes:
- Location-level microservice (monitors all devices at location)
- Uses class variables for offline_concerns tracking
- Integrates with signals.report for org reporting
- Handles device_deleted and new_version for cleanup
"""

import utilities.utilities as utilities  # type: ignore

from intelligence.intelligence import Intelligence  # type: ignore

import signals.report as report  # type: ignore

# Timer reference
TIMER_REFERENCE_CHECK_DEVICES = "CHECK_DEVICE_HEALTH"

# Check interval (1 hour)
CHECK_INTERVAL_MS = utilities.ONE_HOUR_MS

# Offline threshold (1 hour)
OFFLINE_THRESHOLD_MS = utilities.ONE_HOUR_MS


class LocationDeviceHealthMicroservice(Intelligence):
    """
    Device Health Microservice

    Monitors device online/offline transitions and sends concern/resolution
    reports to organization.
    """

    def __init__(self, botengine, parent):
        """
        Initialize the microservice

        :param botengine: BotEngine environment
        :param parent: Parent location object
        """
        Intelligence.__init__(self, botengine, parent)

        # Track offline concerns: {device_id: {report_id, offline_since_ms}}
        self.offline_concerns = {}

        # Start hourly check timer
        self.start_timer_ms(
            botengine, CHECK_INTERVAL_MS, reference=TIMER_REFERENCE_CHECK_DEVICES
        )

    def initialize(self, botengine):
        """
        Initialize the microservice

        :param botengine: BotEngine environment
        """
        return

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
        logger.info(">new_version() Device Health Microservice")

        # Initialize offline_concerns if not exists
        if not hasattr(self, "offline_concerns"):
            self.offline_concerns = {}

        logger.info("<new_version()")

    # ===========================================================================
    # Event Handlers
    # ===========================================================================

    def device_measurements_updated(self, botengine, device_object):
        """
        Device measurements updated - check if device came back online

        :param botengine: BotEngine environment
        :param device_object: Device that was updated
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        device_id = device_object.device_id

        # Check if this device had an offline concern
        if device_id in self.offline_concerns:
            logger.info(
                f"|device_measurements_updated() Device {device_id} back online - sending resolution"
            )
            self._send_device_resolution(botengine, device_object)

    def device_deleted(self, botengine, device_object):
        """
        Device deleted - clean up offline concerns

        :param botengine: BotEngine environment
        :param device_object: Device that was deleted
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        device_id = device_object.device_id

        if device_id in self.offline_concerns:
            logger.info(
                f"|device_deleted() Removing offline concern for deleted device {device_id}"
            )
            del self.offline_concerns[device_id]

    def timer_fired(self, botengine, argument):
        """
        Timer fired - check for offline devices

        :param botengine: BotEngine environment
        :param argument: Timer argument
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        if argument == TIMER_REFERENCE_CHECK_DEVICES:
            logger.info(">timer_fired() Checking device health")

            # Check all devices for offline status
            self._check_offline_devices(botengine)

            # Restart timer
            self.start_timer_ms(
                botengine, CHECK_INTERVAL_MS, reference=TIMER_REFERENCE_CHECK_DEVICES
            )

            logger.info("<timer_fired()")

    # ===========================================================================
    # Core Logic
    # ===========================================================================

    def _check_offline_devices(self, botengine):
        """
        Check all devices for offline status and send concerns

        :param botengine: BotEngine environment
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        if not self.parent.devices:
            return

        now_ms = botengine.get_timestamp()

        for device_id, device_object in self.parent.devices.items():
            # Check if device is offline
            if self._is_device_offline(botengine, device_object):
                # Check if we already have a concern for this device
                if device_id not in self.offline_concerns:
                    # Get offline duration
                    offline_since_ms = self._get_device_last_measurement_ms(
                        device_object
                    )
                    offline_duration_ms = (
                        now_ms - offline_since_ms if offline_since_ms else 0
                    )

                    # Only send concern if offline > threshold
                    if offline_duration_ms > OFFLINE_THRESHOLD_MS:
                        logger.info(
                            f"|_check_offline_devices() Device {device_id} offline for "
                            f"{offline_duration_ms / utilities.ONE_HOUR_MS:.1f} hours"
                        )
                        self._send_device_concern(
                            botengine, device_object, offline_since_ms
                        )

    def _is_device_offline(self, botengine, device_object):
        """
        Check if device is considered offline

        A device is offline if its last measurement is older than threshold.

        :param botengine: BotEngine environment
        :param device_object: Device to check
        :return: True if offline, False otherwise
        """
        now_ms = botengine.get_timestamp()
        last_measurement_ms = self._get_device_last_measurement_ms(device_object)

        if last_measurement_ms is None:
            return False

        age_ms = now_ms - last_measurement_ms
        return age_ms > OFFLINE_THRESHOLD_MS

    def _get_device_last_measurement_ms(self, device_object):
        """
        Get timestamp of device's last measurement

        :param device_object: Device object
        :return: Timestamp in milliseconds or None
        """
        if hasattr(device_object, "last_updated_ms") and device_object.last_updated_ms:
            return device_object.last_updated_ms
        elif (
            hasattr(device_object, "measurements_timestamp")
            and device_object.measurements_timestamp
        ):
            return device_object.measurements_timestamp

        return None

    def _send_device_concern(self, botengine, device_object, offline_since_ms):
        """
        Send device offline concern to organization

        :param botengine: BotEngine environment
        :param device_object: Device that is offline
        :param offline_since_ms: Timestamp when device went offline
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">_send_device_concern() device={device_object.device_id}")

        report_service = self.parent.intelligence_modules.get(
            "intelligence.reports.location_reports_microservice"
        )
        if report_service is None:
            logger.warning("|_send_device_concern() Report service not available")
            return

        try:
            device_id = device_object.device_id
            now_ms = botengine.get_timestamp()
            offline_duration_ms = now_ms - offline_since_ms if offline_since_ms else 0

            # Generate report_id for lifecycle tracking
            report_id = f"device_offline_{self.parent.location_id}_{utilities.good_enough_unique_id()}"

            # Build summary
            device_desc = (
                device_object.description
                if hasattr(device_object, "description")
                else device_id
            )
            device_type = (
                device_object.device_type
                if hasattr(device_object, "device_type")
                else "Unknown"
            )

            hours_offline = offline_duration_ms / utilities.ONE_HOUR_MS
            summary = f"Device offline: {device_desc} ({device_type}) - offline for {hours_offline:.1f} hours"

            # Build context
            context = {
                "device_id": device_id,
                "device_type": device_type,
                "device_description": device_desc,
                "offline_since_ms": offline_since_ms,
                "offline_duration_hours": round(hours_offline, 1),
                "last_measurement_ms": offline_since_ms,
            }

            # Determine severity
            if offline_duration_ms > (24 * utilities.ONE_HOUR_MS):
                priority = report.PRIORITY_CRITICAL
                severity_rank = 90
            elif offline_duration_ms > (12 * utilities.ONE_HOUR_MS):
                priority = report.PRIORITY_WARNING
                severity_rank = 70
            else:
                priority = report.PRIORITY_WARNING
                severity_rank = 50

            # Send concern to organization
            logger.info(f"|_send_device_concern() Sending concern: {summary}")

            report.send_org_report(
                botengine,
                self.parent,
                priority=priority,
                report_type="device_offline",
                sentiment=report.SENTIMENT_CONCERN,
                report_id=report_id,
                summary=summary,
                context=context,
                concerns=[f"Device offline for {hours_offline:.1f} hours"],
                recommended_action="Check device power and connectivity",
                severity_rank=severity_rank,
            )

            # Track concern
            self.offline_concerns[device_id] = {
                "report_id": report_id,
                "offline_since_ms": offline_since_ms,
            }

            logger.info(
                f"|_send_device_concern() Concern sent with report_id={report_id}"
            )

        except Exception as e:
            logger.error(f"|_send_device_concern() Error sending concern: {e}")
            import traceback

            logger.error(traceback.format_exc())

        logger.info("<_send_device_concern()")

    def _send_device_resolution(self, botengine, device_object):
        """
        Send device back online resolution to organization

        :param botengine: BotEngine environment
        :param device_object: Device that came back online
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">_send_device_resolution() device={device_object.device_id}")

        report_service = self.parent.intelligence_modules.get(
            "intelligence.reports.location_reports_microservice"
        )
        if report_service is None:
            logger.warning("|_send_device_resolution() Report service not available")
            return

        try:
            device_id = device_object.device_id

            if device_id not in self.offline_concerns:
                logger.debug(
                    f"|_send_device_resolution() No concern found for device {device_id}"
                )
                return

            concern_info = self.offline_concerns[device_id]
            previous_report_id = concern_info["report_id"]
            offline_since_ms = concern_info["offline_since_ms"]

            now_ms = botengine.get_timestamp()
            offline_duration_ms = now_ms - offline_since_ms if offline_since_ms else 0

            # Build summary
            device_desc = (
                device_object.description
                if hasattr(device_object, "description")
                else device_id
            )
            device_type = (
                device_object.device_type
                if hasattr(device_object, "device_type")
                else "Unknown"
            )

            hours_offline = offline_duration_ms / utilities.ONE_HOUR_MS
            summary = f"Device back online: {device_desc} ({device_type}) - was offline for {hours_offline:.1f} hours"

            # Build context
            context = {
                "device_id": device_id,
                "device_type": device_type,
                "device_description": device_desc,
                "offline_since_ms": offline_since_ms,
                "back_online_ms": now_ms,
                "total_offline_duration_hours": round(hours_offline, 1),
            }

            # Send resolution to organization
            logger.info(f"|_send_device_resolution() Sending resolution: {summary}")

            report.send_org_report(
                botengine,
                self.parent,
                priority=report.PRIORITY_INFO,
                report_type="device_online",
                sentiment=report.SENTIMENT_RESOLUTION,
                previous_report_id=previous_report_id,
                summary=summary,
                context=context,
            )

            # Remove concern from tracking
            del self.offline_concerns[device_id]

            logger.info(
                f"|_send_device_resolution() Resolution sent with previous_report_id={previous_report_id}"
            )

        except Exception as e:
            logger.error(f"|_send_device_resolution() Error sending resolution: {e}")
            import traceback

            logger.error(traceback.format_exc())

        logger.info("<_send_device_resolution()")
