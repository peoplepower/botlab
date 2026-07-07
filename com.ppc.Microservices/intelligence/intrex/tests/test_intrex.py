from unittest.mock import patch

import intelligence.intrex.event_types as event_types
from devices.button.intrex.button import IntrexButtonDevice  # type: ignore
from intelligence.intrex.location_intrex_microservice import (  # type: ignore
    CLASSIFICATION_FALSE_ALARM,
    CLASSIFICATION_REAL,
    INTREX_DEACTIVATION_OPTIONS_PROPERTY,
)
from locations.location import Location  # type: ignore

from botengine_pytest import BotEnginePyTest


class TestIntrexMicroservice:
    def _setup(self, device_id="101"):
        botengine = BotEnginePyTest({})
        # Clear out any previous tests
        botengine.reset()

        # Initialize the location
        location_object = Location(botengine, 0)

        device_object = IntrexButtonDevice(
            botengine, location_object, device_id, 0, "Test Intrex"
        )
        device_object.born_on = 10
        device_object.is_connected = True
        device_object.user_id = 123

        location_object.devices = {device_object.device_id: device_object}

        location_object.new_version(botengine)
        location_object.initialize(botengine)

        mut = location_object.intelligence_modules[
            "intelligence.intrex.location_intrex_microservice"
        ]
        return botengine, location_object, device_object, mut

    def test_intrex_initialization(self):
        botengine, location_object, device_object, mut = self._setup()
        assert mut is not None

    # ==========================================
    # event_types enum/helpers
    # ==========================================

    def test_event_types_ranges(self):
        assert event_types.is_staff_deactivation(2001)
        assert event_types.is_staff_deactivation(2026)
        assert not event_types.is_staff_deactivation(2027)
        assert not event_types.is_staff_deactivation(1)

        assert event_types.is_staff_accept(3001)
        assert event_types.is_staff_accept(3026)
        assert not event_types.is_staff_accept(3027)
        assert not event_types.is_staff_accept(2001)

    def test_event_types_alert_kind(self):
        # A deactivation and its +1000 accept mirror map to the same kind
        assert event_types.alert_kind(2001) == "button_press"
        assert event_types.alert_kind(3001) == "button_press"
        assert event_types.alert_kind(2002) == "fall"
        assert event_types.alert_kind(3002) == "fall"
        assert event_types.alert_kind(2025) == "cellular_fall"
        # Activation codes and anything outside the staff ranges are unknown
        assert event_types.alert_kind(1) == "unknown"
        assert event_types.alert_kind(9999) == "unknown"

    def test_event_types_is_fall_alert_kind(self):
        assert event_types.is_fall_alert_kind("fall")
        assert event_types.is_fall_alert_kind("cellular_fall")
        assert not event_types.is_fall_alert_kind("button_press")

    # ==========================================
    # intrex_event dispatch
    # ==========================================

    def test_intrex_event_accept_notifies_participants(self):
        botengine, location_object, device_object, mut = self._setup(device_id="101")

        # The intrex_event feed is delivered flat (no "event"/"data" wrappers).
        content = {
            "eventType": 3001,
            "type": "alert",
            "deviceId": "101",
        }

        with (
            patch("signals.conversation.accept_conversation") as mock_accept,
            patch("signals.conversation.resolve_conversation") as mock_resolve,
        ):
            mut.intrex_event(botengine, content)

            mock_accept.assert_called_once()
            mock_resolve.assert_not_called()
            kwargs = mock_accept.call_args.kwargs
            assert kwargs["device_id"] == "101"
            assert kwargs["arguments"]["alert_kind"] == "button_press"

    def test_intrex_event_deactivation_real_resolves(self):
        botengine, location_object, device_object, mut = self._setup(device_id="101")

        content = {
            "eventType": 2001,
            "type": "alert",
            "deviceId": "101",
            "deactivationOptionId": 235,
            "deactivationOptionName": "Emergency ",
            "deactivationOptionFallType": None,
        }

        with (
            patch("signals.conversation.resolve_conversation") as mock_resolve,
            patch("signals.conversation.accept_conversation") as mock_accept,
            patch("signals.analytics.track") as mock_track,
        ):
            mut.intrex_event(botengine, content)

            mock_accept.assert_not_called()
            mock_resolve.assert_called_once()
            kwargs = mock_resolve.call_args.kwargs
            assert kwargs["device_id"] == "101"
            # A real alert resolves with a TRUE_POSITIVE labeling option (1)
            assert kwargs["label"] == 1
            assert kwargs["arguments"]["classification"] == CLASSIFICATION_REAL
            assert kwargs["arguments"]["alert_kind"] == "button_press"
            mock_track.assert_called_once()

    def test_intrex_event_deactivation_false_alarm_via_org_property(self):
        botengine, location_object, device_object, mut = self._setup(device_id="101")

        # Organization property overrides the service default
        botengine.organization_properties[INTREX_DEACTIVATION_OPTIONS_PROPERTY] = {
            "Accidental": "false_alarm",
        }

        content = {
            "eventType": 2001,
            "deviceId": "101",
            "deactivationOptionId": 9,
            "deactivationOptionName": "Accidental",
        }

        with (
            patch("signals.conversation.resolve_conversation") as mock_resolve,
            patch("signals.analytics.track"),
        ):
            mut.intrex_event(botengine, content)

            kwargs = mock_resolve.call_args.kwargs
            # A false alarm resolves with a FALSE_POSITIVE labeling option (3)
            assert kwargs["label"] == 3
            assert kwargs["arguments"]["classification"] == CLASSIFICATION_FALSE_ALARM

    def test_intrex_event_activation_ignored(self):
        botengine, location_object, device_object, mut = self._setup(device_id="101")

        content = {"eventType": 1, "deviceId": "101"}

        with (
            patch("signals.conversation.accept_conversation") as mock_accept,
            patch("signals.conversation.resolve_conversation") as mock_resolve,
        ):
            mut.intrex_event(botengine, content)
            mock_accept.assert_not_called()
            mock_resolve.assert_not_called()

    # ==========================================
    # _classify_deactivation
    # ==========================================

    def test_classify_deactivation_default_real(self):
        botengine, location_object, device_object, mut = self._setup()
        event = {"deactivationOptionName": "Something Unmapped"}
        assert (
            mut._classify_deactivation(botengine, event, "button_press")
            == CLASSIFICATION_REAL
        )

    def test_classify_deactivation_name_mapping(self):
        botengine, location_object, device_object, mut = self._setup()
        # Service-default mapping classifies known option names (case-insensitive)
        assert (
            mut._classify_deactivation(
                botengine, {"deactivationOptionName": "Emergency"}, "button_press"
            )
            == CLASSIFICATION_REAL
        )
        assert (
            mut._classify_deactivation(
                botengine, {"deactivationOptionName": "Accidental Push"}, "button_press"
            )
            == CLASSIFICATION_FALSE_ALARM
        )

    def test_classify_deactivation_fall_type_numeric(self):
        botengine, location_object, device_object, mut = self._setup()
        # For a fall kind, a numeric fall type drives classification: 0 = no fall (false alarm), >0 = real fall
        assert (
            mut._classify_deactivation(
                botengine, {"deactivationOptionFallType": 0}, "fall"
            )
            == CLASSIFICATION_FALSE_ALARM
        )
        assert (
            mut._classify_deactivation(
                botengine, {"deactivationOptionFallType": 2}, "fall"
            )
            == CLASSIFICATION_REAL
        )
        # A non-fall kind ignores the fall type and uses the option-name mapping
        assert (
            mut._classify_deactivation(
                botengine,
                {
                    "deactivationOptionName": "emergency",
                    "deactivationOptionFallType": 0,
                },
                "button_press",
            )
            == CLASSIFICATION_REAL
        )

    # ==========================================
    # _device_for_intrex_id
    # ==========================================

    def test_device_for_intrex_id_resolution(self):
        botengine, location_object, device_object, mut = self._setup(
            device_id="Intrex-1404890704"
        )
        # The intrex_event delivers the bare Intrex id; it should resolve to the proxied local device
        resolved = mut._device_for_intrex_id(botengine, "1404890704")
        assert resolved is device_object
        # Unknown id resolves to None
        assert mut._device_for_intrex_id(botengine, "does-not-exist") is None
