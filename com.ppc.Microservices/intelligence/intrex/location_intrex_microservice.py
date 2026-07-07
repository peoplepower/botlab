'''
Created on August 17, 2018

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter
'''


from intelligence.intelligence import Intelligence
from devices.button import ButtonDevice, IntrexButtonDevice
from devices.motion import MotionDevice, IntrexMotionDevice
from devices.entry import EntryDevice, IntrexEntryDevice
from devices.alarm import AlarmDevice, IntrexPullCordDevice

import intelligence.intrex.event_types as event_types

import json
import utilities.utilities as utilities
import signals.conversation as conversation
import signals.dashboard as dashboard
import signals.insights as insights
import signals.analytics as analytics
import signals.trends as trends
import properties

# Test IDs
TEST_ID_SOS = 0

# Timers
TIMER_DEVICE_ADDED_MS = utilities.ONE_MINUTE_MS
TIMER_DEVICE_ADDED = "device_added"

# Deactivation classification values
CLASSIFICATION_REAL = "real"
CLASSIFICATION_FALSE_ALARM = "false_alarm"

# Organization/domain property name for the configurable deactivation-option classification mapping
INTREX_DEACTIVATION_OPTIONS_PROPERTY = "INTREX_DEACTIVATION_OPTIONS"

# Service-default mapping of a normalized deactivationOptionName -> classification.
# Resolved with precedence: organization property -> bot bundle domain property -> this default.
# The enum of option names/fall types is configurable on the Intrex platform; seed the known ones here.
DEFAULT_INTREX_DEACTIVATION_OPTIONS = {
    "emergency": CLASSIFICATION_REAL,
    "accidental push": CLASSIFICATION_FALSE_ALARM,
    "no person detected": CLASSIFICATION_FALSE_ALARM,
    "not resident": CLASSIFICATION_FALSE_ALARM,
    "intentionally on floor": CLASSIFICATION_FALSE_ALARM,
    "unintentionally on floor": CLASSIFICATION_FALSE_ALARM,
    "resident did not fall false alarm": CLASSIFICATION_FALSE_ALARM,
    "resident did fall": CLASSIFICATION_REAL,
    "accidental button press": CLASSIFICATION_FALSE_ALARM,
    "accidental press": CLASSIFICATION_FALSE_ALARM,
    "concierge": CLASSIFICATION_FALSE_ALARM,
    "emergency": CLASSIFICATION_REAL,
    "emergency ": CLASSIFICATION_REAL,
    "false alert": CLASSIFICATION_FALSE_ALARM,
    "false elopement": CLASSIFICATION_FALSE_ALARM,
    "false elopement ": CLASSIFICATION_FALSE_ALARM,
    "intentionally_on_floor": CLASSIFICATION_FALSE_ALARM,
    "no_person_detected": CLASSIFICATION_FALSE_ALARM,
    "not_resident": CLASSIFICATION_FALSE_ALARM,
    "personal care ": CLASSIFICATION_FALSE_ALARM,
    "planned outing": CLASSIFICATION_FALSE_ALARM,
    "resident did not fall - false alarm": CLASSIFICATION_FALSE_ALARM,
    "test press": CLASSIFICATION_FALSE_ALARM,
    "true alert": CLASSIFICATION_REAL,
    "true elopement ": CLASSIFICATION_REAL,
}

## Intrex fall-type constants for deactivationOptionFallType (when present) in the intrex_event data stream.
INTREX_DEACTIVATION_FALL_TYPE_NO_FALL = 0
INTREX_DEACTIVATION_FALL_TYPE_SOFT_FALL = 1
INTREX_DEACTIVATION_FALL_TYPE_HARD_FALL = 2

# When a deactivation option is not present in the mapping, classify the alert as a real, attended alert.
DEFAULT_INTREX_DEACTIVATION_CLASSIFICATION = CLASSIFICATION_REAL

