"""
Created on May 4, 2026

Unit tests for the radar_subregion_analysis organization microservice.
"""

from io import BytesIO
from unittest.mock import patch

from intelligence.radar_subregion_analysis import (
    floorplan_builder,
    report_builder,
    services,
)
from organization.organization import Organization  # type: ignore

from botengine_pytest import BotEnginePyTest


# ===========================================================================
# Fixture helpers
# ===========================================================================
def _sample_room(mounting_type=services.MOUNTING_TYPE_WALL):
    return {
        "x_min_meters": -2.0,
        "x_max_meters": 2.0,
        "y_min_meters": 0.3,
        "y_max_meters": 4.0,
        "z_min_meters": 0.0,
        "z_max_meters": 2.0,
        "mounting_type": mounting_type,
        "sensor_height_m": 1.5,
        "updated_ms": 1762287934433,
        "near_exit": False,
    }


def _sample_subregion(
    name="Master Bed",
    context_id=services.CONTEXT_BED_QUEEN,
    bounds=(-1.5, 0.5, 0.5, 2.5, 0.0, 1.0),
    detect_falls=True,
    detect_presence=True,
    is_door=False,
    ai=False,
):
    sx0, sx1, sy0, sy1, sz0, sz1 = bounds
    return {
        "subregion_id": 0,
        "unique_id": f"sub-{name}",
        "name": name,
        "context_id": context_id,
        "x_min_meters": sx0,
        "x_max_meters": sx1,
        "y_min_meters": sy0,
        "y_max_meters": sy1,
        "z_min_meters": sz0,
        "z_max_meters": sz1,
        "detect_falls": detect_falls,
        "detect_presence": detect_presence,
        "is_door": is_door,
        "ai": ai,
        "low_sensor_energy": True,
        "hidden": False,
    }


def _sample_devices_content():
    """Simulate the DATA_REQUEST_TYPE_DEVICES response shape:
    content[location_id][device_id] = {deviceType, description, ...}
    """
    return {
        "100": {
            "dev_pontosense": {
                "deviceType": services.DEVICE_TYPE_PONTOSENSE,
                "description": "Pontosense bedroom",
            },
            "dev_thermostat": {
                "deviceType": 9999,  # unrelated, must be filtered out
                "description": "Thermostat",
            },
        },
        "200": {
            "dev_vayyar": {
                "deviceType": services.DEVICE_TYPE_VAYYAR,
                "description": "Vayyar bathroom",
            },
            "dev_assure": {
                "deviceType": services.DEVICE_TYPE_ASSURE,
                "description": "Assure living room",
            },
        },
    }


def _sample_devices_data():
    return {
        "devices_by_location": {
            "100": [
                {
                    "device_id": "dev_pontosense",
                    "device_type": services.DEVICE_TYPE_PONTOSENSE,
                    "description": "Pontosense bedroom",
                },
            ],
            "200": [
                {
                    "device_id": "dev_vayyar",
                    "device_type": services.DEVICE_TYPE_VAYYAR,
                    "description": "Vayyar bathroom",
                },
                {
                    "device_id": "dev_assure",
                    "device_type": services.DEVICE_TYPE_ASSURE,
                    "description": "Assure living room",
                },
            ],
        },
        "total_devices": 3,
        "total_locations": 2,
    }


def _build_state(
    ready=False,
    devices_data=None,
):
    return {
        "config": {
            "email_addresses": ["admin@example.com"],
            "analysis_name": "Radar Subregion Analysis",
        },
        "phase": services.PHASE_DEVICES,
        "start_time": 1773550800000,
        "devices_data": devices_data,
        "ready_for_processing": ready,
    }


def _make_get_state_stub(state_table):
    """
    Build a fake `botengine.get_state(name, location_id=...)` callable.

    :param state_table: Nested dict {location_id: {state_name: value}}.
    """

    def _stub(name, location_id=None, **_kwargs):
        return state_table.get(str(location_id), {}).get(name)

    return _stub


