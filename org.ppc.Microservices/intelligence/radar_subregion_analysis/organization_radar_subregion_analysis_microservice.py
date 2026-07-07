"""
Created on May 4, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter

Organization Radar Subregion Analysis Microservice
==================================================

Walks every location in an organization, finds radar devices
(Vayyar / Pontosense / Assure) via a DEVICES data request, then reads each
location's `radar_room`, `radar_subregions`, and `radar_subregion_behaviors`
location states via synchronous `botengine.get_state(name, location_id=...)`
calls. Emails back a single PDF with a 2D top-down floorplan and a
descriptive table per device.

Pipeline:

1. `radar_subregion_analysis_run` datastream -->
   `request_data(DEVICES, device_types=RADAR_DEVICE_TYPES)`.
2. `async_data_request_ready(DEVICES)` collects the device listing,
   sets `ready_for_processing=True`.
3. Timer fires --> sync `_build_and_email_report()` iterates each
   location returned in step 2, pulls the three location states with
   `botengine.get_state()`, composes the per-device payload, generates
   the PDF, and emails it.

Org bots cannot call `get_device_property` (access denied) and the
radar configuration is point-in-time, not time-series, so we read it via
`get_state` rather than a `LOCATION_TIME_STATES` data request.
"""

import base64

import properties  # type: ignore
from intelligence.intelligence import Intelligence  # type: ignore

from . import report_builder, services


