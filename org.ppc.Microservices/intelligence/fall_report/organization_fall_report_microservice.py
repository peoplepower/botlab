"""
Created on April 27, 2026

Organization-level Fall Report Microservice.

Queries the 'falls' time-series state from all child locations for a given date range,
builds a CSV report with one row per fall event, and emails it to organization admins.

Triggered by the 'generate_fall_report' datastream message with content:
{
    "start_date_ms": int,      # Required: start of reporting period
    "end_date_ms": int,        # Optional: end of reporting period (defaults to now)
}

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Claude
"""

import intelligence.fall_report.report_builder as report_builder  # type: ignore
import intelligence.fall_report.services as services  # type: ignore
import utilities.utilities as utilities  # type: ignore
from intelligence.intelligence import Intelligence  # type: ignore


class OrganizationFallReportMicroservice(Intelligence):
    """
    Organization-level microservice that generates Fall Reports by querying
    the 'falls' time-series state across all child locations.
    """

    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, either a location or a device object.
        """
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        return

    def destroy(self, botengine):
        """
        This device or object is getting permanently deleted
        :param botengine: BotEngine environment
        """
        return

    def new_version(self, botengine):
        """
        Upgraded to a new bot version
        :param botengine: BotEngine environment
        """
        return

    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Message Received
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Content of the message
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">datastream_updated() address={address}")

        if address == "generate_fall_report":
            self._handle_generate_fall_report(botengine, content)

        logger.info("<datastream_updated()")

    # ===========================================================================
    # Timer Handler
    # ===========================================================================
    def timer_fired(self, botengine, argument):
        """
        Timer fired - bridge async data request back to synchronous processing.
        :param botengine: BotEngine environment
        :param argument: Argument applied when setting the timer
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        if not isinstance(argument, dict):
            return

        timer_type = argument.get("type")

        if timer_type == "data_request_timeout":
            retry_count = argument.get("retry_count", 0)

            stored_data = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)

            if stored_data is not None:
                logger.info(
                    "|timer_fired() Fall report data ready, processing"
                )
                botengine.delete_variable(services.STATE_VAR_REPORT_IN_PROGRESS)

                fall_records = stored_data.get("fall_records", [])
                start_date_ms = stored_data.get("start_date_ms")
                end_date_ms = stored_data.get("end_date_ms")

                self._build_and_send_report(
                    botengine, fall_records, start_date_ms, end_date_ms
                )
            else:
                if retry_count >= services.MAX_DATA_REQUEST_RETRIES:
                    logger.warning(
                        "|timer_fired() Max retries ({}) exceeded waiting for fall data. Giving up.".format(
                            services.MAX_DATA_REQUEST_RETRIES
                        )
                    )
                    return

                logger.warning(
                    "|timer_fired() Data request timeout, retry {}/{}".format(
                        retry_count + 1, services.MAX_DATA_REQUEST_RETRIES
                    )
                )
                self.start_timer_s(
                    botengine,
                    services.DATA_REQUEST_TIMEOUT_S,
                    argument={
                        "type": "data_request_timeout",
                        "retry_count": retry_count + 1,
                    },
                    reference="fall_report_data_timeout",
                )

    # ===========================================================================
    # Async Data Request Handler
    # ===========================================================================
    def async_data_request_ready(self, botengine, reference, content):
        """
        Data request ready.

        IMPORTANT: Executes in async environment - cannot set timers or manage class state.

        :param botengine: BotEngine environment
        :param reference: Data request reference
        :param content: Data request content - {location_id: {"falls": {timestamp: fall_dict}}}
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        if reference != services.DATA_REQUEST_REFERENCE_FALLS:
            return

        logger.info(">async_data_request_ready() reference={}".format(reference))

        # Flatten all fall records from all locations
        fall_records = []
        for location_id in content:
            location_falls = content[location_id].get(services.FALLS_STATE_NAME, {})
            for timestamp_str, fall_dict in location_falls.items():
                record = dict(fall_dict)
                record["location_id"] = location_id
                record["start_time_ms"] = int(timestamp_str)
                fall_records.append(record)

        if not fall_records:
            logger.warning(
                "|async_data_request_ready() No fall records found across locations."
            )

        logger.info(
            "|async_data_request_ready() Collected {} fall records from {} locations".format(
                len(fall_records), len(content)
            )
        )

        # Load the stored request parameters
        existing = botengine.load_variable(services.STATE_VAR_REPORT_IN_PROGRESS)
        start_date_ms = existing.get("start_date_ms") if existing else None
        end_date_ms = existing.get("end_date_ms") if existing else None

        # Store for synchronous processing via timer_fired()
        botengine.save_variable(
            services.STATE_VAR_REPORT_IN_PROGRESS,
            {
                "fall_records": fall_records,
                "start_date_ms": start_date_ms,
                "end_date_ms": end_date_ms,
            },
            overwrite=True,
        )

        logger.info("<async_data_request_ready()")

    # ===========================================================================
    # Report Generation
    # ===========================================================================
    def _handle_generate_fall_report(self, botengine, content):
        """
        Handle the generate_fall_report datastream message.
        Initiates the async data request to pull falls from all locations.

        :param botengine: BotEngine environment
        :param content: Content with start_date_ms and optional end_date_ms
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_handle_generate_fall_report()")

        if content is None or "start_date_ms" not in content:
            logger.warning(
                "<_handle_generate_fall_report() Missing 'start_date_ms' in content"
            )
            return

        start_date_ms = content["start_date_ms"]
        end_date_ms = content.get("end_date_ms", botengine.get_timestamp())

        logger.info(
            "|_handle_generate_fall_report() Requesting falls data from {} to {}".format(
                start_date_ms, end_date_ms
            )
        )

        # Store request parameters for use in async callback
        botengine.save_variable(
            services.STATE_VAR_REPORT_IN_PROGRESS,
            {
                "start_date_ms": start_date_ms,
                "end_date_ms": end_date_ms,
            },
            overwrite=True,
        )

        # Request falls time-series state from all child locations
        botengine.request_data(
            type=botengine.DATA_REQUEST_TYPE_LOCATION_TIME_STATES,
            reference=services.DATA_REQUEST_REFERENCE_FALLS,
            oldest_timestamp_ms=start_date_ms,
            newest_timestamp_ms=end_date_ms,
            names=[services.FALLS_STATE_NAME],
        )

        # Set timeout timer for async bridge
        self.start_timer_s(
            botengine,
            services.DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": "data_request_timeout",
                "retry_count": 0,
            },
            reference="fall_report_data_timeout",
        )

        logger.info("<_handle_generate_fall_report()")

    def _build_and_send_report(self, botengine, fall_records, start_date_ms, end_date_ms):
        """
        Build the fall report and email it to organization admins.

        :param botengine: BotEngine environment
        :param fall_records: List of fall record dicts enriched with location_id
        :param start_date_ms: Report start date in milliseconds
        :param end_date_ms: Report end date in milliseconds
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_build_and_send_report() records={}".format(len(fall_records)))

        if not fall_records:
            logger.info("|_build_and_send_report() No fall records to report.")
            # Still send the report to confirm no falls occurred
            pass

        # Resolve location names
        location_names = {}
        try:
            locations = botengine.get_organization_locations(
                botengine.get_organization_id()
            )
            if locations:
                for loc in locations:
                    loc_id = loc.get("id")
                    loc_name = loc.get("name", "Location {}".format(loc_id))
                    if loc_id is not None:
                        location_names[int(loc_id)] = loc_name
        except Exception as e:
            logger.warning(
                "|_build_and_send_report() Could not resolve location names: {}".format(e)
            )

        # Build the report
        csv_content, summary = report_builder.build_fall_report(
            fall_records, start_date_ms, end_date_ms, location_names
        )

        # Build HTML email summary
        html_content = report_builder.build_email_html(
            summary, start_date_ms, end_date_ms
        )

        # Format dates for email subject
        start_str = utilities.strftime(
            utilities.timestamp_ms_to_datetime(botengine, start_date_ms),
            "%Y-%m-%d",
        )
        end_str = utilities.strftime(
            utilities.timestamp_ms_to_datetime(botengine, end_date_ms),
            "%Y-%m-%d",
        )

        # Build email with CSV attachment
        import base64

        csv_bytes = csv_content.encode("utf-8")
        csv_b64 = base64.b64encode(csv_bytes).decode("utf-8")

        botengine.email_admins(
            email_subject="Fall Report - {} to {}".format(start_str, end_str),
            email_content=html_content,
            email_html=True,
            email_attachments=[
                {
                    "name": "fall_report_{}_{}.csv".format(start_str, end_str),
                    "contentType": "text/csv",
                    "content": csv_b64,
                }
            ],
            categories=[1, 2],
        )

        logger.info(
            "<_build_and_send_report() Report sent with {} fall records".format(
                len(fall_records)
            )
        )