# ===========================================================================
# services.py helpers
# ===========================================================================
class TestServicesHelpers:
    def test_context_name_known_and_unknown(self):
        assert services.context_name(services.CONTEXT_BED) == "Bed"
        assert services.context_name(services.CONTEXT_TOILET) == "Toilet"
        assert services.context_name(8888) == "Other"

    def test_context_color_known_and_unknown(self):
        assert services.context_color(services.CONTEXT_BED).startswith("#")
        assert services.context_color(8888) == services.DEFAULT_CONTEXT_COLOR

    def test_device_type_name_known_and_unknown(self):
        assert (
            services.device_type_name(services.DEVICE_TYPE_PONTOSENSE) == "Pontosense"
        )
        assert services.device_type_name(424242) == "Type 424242"

    def test_mounting_type_name_known_and_unknown(self):
        assert services.mounting_type_name(services.MOUNTING_TYPE_CORNER) == "Corner"
        assert services.mounting_type_name(99) == "Type 99"

    def test_radar_device_types_consistent(self):
        # Known production values from each radar device class.
        assert services.DEVICE_TYPE_VAYYAR == 2000
        assert services.DEVICE_TYPE_PONTOSENSE == 2007
        assert services.DEVICE_TYPE_ASSURE == 2020
        assert set(services.RADAR_DEVICE_TYPES) == {2000, 2007, 2020}

    def test_radar_state_names(self):
        assert services.STATE_NAME_RADAR_ROOM == "radar_room"
        assert services.STATE_NAME_RADAR_SUBREGIONS == "radar_subregions"
        assert (
            services.STATE_NAME_RADAR_SUBREGION_BEHAVIORS
            == "radar_subregion_behaviors"
        )