class OrganizationRadarSubregionAnalysisMicroservice(Intelligence):
    """
    Organization-level microservice that compiles a PDF showing every radar
    room and its subregion configuration across all child locations.

    Trigger: Manual only via `radar_subregion_analysis_run` datastream message.
    """

    def __init__(self, botengine, parent):
        Intelligence.__init__(self, botengine, parent)

    def initialize(self, botengine):
        pass

    def destroy(self, botengine):
        pass

    def new_version(self, botengine):
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(">new_version()")

    # ======================================================================
    # Datastream
    # ======================================================================
    def datastream_updated(self, botengine, address, content):
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    def radar_subregion_analysis_run(self, botengine, content):
        """
        Trigger a new radar subregion analysis.

        Expected content:
        {
            "email_addresses": ["admin@example.com"],
            "analysis_name": "Radar Subregion Analysis"   # optional
        }
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">radar_subregion_analysis_run()")

        email_addresses = (
            content.get("email_addresses") if isinstance(content, dict) else None
        )
        if not email_addresses:
            logger.warning(
                "|radar_subregion_analysis_run() Missing required field: email_addresses"
            )
            return

        # Guard against concurrent runs.
        existing = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        if existing is not None:
            logger.warning(
                "|radar_subregion_analysis_run() Analysis already in progress, skipping"
            )
            return

        analysis_name = content.get("analysis_name", "Radar Subregion Analysis")

        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS,
            {
                "config": {
                    "email_addresses": email_addresses,
                    "analysis_name": analysis_name,
                },
                "phase": services.PHASE_DEVICES,
                "start_time": botengine.get_timestamp(),
                "devices_data": None,
                "ready_for_processing": False,
            },
            overwrite=True,
        )

        botengine.request_data(
            type=botengine.DATA_REQUEST_TYPE_DEVICES,
            reference=services.DATA_REQUEST_REFERENCE_DEVICES,
            device_types=services.RADAR_DEVICE_TYPES,
        )

        self._start_timeout_timer(botengine, services.PHASE_DEVICES, 0)

        logger.info("<radar_subregion_analysis_run()")

    # ======================================================================
    # Timer (sync bridge from async DEVICES response to report build)
    # ======================================================================
    def timer_fired(self, botengine, argument):
        if not isinstance(argument, dict):
            return
        if argument.get("type") != services.TIMER_TYPE_DATA_REQUEST_TIMEOUT:
            return

        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        retry_count = argument.get("retry_count", 0)
        phase = argument.get("phase", "")

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        if state is None:
            logger.warning("|timer_fired() No analysis in progress")
            return

        if state.get("ready_for_processing") and phase == services.PHASE_DEVICES:
            state["ready_for_processing"] = False
            botengine.save_variable(
                services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
            )
            self._build_and_email_report(botengine, state)
            return

        if retry_count >= services.MAX_DATA_REQUEST_RETRIES:
            logger.warning(
                f"|timer_fired() Max retries exceeded for phase={phase}. Cleaning up."
            )
            self._cleanup(botengine)
            return

        logger.info(
            f"|timer_fired() Retry {retry_count + 1}/{services.MAX_DATA_REQUEST_RETRIES} "
            f"for phase={phase}"
        )
        self._start_timeout_timer(botengine, phase, retry_count + 1)

    def _start_timeout_timer(self, botengine, phase, retry_count):
        self.start_timer_s(
            botengine,
            services.DATA_REQUEST_TIMEOUT_S,
            argument={
                "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                "phase": phase,
                "retry_count": retry_count,
            },
            reference=f"radar_subregion_data_request_timeout_{phase}",
        )

    # ======================================================================
    # Data Request (async)
    # ======================================================================
    def async_data_request_ready(self, botengine, reference, content):
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(f">async_data_request_ready() reference={reference}")

        if reference != services.DATA_REQUEST_REFERENCE_DEVICES:
            logger.info(
                f"|async_data_request_ready() Ignoring unrelated reference {reference}"
            )
            return

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        if state is None:
            logger.warning("|async_data_request_ready() No analysis in progress")
            return

        radar_types = set(services.RADAR_DEVICE_TYPES)
        devices_by_location = {}

        if isinstance(content, dict):
            for location_id, location_devices in content.items():
                if not isinstance(location_devices, dict):
                    continue
                for device_id, device_info in location_devices.items():
                    if not isinstance(device_info, dict):
                        continue
                    device_type = device_info.get(
                        "deviceType", device_info.get("type")
                    )
                    try:
                        device_type_int = int(device_type)
                    except (TypeError, ValueError):
                        continue
                    if device_type_int not in radar_types:
                        continue
                    devices_by_location.setdefault(str(location_id), []).append(
                        {
                            "device_id": str(device_id),
                            "device_type": device_type_int,
                            "description": device_info.get(
                                "description", device_info.get("desc", "")
                            ),
                        }
                    )

        total_devices = sum(len(v) for v in devices_by_location.values())
        state["devices_data"] = {
            "devices_by_location": devices_by_location,
            "total_devices": total_devices,
            "total_locations": len(devices_by_location),
        }
        state["ready_for_processing"] = True
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        logger.info(
            f"|async_data_request_ready() Found {total_devices} radar devices "
            f"across {len(devices_by_location)} locations"
        )
        logger.info("<async_data_request_ready()")

    # ======================================================================
    # Sync report build + delivery
    # ======================================================================
    def _build_and_email_report(self, botengine, state):
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_build_and_email_report()")

        devices_data = state.get("devices_data") or {}
        devices_with_config = []
        missing_state_devices = []
        behaviors = None

        for location_id, devices in devices_data.get("devices_by_location", {}).items():
            location_rooms = self._safe_get_state(
                botengine, services.STATE_NAME_RADAR_ROOM, location_id
            )
            location_subs = self._safe_get_state(
                botengine, services.STATE_NAME_RADAR_SUBREGIONS, location_id
            )
            if behaviors is None:
                location_behaviors = self._safe_get_state(
                    botengine, services.STATE_NAME_RADAR_SUBREGION_BEHAVIORS, location_id
                )
                if isinstance(location_behaviors, list) and location_behaviors:
                    behaviors = location_behaviors

            if not isinstance(location_rooms, dict):
                location_rooms = {}
            if not isinstance(location_subs, dict):
                location_subs = {}

            for device in devices:
                device_id = device["device_id"]
                room = location_rooms.get(device_id)
                subs = location_subs.get(device_id)

                room_defaulted = room is None
                if room_defaulted:
                    room = dict(services.DEFAULT_ROOM)

                if subs is None:
                    subs = []
                    if device_id not in location_subs:
                        missing_state_devices.append(
                            (
                                location_id,
                                device_id,
                                "no radar_subregions state for this device",
                            )
                        )

                devices_with_config.append(
                    {
                        "location_id": location_id,
                        "device_id": device_id,
                        "device_type": device["device_type"],
                        "description": device.get("description", ""),
                        "room": room,
                        "subregions": list(subs),
                        "room_defaulted": room_defaulted,
                    }
                )

        self._finalize_report(
            botengine,
            state,
            devices_with_config,
            missing_state_devices,
            behaviors or [],
        )

        logger.info("<_build_and_email_report()")

    def _safe_get_state(self, botengine, name, location_id):
        """Wrap `botengine.get_state` so a single state failure doesn't kill the run."""
        try:
            return botengine.get_state(name, location_id=location_id)
        except Exception as e:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                f"|_safe_get_state() get_state({name}, location_id={location_id}) "
                f"failed: {e}"
            )
            return None

    def _finalize_report(
        self, botengine, state, devices_with_config, missing_devices, behaviors
    ):
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">_finalize_report()")

        config = state["config"]
        analysis_name = config.get("analysis_name", "Radar Subregion Analysis")

        try:
            summary = report_builder.compile_summary(
                devices_with_config, missing_devices
            )
            pdf_bytes = report_builder.generate_pdf(
                devices_with_config,
                summary,
                analysis_name,
                botengine.get_timestamp(),
                behaviors=behaviors,
            )
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
            html_summary = report_builder.generate_html_summary(summary, analysis_name)

            attachments = []
            botengine.add_email_attachment(
                destination_attachment_array=attachments,
                filename="Radar_Subregion_Analysis.pdf",
                content=pdf_base64,
                content_type="application/pdf",
                content_id="radar_subregion_analysis_pdf",
            )

            botengine.email_admins(
                email_subject=f"{analysis_name} - Radar Subregion Analysis",
                email_content=html_summary,
                email_html=True,
                email_attachments=attachments,
                email_addresses=config.get("email_addresses"),
                brand=properties.get_property(
                    botengine,
                    "ORGANIZATION_BRAND",
                    complain_if_missing=False,
                ),
            )

            logger.info("|_finalize_report() PDF generated and emailed")
        except ImportError as e:
            logger.warning(f"|_finalize_report() Missing dependency: {e}")
        except Exception as e:
            import traceback

            logger.error(f"|_finalize_report() Error: {e}\n{traceback.format_exc()}")

        self._cleanup(botengine)

        duration_ms = botengine.get_timestamp() - state["start_time"]
        logger.info(f"|_finalize_report() Completed in {duration_ms}ms")
        logger.info("<_finalize_report()")

    def _cleanup(self, botengine):
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, None, overwrite=True
        )