class LocationIntrexMicroservice(Intelligence):
    """
    """
    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, either a location or a device object.
        """
        Intelligence.__init__(self, botengine, parent)
        pass

    def new_version(self, botengine):
        """
        Upgraded to a new bot version
        :param botengine: BotEngine environment
        """
        pass

    def destroy(self, botengine):
        """
        This device or object is getting permanently deleted - it is no longer in the user's account.
        :param botengine: BotEngine environment
        """
        pass

    def mode_updated(self, botengine, current_mode):
        """
        Mode was updated
        :param botengine: BotEngine environment
        :param current_mode: Current mode
        :param current_timestamp: Current timestamp
        """
        pass

    def device_measurements_updated(self, botengine, device_object):
        """
        Device was updated
        :param botengine: BotEngine environment
        :param device_object: Device object that was updated
        """
        pass

    def user_role_updated(
        self,
        botengine,
        location_id,
        user_id,
        role,
        previous_role,
        category,
        previous_category,
        location_access,
        previous_location_access,
        residency,
        previous_residency,
    ):
        """
        A user changed roles
        :param botengine: BotEngine environment
        :param location_id: Location ID
        :param user_id: User ID that changed
        :param role: ROLE_TYPE_* Application-layer agreed upon role integer which may auto-configure location_access and alert category
        :param previous_role: User's previous role, if any
        :param category: ALERT_CATEGORY_* User's current alert/communications category (1=resident; 2=supporter)
        :param previous_category: User's previous category, if any
        :param location_access: LOCATION_ACCESS_* User's current access to the location
        :param previous_location_access: User's previous access to the location, if any
        :param residency: RESIDENCY_* User's current residency status
        :param previous_residency: User's previous residency status, if any
        :return:
        """
        pass

    def device_metadata_updated(self, botengine, device_object):
        """
        Evaluate a device that is new or whose goal/scenario was recently updated
        :param botengine: BotEngine environment
        :param device_object: Device object that was updated
        """
        pass

    def device_alert(self, botengine, device_object, alert_type, alert_params):
        """
        Device sent an alert.
        :param botengine: BotEngine environment
        :param device_object: Device object that sent the alert
        :param alert_type: Type of alert
        :param alert_params: Alert parameters as key/value dictionary
        """
        pass

    def device_added(self, botengine, device_object):
        """
        A new Device was added to this Location
        :param botengine: BotEngine environment
        :param device_object: Device object that is getting added
        """
        return
    
    def device_deleted(self, botengine, device_object):
        """
        Device is getting deleted
        :param botengine: BotEngine environment
        :param device_object: Device object that is getting deleted
        """
        pass

    def question_answered(self, botengine, question):
        """
        The user answered a question
        :param botengine: BotEngine environment
        :param question: Question object
        """
        pass

    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Message Received
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Content of the message
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)
        pass

    def timer_fired(self, botengine, argument):
        """
        The bot's intelligence timer fired
        :param botengine: Current botengine environment
        :param argument: Argument applied when setting the timer
        """
        pass

    def file_uploaded(self, botengine, device_object, file_id, filesize_bytes, content_type, file_extension):
        """
        A device file has been uploaded
        :param botengine: BotEngine environment
        :param device_object: Device object that uploaded the file
        :param file_id: File ID to reference this file at the server
        :param filesize_bytes: The file size in bytes
        :param content_type: The content type, for example 'video/mp4'
        :param file_extension: The file extension, for example 'mp4'
        """
        pass

    def coordinates_updated(self, botengine, latitude, longitude):
        """
        Approximate coordinates of the parent proxy device object have been updated
        :param latitude: Latitude
        :param longitude: Longitude
        """
        pass

    def occupancy_status_updated(self, botengine, status, reason, last_status, last_reason):
        """
        Occupancy status updated
        :param botengine:
        :param content:
        :return:
        """
        pass

    def ism_updated(self, botengine, content):
        """
        Data stream message : Recalculate path models from a given integrated sensor matrix
        Depends upon the 'machine_learning' microservice package
        :param botengine:
        :return:
        """
        pass

    ####################################################################################################################
    # Data Stream Messages
    ####################################################################################################################

    def intrex_run_test(self, botengine, content):
        """
        Data stream message : Internet Data Usage
        :param botengine:
        :param content:
        :return:
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(">intrex_run_test() content={}".format(content))
        test_id = content.get('test_id')
        if test_id is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info("<intrex_run_test() Test ID not found")
            return
        
        device_object = None
        for device_id, device in self.parent.devices.items():
            if utilities._isinstance(device, IntrexButtonDevice) and device.user_id is not None:
                device_object = device
                break
        if device_object is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info("<intrex_run_test() No Intrex Button Device found")
            return
            
        if test_id == TEST_ID_SOS:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info("|intrex_run_test() Test SOS")
            pass
            
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info("<intrex_run_test()")
        pass

    

    ####################################################################################################################
    # Internal Methods
    ####################################################################################################################
    
    def intrex_event(self, botengine, content):
        """
        Data stream message : Intrex Event

        Handles the Intrex (Rythmos) alert lifecycle delivered on the `intrex_event` data stream:
          * Staff accept (eventType 3001-3026) -> notify the active alert's participants ("Staff is responding").
          * Staff deactivation (eventType 2001-2026) -> resolve the active alert, classifying it as a real
            alert or a false alarm so that false positives are kept out of existing trend metrics.

        Activation events (eventType 1-37, 1001-1007) arrive as device measurements, not here, so they are
        logged and ignored.

        :param botengine: BotEngine environment
        :param content: Data stream content (the `intrex_event` feed; may wrap the event under "event")
        :return:
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">intrex_event() content={}".format(content))

        if not isinstance(content, dict):
            logger.warning("<intrex_event() Unexpected content type: {}".format(type(content)))
            return

        event_type = content.get("eventType")
        if event_type is None:
            logger.warning("<intrex_event() No eventType found in content")
            return
        try:
            event_type = int(event_type)
        except (TypeError, ValueError):
            logger.warning("<intrex_event() eventType is not an integer: {}".format(event_type))
            return

        # Resolve the Intrex device id to a local device so we act on the correct (per-device) conversation.
        intrex_device_id = content.get("deviceId")
        device_object = self._device_for_intrex_id(botengine, intrex_device_id)
        local_device_id = device_object.device_id if device_object is not None else None

        kind = event_types.alert_kind(event_type)

        if event_types.is_staff_accept(event_type):
            logger.info("|intrex_event() Staff accepted alert kind={} device_id={}".format(kind, local_device_id))
            conversation.accept_conversation(
                botengine,
                self.parent,
                device_id=local_device_id,
                message=_("Staff is responding to the alert."),  # noqa: F821 # type: ignore
                arguments={
                    "alert_kind": kind,
                },
            )

        elif event_types.is_staff_deactivation(event_type):
            classification = self._classify_deactivation(botengine, content, kind)
            option_name = (content.get("deactivationOptionName") or "").strip()
            logger.info(
                "|intrex_event() Staff deactivated alert kind={} classification={} option={} device_id={}".format(
                    kind, classification, option_name, local_device_id
                )
            )
            # Defined by optional conversation service
            CONVERSATION_LABELING_OPTION_FALSE_POSITIVE = 3
            CONVERSATION_LABELING_OPTION_TRUE_POSITIVE = 1

            conversation.resolve_conversation(
                botengine,
                self.parent,
                device_id=local_device_id,
                message=_("Deactivated by staff: {}").format(option_name or _("Resolved")),  # noqa: F821 # type: ignore
                label=CONVERSATION_LABELING_OPTION_FALSE_POSITIVE if classification == CLASSIFICATION_FALSE_ALARM else CONVERSATION_LABELING_OPTION_TRUE_POSITIVE,
                arguments={
                    "alert_kind": kind,
                    "classification": classification,
                    "deactivation_option_id": content.get("deactivationOptionId"),
                    "deactivation_option_name": option_name or None,
                    "deactivation_option_fall_type": content.get("deactivationOptionFallType"),
                },
            )

            analytics.track(
                botengine,
                self.parent,
                "intrex_alert_deactivated",
                properties={
                    "alert_kind": kind,
                    "classification": classification,
                    "deactivation_option_id": content.get("deactivationOptionId"),
                    "deactivation_option_name": option_name or None,
                    "deactivation_option_fall_type": content.get("deactivationOptionFallType"),
                },
            )

        else:
            # Activation events (reported as device measurements) and any unrecognized event types are ignored.
            logger.info("|intrex_event() Ignoring eventType={} (kind={})".format(event_type, kind))

        logger.info("<intrex_event()")

    def _device_for_intrex_id(self, botengine, intrex_device_id):
        """
        Resolve an Intrex/Rythmos device id (as delivered in an intrex_event, e.g. "1404890704") to the
        local device object. The Intrex proxy id is embedded in the local device id, so match by equality
        first, then by suffix/substring for proxied ids (e.g. "Intrex-1404890704").

        :param botengine: BotEngine environment
        :param intrex_device_id: Device id string from the intrex_event content
        :return: Device object, or None if no local device matches
        """
        if intrex_device_id is None:
            return None

        intrex_device_id = str(intrex_device_id)
        for device_id, device_object in self.parent.devices.items():
            device_id = str(device_id)
            if device_id == intrex_device_id or device_id.endswith(intrex_device_id) or intrex_device_id in device_id:
                return device_object

        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|_device_for_intrex_id() No local device matched Intrex device id={}".format(intrex_device_id)
        )
        return None

    def _classify_deactivation(self, botengine, event, kind):
        """
        Classify a staff deactivation as a real alert or a false alarm using a configurable mapping resolved
        with precedence: organization property -> bot bundle domain property -> service default.

        For fall alert kinds, the Intrex `deactivationOptionFallType` is preferred when present; otherwise the
        deactivationOptionName is looked up in the mapping. Unmapped options default to a real,
        attended alert.

        :param botengine: BotEngine environment
        :param event: The intrex_event "event" dictionary
        :param kind: Canonical alert kind from event_types.alert_kind()
        :return: CLASSIFICATION_REAL or CLASSIFICATION_FALSE_ALARM
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|_classify_deactivation() kind={} event={}".format(kind, event)
        )
        option_name = (event.get("deactivationOptionName") or "").strip()
        fall_type = event.get("deactivationOptionFallType")

        mapping = properties.get_property(
            botengine,
            INTREX_DEACTIVATION_OPTIONS_PROPERTY,
            complain_if_missing=False,
            default=DEFAULT_INTREX_DEACTIVATION_OPTIONS,
        )
        if not isinstance(mapping, dict):
            mapping = DEFAULT_INTREX_DEACTIVATION_OPTIONS

        # Normalize keys/values to a case-insensitive lookup. Organization properties are read back through
        # a JSON-literal conversion that title-cases the substrings "true"/"false"/"null" (e.g. the value
        # "false_alarm" becomes "False_alarm"), so we compare case-insensitively to stay robust to that.
        normalized = {str(k).strip().lower(): str(v).strip().lower() for k, v in mapping.items()}

        classification = None

        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|_classify_deactivation() kind={} option_name={} fall_type={} mapping={}".format(
                kind, option_name, fall_type, normalized
            )
        )

        # Prefer the fall-type classification for fall alerts when the platform provides it.
        if event_types.is_fall_alert_kind(kind) and fall_type is not None:
            classification = CLASSIFICATION_REAL if fall_type > 0 else CLASSIFICATION_FALSE_ALARM

        if classification is None and option_name:
            classification = normalized.get(option_name.lower())

        if classification == CLASSIFICATION_FALSE_ALARM:
            return CLASSIFICATION_FALSE_ALARM
        if classification == CLASSIFICATION_REAL:
            return CLASSIFICATION_REAL
        return DEFAULT_INTREX_DEACTIVATION_CLASSIFICATION