# ===========================================================================
# floorplan_builder.py
# ===========================================================================
class TestFloorplanBuilder:
    def test_returns_png_bytesio(self):
        room = _sample_room()
        subregions = [_sample_subregion()]
        buf = floorplan_builder.generate_floorplan(room, subregions, "Test Device")
        assert isinstance(buf, BytesIO)
        head = buf.read(8)
        assert head[:8] == b"\x89PNG\r\n\x1a\n"
        buf.close()

    def test_works_with_empty_subregions(self):
        buf = floorplan_builder.generate_floorplan(_sample_room(), [], "Empty")
        assert isinstance(buf, BytesIO)
        assert buf.read(4) == b"\x89PNG"
        buf.close()

    def test_works_with_default_room(self):
        buf = floorplan_builder.generate_floorplan({}, [], "Default")
        assert isinstance(buf, BytesIO)
        assert buf.read(4) == b"\x89PNG"
        buf.close()

    def test_skips_subregions_with_missing_bounds(self):
        partial = {"name": "broken", "context_id": services.CONTEXT_BED}
        buf = floorplan_builder.generate_floorplan(_sample_room(), [partial], "Skip")
        assert isinstance(buf, BytesIO)
        buf.close()

    def test_pontosense_flips_x_axis(self):
        """For Pontosense devices the rendered X-axis is inverted so the
        sensor at (0, 0) ends up at the bottom-right corner of the chart."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Use a spy on plt.subplots so we can grab the Axes object
        # the renderer creates.
        captured = {}
        original_subplots = plt.subplots

        def spy(*args, **kwargs):
            fig, ax = original_subplots(*args, **kwargs)
            captured["ax"] = ax
            return fig, ax

        with patch.object(plt, "subplots", side_effect=spy):
            buf = floorplan_builder.generate_floorplan(
                _sample_room(),
                [_sample_subregion()],
                "Pontosense",
                device_type=services.DEVICE_TYPE_PONTOSENSE,
            )
        buf.close()

        ax = captured["ax"]
        xmin, xmax = ax.get_xlim()
        # Inverted axis -> first limit > second limit.
        assert xmin > xmax

    def test_non_pontosense_does_not_flip_x_axis(self):
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        captured = {}
        original_subplots = plt.subplots

        def spy(*args, **kwargs):
            fig, ax = original_subplots(*args, **kwargs)
            captured["ax"] = ax
            return fig, ax

        with patch.object(plt, "subplots", side_effect=spy):
            buf = floorplan_builder.generate_floorplan(
                _sample_room(),
                [_sample_subregion()],
                "Vayyar",
                device_type=services.DEVICE_TYPE_VAYYAR,
            )
        buf.close()

        ax = captured["ax"]
        xmin, xmax = ax.get_xlim()
        # Normal orientation -> first limit < second limit.
        assert xmin < xmax


# ===========================================================================
# report_builder.py
# ===========================================================================
class TestReportBuilder:
    def _entries(self):
        return [
            {
                "location_id": "100",
                "device_id": "dev_pontosense",
                "device_type": services.DEVICE_TYPE_PONTOSENSE,
                "description": "Pontosense bedroom",
                "room": _sample_room(),
                "subregions": [
                    _sample_subregion(name="Bed", context_id=services.CONTEXT_BED),
                    _sample_subregion(
                        name="Door",
                        context_id=services.CONTEXT_EXIT,
                        is_door=True,
                    ),
                ],
                "room_defaulted": False,
            },
            {
                "location_id": "200",
                "device_id": "dev_vayyar",
                "device_type": services.DEVICE_TYPE_VAYYAR,
                "description": "Vayyar bathroom",
                "room": _sample_room(),
                "subregions": [],
                "room_defaulted": True,
            },
        ]

    def test_compile_summary_tallies(self):
        entries = self._entries()
        errors = [("300", "dev_missing", "no radar_subregions state")]

        summary = report_builder.compile_summary(entries, errors)

        assert summary["total_locations"] == 2
        assert summary["total_devices"] == 2
        assert summary["total_subregions"] == 2
        assert summary["by_device_type"][services.DEVICE_TYPE_PONTOSENSE] == 1
        assert summary["by_device_type"][services.DEVICE_TYPE_VAYYAR] == 1
        assert summary["by_context"][services.CONTEXT_BED] == 1
        assert summary["by_context"][services.CONTEXT_EXIT] == 1
        assert len(summary["devices_without_subregions"]) == 1
        assert summary["missing_property_devices"] == errors

    def test_generate_pdf_returns_bytes(self):
        entries = self._entries()
        summary = report_builder.compile_summary(entries, [])
        pdf_bytes = report_builder.generate_pdf(
            entries, summary, "Test Run", 1773550800000
        )
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert pdf_bytes[:5] == b"%PDF-"

    def test_generate_pdf_with_errors_appendix(self):
        entries = self._entries()
        errors = [("300", "broken_dev", "no radar_subregions state")]
        summary = report_builder.compile_summary(entries, errors)
        pdf_bytes = report_builder.generate_pdf(
            entries, summary, "Test Run", 1773550800000
        )
        assert pdf_bytes[:5] == b"%PDF-"

    def test_generate_pdf_with_behaviors(self):
        entries = self._entries()
        summary = report_builder.compile_summary(entries, [])
        behaviors = [
            {"context_id": services.CONTEXT_BED, "title": "Custom Bed Title"},
            {"context_id": services.CONTEXT_EXIT, "title": "Custom Door Title"},
        ]
        pdf_bytes = report_builder.generate_pdf(
            entries, summary, "Test Run", 1773550800000, behaviors=behaviors
        )
        assert pdf_bytes[:5] == b"%PDF-"

    def test_behaviors_to_title_map_filters_invalid(self):
        behaviors = [
            {"context_id": services.CONTEXT_BED, "title": "Bed"},
            {"context_id": "non-int", "title": "Skip"},
            {"context_id": services.CONTEXT_TOILET, "title": ""},  # empty title
            "garbage entry",
            {"context_id": services.CONTEXT_EXIT, "title": "Exit"},
        ]
        titles = report_builder.behaviors_to_title_map(behaviors)
        assert titles == {
            services.CONTEXT_BED: "Bed",
            services.CONTEXT_EXIT: "Exit",
        }

    def test_context_label_prefers_behavior_title(self):
        titles = {services.CONTEXT_BED: "Custom Bed"}
        assert (
            report_builder.context_label(services.CONTEXT_BED, titles) == "Custom Bed"
        )
        # Falls back to services.CONTEXT_NAMES when behavior is missing.
        assert (
            report_builder.context_label(services.CONTEXT_TOILET, titles) == "Toilet"
        )

    def test_generate_html_summary_includes_counts(self):
        entries = self._entries()
        summary = report_builder.compile_summary(entries, [])
        html = report_builder.generate_html_summary(summary, "Test Run")
        assert "Test Run" in html
        assert "Pontosense" in html
        assert "Vayyar" in html
        # Total subregions = 2
        assert ">2<" in html

    def test_sanitize_strips_smart_punctuation(self):
        assert report_builder._sanitize("don’t") == "don't"
        assert report_builder._sanitize("a — b") == "a - b"
        assert report_builder._sanitize("“hello”") == '"hello"'


# ===========================================================================
# Microservice
# ===========================================================================
class TestRadarSubregionAnalysisMicroservice:
    _MODULE_PATH = (
        "intelligence.radar_subregion_analysis."
        "organization_radar_subregion_analysis_microservice"
    )

    def _setup(self):
        botengine = BotEnginePyTest({})
        botengine.reset()
        organization = Organization(botengine, 0)
        organization.new_version(botengine)
        organization.initialize(botengine)
        mut = organization.intelligence_modules[self._MODULE_PATH]
        return botengine, organization, mut

    # --------------------------- lifecycle -------------------------------
    def test_initialization(self):
        botengine, _, mut = self._setup()
        assert mut is not None
        mut.new_version(botengine)
        mut.initialize(botengine)
        mut.destroy(botengine)

    def test_datastream_routing(self):
        botengine, _, mut = self._setup()
        with patch.object(mut, "radar_subregion_analysis_run") as mock_run:
            mut.datastream_updated(
                botengine, "radar_subregion_analysis_run", {"x": 1}
            )
            mock_run.assert_called_once_with(botengine, {"x": 1})

        # Unknown address must not raise.
        mut.datastream_updated(botengine, "no_such_address", {})

    def test_run_requires_email_addresses(self):
        botengine, _, mut = self._setup()

        with patch.object(botengine, "request_data") as mock_rd:
            mut.radar_subregion_analysis_run(botengine, {})
            mock_rd.assert_not_called()

        with patch.object(botengine, "request_data") as mock_rd:
            mut.radar_subregion_analysis_run(botengine, {"email_addresses": []})
            mock_rd.assert_not_called()

        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

    def test_run_starts_devices_phase(self):
        botengine, _, mut = self._setup()

        with patch.object(botengine, "request_data") as mock_rd:
            mut.radar_subregion_analysis_run(
                botengine, {"email_addresses": ["a@b.com"]}
            )
            mock_rd.assert_called_once()
            assert (
                mock_rd.call_args[1]["reference"]
                == services.DATA_REQUEST_REFERENCE_DEVICES
            )
            assert mock_rd.call_args[1]["device_types"] == services.RADAR_DEVICE_TYPES

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state is not None
        assert state["phase"] == services.PHASE_DEVICES
        assert state["config"]["email_addresses"] == ["a@b.com"]
        assert state["ready_for_processing"] is False

    def test_concurrent_run_is_rejected(self):
        botengine, _, mut = self._setup()

        with patch.object(botengine, "request_data"):
            mut.radar_subregion_analysis_run(
                botengine, {"email_addresses": ["a@b.com"]}
            )

        with patch.object(botengine, "request_data") as mock_rd:
            mut.radar_subregion_analysis_run(
                botengine, {"email_addresses": ["a@b.com"]}
            )
            mock_rd.assert_not_called()

    # --------------------------- DEVICES phase ---------------------------
    def test_async_devices_filters_non_radar(self):
        botengine, _, mut = self._setup()
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, _build_state(), overwrite=True
        )

        mut.async_data_request_ready(
            botengine,
            services.DATA_REQUEST_REFERENCE_DEVICES,
            _sample_devices_content(),
        )

        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state["ready_for_processing"] is True
        devices_by_location = state["devices_data"]["devices_by_location"]
        assert "100" in devices_by_location
        assert "200" in devices_by_location
        assert {d["device_id"] for d in devices_by_location["100"]} == {
            "dev_pontosense"
        }
        assert {d["device_id"] for d in devices_by_location["200"]} == {
            "dev_vayyar",
            "dev_assure",
        }
        assert state["devices_data"]["total_devices"] == 3
        assert state["devices_data"]["total_locations"] == 2

    def test_async_unknown_reference_is_ignored(self):
        botengine, _, mut = self._setup()
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, _build_state(), overwrite=True
        )

        mut.async_data_request_ready(botengine, "some_other_ref", {})
        state = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state["ready_for_processing"] is False

    def test_async_no_state_does_not_crash(self):
        botengine, _, mut = self._setup()
        mut.async_data_request_ready(
            botengine, services.DATA_REQUEST_REFERENCE_DEVICES, {}
        )

    # --------------------------- timer / report -------------------------
    def test_timer_devices_phase_triggers_report(self):
        botengine, _, mut = self._setup()
        state = _build_state(ready=True, devices_data=_sample_devices_data())
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        with patch.object(mut, "_build_and_email_report") as mock_build:
            mut.timer_fired(
                botengine,
                {
                    "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                    "phase": services.PHASE_DEVICES,
                    "retry_count": 0,
                },
            )
            mock_build.assert_called_once()

        # ready_for_processing reset before bridge so re-entry is safe.
        state2 = botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS)
        assert state2["ready_for_processing"] is False

    def test_timer_retries_then_gives_up(self):
        botengine, _, mut = self._setup()
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS,
            _build_state(ready=False),
            overwrite=True,
        )

        with patch.object(mut, "start_timer_s") as mock_timer:
            mut.timer_fired(
                botengine,
                {
                    "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                    "phase": services.PHASE_DEVICES,
                    "retry_count": 0,
                },
            )
            mock_timer.assert_called_once()
            assert mock_timer.call_args[1]["argument"]["retry_count"] == 1

        with patch.object(mut, "start_timer_s") as mock_timer:
            mut.timer_fired(
                botengine,
                {
                    "type": services.TIMER_TYPE_DATA_REQUEST_TIMEOUT,
                    "phase": services.PHASE_DEVICES,
                    "retry_count": services.MAX_DATA_REQUEST_RETRIES,
                },
            )
            mock_timer.assert_not_called()

        # State should be cleaned up after max retries.
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

    def test_timer_ignores_non_dict_or_unrelated_arguments(self):
        botengine, _, mut = self._setup()
        # Should not raise.
        mut.timer_fired(botengine, "string-arg")
        mut.timer_fired(botengine, 42)
        mut.timer_fired(botengine, None)
        mut.timer_fired(botengine, {"type": "something_else"})

    # --------------------------- get_state composition -------------------
    def test_build_report_pulls_state_per_location(self):
        botengine, _, mut = self._setup()
        state = _build_state(devices_data=_sample_devices_data())
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        bed = _sample_subregion(name="King Bed", context_id=services.CONTEXT_BED_KING)
        door = _sample_subregion(
            name="Door",
            context_id=services.CONTEXT_EXIT,
            is_door=True,
            bounds=(-0.5, 0.5, 3.5, 4.0, 0.0, 2.0),
        )
        bathroom = _sample_subregion(
            name="Walk-in Shower",
            context_id=services.CONTEXT_WALK_IN_SHOWER,
            bounds=(-0.43, 0.48, 0.58, 2.1, 0.0, 2.0),
        )
        behaviors = [
            {"context_id": services.CONTEXT_BED_KING, "title": "King Bed"},
            {"context_id": services.CONTEXT_EXIT, "title": "Door or entry way"},
        ]

        state_table = {
            "100": {
                services.STATE_NAME_RADAR_ROOM: {"dev_pontosense": _sample_room()},
                services.STATE_NAME_RADAR_SUBREGIONS: {
                    "dev_pontosense": [bed, door]
                },
                services.STATE_NAME_RADAR_SUBREGION_BEHAVIORS: behaviors,
            },
            "200": {
                # vayyar present, assure missing from radar_subregions
                services.STATE_NAME_RADAR_ROOM: {"dev_vayyar": _sample_room()},
                services.STATE_NAME_RADAR_SUBREGIONS: {"dev_vayyar": [bathroom]},
            },
        }

        with (
            patch.object(
                botengine, "get_state", side_effect=_make_get_state_stub(state_table)
            ) as mock_gs,
            patch.object(mut, "_finalize_report") as mock_fin,
        ):
            mut._build_and_email_report(botengine, state)

            # Three calls per location for radar_room/subregions/behaviors,
            # except behaviors short-circuits once a non-empty list is found.
            called_names = {
                (call.args[0], call.kwargs.get("location_id"))
                for call in mock_gs.call_args_list
            }
            assert (services.STATE_NAME_RADAR_ROOM, "100") in called_names
            assert (services.STATE_NAME_RADAR_SUBREGIONS, "100") in called_names
            assert (
                services.STATE_NAME_RADAR_SUBREGION_BEHAVIORS,
                "100",
            ) in called_names
            assert (services.STATE_NAME_RADAR_ROOM, "200") in called_names
            assert (services.STATE_NAME_RADAR_SUBREGIONS, "200") in called_names
            # Behaviors not requested for location 200 because location 100
            # already supplied a non-empty list.
            assert (
                services.STATE_NAME_RADAR_SUBREGION_BEHAVIORS,
                "200",
            ) not in called_names

            _, _, devices_with_config, missing, fwd_behaviors = mock_fin.call_args[0]

            ids = {(e["location_id"], e["device_id"]) for e in devices_with_config}
            assert ids == {
                ("100", "dev_pontosense"),
                ("200", "dev_vayyar"),
                ("200", "dev_assure"),
            }

            by_id = {e["device_id"]: e for e in devices_with_config}
            assert by_id["dev_pontosense"]["room_defaulted"] is False
            assert len(by_id["dev_pontosense"]["subregions"]) == 2
            assert by_id["dev_vayyar"]["room_defaulted"] is False
            assert len(by_id["dev_vayyar"]["subregions"]) == 1

            # Assure: location 200 has no entry for it in radar_subregions ->
            # defaulted + appears in missing.
            assert by_id["dev_assure"]["room_defaulted"] is True
            assert by_id["dev_assure"]["subregions"] == []
            assert any(d_id == "dev_assure" for _, d_id, _ in missing)

            assert fwd_behaviors == behaviors

    def test_build_report_handles_get_state_exceptions(self):
        botengine, _, mut = self._setup()
        state = _build_state(devices_data=_sample_devices_data())
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, state, overwrite=True
        )

        def boom(name, location_id=None, **_):
            if location_id == "200":
                raise RuntimeError("upstream timeout")
            return None

        with (
            patch.object(botengine, "get_state", side_effect=boom),
            patch.object(mut, "_finalize_report") as mock_fin,
        ):
            mut._build_and_email_report(botengine, state)

            _, _, devices_with_config, missing, _ = mock_fin.call_args[0]

            # All three devices should still appear, all defaulted, all missing.
            assert {e["device_id"] for e in devices_with_config} == {
                "dev_pontosense",
                "dev_vayyar",
                "dev_assure",
            }
            for entry in devices_with_config:
                assert entry["room_defaulted"] is True
                assert entry["subregions"] == []
            missing_ids = {d_id for _, d_id, _ in missing}
            assert missing_ids == {"dev_pontosense", "dev_vayyar", "dev_assure"}

    def test_finalize_report_emails_pdf(self):
        botengine, _, mut = self._setup()
        state = _build_state()
        entries = [
            {
                "location_id": "100",
                "device_id": "dev_pontosense",
                "device_type": services.DEVICE_TYPE_PONTOSENSE,
                "description": "Pontosense bedroom",
                "room": _sample_room(),
                "subregions": [_sample_subregion()],
                "room_defaulted": False,
            }
        ]

        with (
            patch.object(botengine, "add_email_attachment") as mock_attach,
            patch.object(botengine, "email_admins") as mock_email,
        ):
            mut._finalize_report(botengine, state, entries, [], [])
            mock_attach.assert_called_once()
            assert (
                mock_attach.call_args[1]["filename"] == "Radar_Subregion_Analysis.pdf"
            )
            assert mock_attach.call_args[1]["content_type"] == "application/pdf"
            mock_email.assert_called_once()
            assert mock_email.call_args[1]["email_addresses"] == ["admin@example.com"]

        # State should be cleaned up after a successful run.
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None

    def test_cleanup_clears_state(self):
        botengine, _, mut = self._setup()
        botengine.save_variable(
            services.STATE_VAR_ANALYSIS_IN_PROGRESS, _build_state(), overwrite=True
        )
        mut._cleanup(botengine)
        assert botengine.load_variable(services.STATE_VAR_ANALYSIS_IN_PROGRESS) is None
