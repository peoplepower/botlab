"""
Created on March 27, 2017

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""

import json

import localization
from controller import Controller
from startup import StartUpUtil
from utilities.utilities import Color, getsize, normalize_measurement


def run(botengine):
    """
    Entry point for bot microservices

    The bot boots up in this order:
        1. Create the `controller` object.

        2. Synchronize with our devices and create a location object and device objects

        3. new_version() - Executes one time when we're running a new version of the bot
            2.a. Microservices and filters are synchronized inside the location object
            2.a. Each device object, microservice, and filter should run its new_version() event

        4. initialize() - This event executes in every location / device object / microservice / filter on every trigger the bot

    :param botengine: BotEngine environment object, our window to the outside world.
    """
    localization.initialize(botengine)

    # ===========================================================================
    # botengine.get_logger().info("bot: inputs={}".format(json.dumps(botengine.get_inputs())))
    # ===========================================================================
    trigger_type = botengine.get_trigger_type()
    triggers = botengine.get_triggers()
    botengine.get_logger(f"{__name__}").info(">run() trigger_type=" + str(trigger_type))

    # RESET
    if trigger_type == botengine.TRIGGER_UNPAUSED:
        # This triggers on (a) the first execution of a bot, ever.
        # Or (b) when a bot was cryogenically frozen and is now thawed out and running again.
        # What happens on (b) is the bot used to be in the middle of doing something, and now as it
        # wakes up, it still thinks it is in the middle of that last situation it was tracking.
        # Even though it may be hours or days later. The bot has no idea where it is or what it should be doing now.
        # Since this affects potentially hundreds of microservices, the best bet right now is to blow the
        # bot's brains out and make it restart from scratch. Best practice is to store persistent memories
        # inside separate non-volatile variables or state variables that exist outside of this bot's 'controller' memory.
        # If you'd like to do something more elegant, please be my guest...
        botengine.get_logger(f"{__name__}").info(
            "|run() Unpaused. Deleting all internal memory."
        )
        botengine.destroy_core_memory()

    # Start up tool to cache the triggers when controller is not ready
    startup = load_startup_tool(botengine)

    if trigger_type & botengine.TRIGGER_DATA_REQUEST == 0:
        startup.queue_triggers((trigger_type, triggers))

    if startup.is_bot_preparing():
        # We are not allowed to save core state when DATA REQUEST get triggered, so lets ignore it.
        if trigger_type & botengine.TRIGGER_DATA_REQUEST == 0:
            if startup.is_something_wrong(botengine):
                startup.reset()

            botengine.save_variable(
                "startup_tool", startup, required_for_each_execution=True
            )
            # We need to flush immediately cause we may have multiple trigger inputs.
            botengine.flush_binary_variables()

        # Provide a little bit of time for the controller to get ready during playback.
        if botengine.playback:
            botengine.get_logger(f"{__name__}").warning(
                "<run() Controller is not ready..."
            )
            return

    # Grab our non-volatile memory
    botengine.get_logger(f"{__name__}").debug("|run() Loading Controller")
    controller = load_controller(botengine)
    botengine.get_logger(f"{__name__}").debug("|run() Controller Loaded")

    # When running locally, report the largest objects inside the controller
    # Only execute this once per local execution, similar to how new_version() is triggered
    if (
        hasattr(botengine, "local")
        and botengine.local
        and botengine.local_execution_count == 0
    ):
        try:
            sizes = []
            controller_dict = (
                vars(controller) if hasattr(controller, "__dict__") else {}
            )
            for attr_name, attr_value in controller_dict.items():
                try:
                    sizes.append(
                        (attr_name, type(attr_value).__name__, getsize(attr_value))
                    )
                except Exception:
                    # Best-effort sizing; skip problematic attributes
                    pass

            sizes.sort(key=lambda t: t[2], reverse=True)

            total_size = 0
            try:
                total_size = getsize(controller)
            except Exception:
                pass

            botengine.get_logger(f"{__name__}").info(
                f"{Color.BOLD}{Color.YELLOW}Controller deep size: {total_size / 1024 / 1024:.2f} MB{Color.END} — Top 50 attributes by size:"
            )

            for name, typename, size_bytes in sizes[:50]:
                botengine.get_logger(f"{__name__}").info(
                    f" {Color.CYAN}- {Color.BOLD}{name}{Color.END} ({typename}): {Color.GREEN}{size_bytes / 1024 / 1024:.2f} MB{Color.END} ({size_bytes:,} bytes)"
                )

            # Microservice deep sizes across all locations and devices.
            # Exclude shared graph roots (controller/locations/devices) to avoid identical sizes via back-references.
            micro_sizes = []
            try:
                excluded_ids = set()
                excluded_ids.add(id(controller))
                try:
                    excluded_ids.add(id(controller.locations))
                except Exception:
                    pass

                if getattr(controller, "locations", None):
                    for _loc_id, _loc_obj in controller.locations.items():
                        excluded_ids.add(id(_loc_obj))
                        try:
                            excluded_ids.add(id(_loc_obj.devices))
                        except Exception:
                            pass
                        if getattr(_loc_obj, "devices", None):
                            for _dev_id, _dev_obj in _loc_obj.devices.items():
                                excluded_ids.add(id(_dev_obj))

                def deep_size_excluding(obj, excluded):
                    import sys
                    from collections import deque
                    from numbers import Number

                    try:
                        from collections.abc import Mapping

                        zero_depth_bases = (str, bytes, Number, range, bytearray)
                        iteritems = "items"
                    except ImportError:
                        from collections import Mapping

                        zero_depth_bases = (basestring, Number, xrange, bytearray)  # noqa: F821 # type: ignore
                        iteritems = "iteritems"

                    seen = set()

                    def inner(o):
                        oid = id(o)
                        if oid in seen or oid in excluded:
                            return 0
                        seen.add(oid)
                        size_ = 0
                        try:
                            size_ = sys.getsizeof(o)
                        except Exception:
                            pass
                        if isinstance(o, zero_depth_bases):
                            return size_
                        if isinstance(o, (tuple, list, set, deque)):
                            return size_ + sum(inner(i) for i in o)
                        if isinstance(o, Mapping) or hasattr(o, iteritems):
                            try:
                                it = getattr(o, iteritems)()
                            except Exception:
                                it = []
                            return size_ + sum(inner(k) + inner(v) for k, v in it)
                        if hasattr(o, "__dict__"):
                            size_ += inner(vars(o))
                        if hasattr(o, "__slots__"):
                            try:
                                size_ += sum(
                                    inner(getattr(o, s))
                                    for s in o.__slots__
                                    if hasattr(o, s)
                                )
                            except Exception:
                                pass
                        return size_

                    return inner(obj)

                for location_id, location_obj in (controller.locations or {}).items():
                    # Location-level intelligence modules
                    if hasattr(location_obj, "intelligence_modules") and isinstance(
                        location_obj.intelligence_modules, dict
                    ):
                        for ms_key, ms_obj in location_obj.intelligence_modules.items():
                            try:
                                size_bytes = deep_size_excluding(ms_obj, excluded_ids)
                                micro_sizes.append(
                                    (size_bytes, "location", None, None, ms_key)
                                )
                            except Exception:
                                pass

                    # Device-level intelligence modules
                    if hasattr(location_obj, "devices") and isinstance(
                        location_obj.devices, dict
                    ):
                        for device_id, device_obj in location_obj.devices.items():
                            if hasattr(
                                device_obj, "intelligence_modules"
                            ) and isinstance(device_obj.intelligence_modules, dict):
                                for (
                                    ms_key,
                                    ms_obj,
                                ) in device_obj.intelligence_modules.items():
                                    try:
                                        size_bytes = deep_size_excluding(
                                            ms_obj, excluded_ids
                                        )
                                        micro_sizes.append(
                                            (
                                                size_bytes,
                                                "device",
                                                None,
                                                device_id,
                                                ms_key,
                                            )
                                        )
                                    except Exception:
                                        pass
            except Exception:
                pass

            if micro_sizes:
                micro_sizes.sort(key=lambda t: t[0], reverse=True)
                botengine.get_logger(f"{__name__}").info(
                    f"{Color.BOLD}{Color.YELLOW}Top 50 microservices by deep size:{Color.END}"
                )
                for size_bytes, scope, loc_id, dev_id, ms_key in micro_sizes[:50]:
                    # Show device id if present; omit location scope entirely
                    scope_suffix = f" [device={dev_id}]" if dev_id is not None else ""
                    botengine.get_logger(f"{__name__}").info(
                        f" {Color.CYAN}- {Color.BOLD}{ms_key}{Color.END}{scope_suffix}: {Color.GREEN}({size_bytes:,} bytes){Color.END}"
                    )
        except Exception as e:
            botengine.get_logger(f"{__name__}").warning(
                f"Local controller size report failed: {e}"
            )

    # The controller stores the bot's last version number.
    # If this is a new bot version, this evaluation will automatically trigger the new_version() event in all microservices.
    # Note that the new_version() event is also a bot trigger.
    if controller.is_version_updated(botengine):
        # We are not allowed to save core state when DATA REQUEST get triggered, so lets ignore it.
        if trigger_type & botengine.TRIGGER_DATA_REQUEST != 0:
            return

        startup.start(botengine.get_timestamp())
        botengine.save_variable(
            "startup_tool", startup, required_for_each_execution=True
        )
        botengine.flush_binary_variables()

        controller.update_version(botengine)

    # INITIALIZE
    controller.initialize(botengine)

    botengine.get_logger(f"{__name__}").debug("|run() Controller is ready now...")
    if trigger_type & botengine.TRIGGER_DATA_REQUEST == 0:
        while len(startup.event_queue) > 0:
            (queue_trigger_type, queue_triggers) = startup.event_queue.pop(0)
            trigger_event(botengine, controller, queue_trigger_type, queue_triggers)

        # Always save your variables!
        botengine.save_variable(
            "controller", controller, required_for_each_execution=True
        )
        startup.reset()
        botengine.save_variable(
            "startup_tool", startup, required_for_each_execution=True
        )

    else:
        # DATA REQUEST
        trigger_event(botengine, controller, trigger_type, triggers)
    botengine.get_logger(f"{__name__}").info("<run()")


def load_controller(botengine):
    """
    Load the Controller object
    :param botengine: Execution environment
    """
    botengine.get_logger(f"{__name__}").debug(">load_controller()")
    try:
        controller = botengine.load_variable("controller")
    except Exception as e:
        controller = None
        botengine.get_logger(f"{__name__}").warning(
            "|load_controller() Unable to load the controller: {}".format(str(e))
        )

    if controller is None:
        botengine.get_logger(f"{__name__}").info(
            "|load_controller() Creating a new Controller object. Hello."
        )
        controller = Controller()
        botengine.save_variable(
            "controller", controller, required_for_each_execution=True
        )

    botengine.get_logger(f"{__name__}").debug("|load_controller() track organizations")
    controller.track_new_and_deleted_organizations(botengine)

    botengine.get_logger(f"{__name__}").debug("<load_controller()")
    return controller


def load_startup_tool(botengine):
    """
    Load the Controller object
    :param botengine: Execution environment
    """
    botengine.get_logger(f"{__name__}").debug(">load_startup_tool()")
    try:
        startup = botengine.load_variable("startup_tool")

    except Exception:
        startup = None
        botengine.get_logger(f"{__name__}").debug(
            "|load_startup_tool() Unable to load the startup tool"
        )

    if startup is None:
        botengine.get_logger(f"{__name__}").info(
            "|load_startup_tool() Creating a new startup tool object."
        )
        startup = StartUpUtil()
    botengine.get_logger(f"{__name__}").debug("<load_startup_tool()")
    return startup


def get_intelligence_statistics(botengine):
    """
    Get the microservice statistics
    :param botengine: BotEngine environment
    :return: Microservice statistics
    """
    controller = load_controller(botengine)
    return controller.get_intelligence_statistics(botengine)


def trigger_event(botengine, controller, trigger_type, triggers):
    botengine.get_logger(f"{__name__}").info(
        ">trigger_event() trigger_type={}".format(trigger_type)
    )
    # SCHEDULE TRIGGER
    if trigger_type & botengine.TRIGGER_SCHEDULE != 0:
        botengine.get_logger(f"{__name__}").info("|trigger_event() Schedule triggered")
        schedule_ids = ["DEFAULT"]
        if "scheduleIds" in botengine.get_inputs():
            schedule_ids = botengine.get_inputs()["scheduleIds"]
            botengine.get_logger(f"{__name__}").info(
                "|trigger_event() schedule_ids={}".format(schedule_ids)
            )

        for schedule_id in schedule_ids:
            controller.run_intelligence_schedules(botengine, schedule_id)

    # MODE TRIGGERS - Not supported

    # MEASUREMENT TRIGGERS - Not supported

    # DEVICE ALERTS - Not supported

    # FILE UPLOAD TRIGGERS - Not supported

    # TIMER FIRED
    if trigger_type & botengine.TRIGGER_TIMER != 0:
        botengine.get_logger(f"{__name__}").info("|trigger_event() Timer triggered")
        MAXINT = 9223372036854775807
        TIMERS_VARIABLE_NAME = "[t]"
        TIMER_MIN_MS = 10000
        timer = botengine.inputs["time"]

        saved_timers = botengine.load_variable(TIMERS_VARIABLE_NAME)

        if saved_timers:
            execution_time = botengine.get_timestamp()
            min_countdown_threshold = botengine.get_system_property(
                "ppc.bot.minCountdownThreshold"
            )
            botengine.get_logger(f"{'botengine'}").debug(
                "|trigger_Event() min_countdown_threshold={}".format(
                    min_countdown_threshold
                )
            )

            # Summarize timer stack in a single line

            system_time = botengine.get_system_time_ms()
            next_timer_ms = saved_timers[0][0] if saved_timers else None
            next_timer_delta = (next_timer_ms - system_time) if next_timer_ms else None
            botengine.get_logger(f"{__name__}").info(
                "|trigger_event() "
                + Color.PURPLE
                + f"Checking {len(saved_timers)} timer(s); next fires in {next_timer_delta}ms"
                + Color.END
            )

            # Double check our timers first, before giving up and letting the bot engine execute trigger type 64.
            while True:
                saved_timers = botengine.load_variable(TIMERS_VARIABLE_NAME)
                if saved_timers is None:
                    botengine.get_logger(f"{__name__}").warning(
                        "|trigger_event() "
                        + Color.YELLOW
                        + "No timers variable found."
                        + Color.END
                    )
                    break
                if len(saved_timers) == 0:
                    break
                focused_timer = saved_timers[0]
                t = focused_timer[0]
                botengine.get_logger(f"{__name__}").debug(
                    "|trigger_event() Checking timer at time {}".format(t)
                )
                if t == MAXINT:
                    botengine.get_logger(f"{__name__}").warning(
                        "|trigger_event() "
                        + Color.YELLOW
                        + "No timers available for execution."
                        + Color.END
                    )
                    break
                system_time = botengine.get_system_time_ms()
                try:
                    time_variance = int(min_countdown_threshold or TIMER_MIN_MS)
                except Exception:
                    time_variance = TIMER_MIN_MS
                if t - time_variance > system_time or t - time_variance > timer:
                    botengine.get_logger(f"{__name__}").debug(
                        "|trigger_event() Next timer not ready for execution yet."
                    )
                    break
                # Pop the timer and execute it
                focused_timer = saved_timers.pop(0)
                botengine.save_variable(
                    TIMERS_VARIABLE_NAME, saved_timers, overwrite=True
                )
                botengine.get_logger(f"{__name__}").info(
                    "|trigger_event() "
                    + Color.PURPLE
                    + "Executing timer. t{} timer={}".format(
                        system_time - t, focused_timer
                    )
                    + Color.END
                )
                if callable(focused_timer[1]):
                    # Execute the timer function relative to the timer's timestamp
                    botengine.set_timestamp(focused_timer[0])
                    focused_timer[1](botengine, focused_timer[2])
                    botengine.get_logger(f"{__name__}").info(
                        "|trigger_event() Finished executing timer: "
                        + str(focused_timer)
                    )
                    botengine.set_timestamp(execution_time)
                else:
                    botengine.get_logger(f"{__name__}").error(
                        "|trigger_event() Timer fired and popped, but cannot call the focused timer: "
                        + str(focused_timer)
                    )
        pass

    # QUESTIONS ANSWERED
    if trigger_type & botengine.TRIGGER_QUESTION_ANSWER != 0:
        botengine.get_logger(f"{__name__}").info("|trigger_event() Question triggered")
        question = botengine.get_answered_question()
        if question is None:
            botengine.get_logger(f"{__name__}").error(
                "|trigger_event() Triggered off a question answer, but no question was answered. triggers={}".format(
                    json.dumps(triggers)
                )
            )
        else:
            botengine.get_logger(f"{__name__}").info(
                "|trigger_event() question.key_identifier="
                + str(question.key_identifier)
            )
            botengine.get_logger(f"{__name__}").info(
                "|trigger_event() question.answer={}".format(question.answer)
            )
            controller.sync_question(botengine, question)

    # DATA STREAM TRIGGERS
    if trigger_type & botengine.TRIGGER_DATA_STREAM != 0:
        # Triggered off a data stream message
        data_stream = botengine.get_datastream_block() or {}
        botengine.get_logger(f"{__name__}").info(
            "|trigger_event() data_stream=" + json.dumps(data_stream, sort_keys=True)
        )
        if "address" not in data_stream:
            botengine.get_logger(f"{__name__}").warn(
                "|trigger_event() Data stream message does not contain an 'address' field. Ignoring the message."
            )

        else:
            address = data_stream["address"]

            if "feed" in data_stream:
                content = data_stream["feed"]
            else:
                content = {}

            if "fromAppInstanceId" in data_stream:
                if isinstance(content, dict):
                    content["sender_bot_id"] = data_stream["fromAppInstanceId"]

            # Add the key to the content (if it exists) so we can pass it along to the microservice
            if botengine.get_input_key():
                content["key"] = botengine.get_input_key()

            if address != "schedule":
                controller.sync_datastreams(botengine, address, content)
            else:
                controller.run_intelligence_schedules(botengine)

    # COMMAND RESPONSES - Not supported

    # GOAL / SCENARIO CHANGES - Not supported

    # LOCATION CONFIGURATION CHANGES - Not supported

    # DATA REQUEST
    if trigger_type & botengine.TRIGGER_DATA_REQUEST != 0:
        botengine.get_logger(f"{__name__}").info(
            "|trigger_event() Data request received"
        )
        events = {}
        data = botengine.get_data_block()
        botengine.get_logger(f"{__name__}").debug(
            "|trigger_event() data={}".format(data)
        )

        if botengine.playback:
            for d in data:
                reference = None
                if "key" in d:
                    reference = d["key"]

                if reference not in events:
                    events[reference] = {}
                botengine.get_logger(f"{__name__}").info(
                    "|trigger_event() Inserting from playback {} ({} bytes)...".format(
                        d["deviceId"], d["dataLength"]
                    )
                )
                events[reference][d["deviceId"]] = d["data"]

            data_events = {}

            for reference, value in events.items():
                if reference not in data_events:
                    data_events[reference] = {}

                for device_id, decompressed_content in value.items():
                    data_events[reference][
                        controller.get_device(botengine, device_id)
                    ] = decompressed_content

            for reference in data_events:
                controller.async_data_request_ready(
                    botengine, reference, data_events[reference]
                )

        else:
            imported = False

            try:
                import lz4.block  # type: ignore

                imported = True
            except ImportError:
                botengine.get_logger(f"{__name__}").error(
                    "|trigger_event() Attempted to import 'lz4' to uncompress the data request response, but lz4 is not available. Please add 'lz4' to 'pip_install_remotely' in your structure.json."
                )
                pass

        if imported:
            for d in data:
                reference = None
                if 'key' in d:
                    reference = d['key']

                if reference not in events:
                    events[reference] = {}

                botengine.get_logger(f"{__name__}").info("|run() Downloading {} bytes...".format(d['compressedLength']))
                r = botengine._requests.get(d['url'], timeout=60, stream=True)
                data = lz4.block.decompress(r.content, uncompressed_size=d['dataLength'])

                if d['type'] == botengine.DATA_REQUEST_TYPE_LOCATIONS:
                    import csv
                    import io
                    csv_file_like_object = io.StringIO(data.decode('utf-8'))
                    reader = csv.DictReader(csv_file_like_object)

                    # formated[location_id] = { ... }
                    formatted = {}

                    for line in reader:
                        for key in line:
                            line[key] = normalize_measurement(line[key])
                        location_id = line["id"]
                        del line["id"]
                        formatted[location_id] = line

                    events[reference] = formatted

                elif d['type'] == botengine.DATA_REQUEST_TYPE_DEVICES:
                    import csv
                    import io
                    csv_file_like_object = io.StringIO(data.decode('utf-8'))
                    reader = csv.DictReader(csv_file_like_object)

                    # formated[location_id][device_id] = { ... }
                    formatted = {}

                    for line in reader:
                        for key in line:
                            line[key] = normalize_measurement(line[key])

                        # CSV columns: locationId, deviceId, deviceType, etc.
                        location_id = line.pop("locationId", line.pop("id", None))
                        device_id = line.pop("deviceId", line.pop("device_id", None))

                        if location_id is not None and device_id is not None:
                            if location_id not in formatted:
                                formatted[location_id] = {}
                            formatted[location_id][device_id] = line

                    events[reference] = formatted

                elif d['type'] == botengine.DATA_REQUEST_TYPE_LOCATION_TIME_STATES:
                    import csv
                    import io
                    csv_file_like_object = io.StringIO(data.decode('utf-8'))
                    reader = csv.DictReader(csv_file_like_object)

                    # formated[location_id][state_name][state_time] = { ... }
                    formatted = {}

                    for line in reader:
                        for key in line:
                            if key == "value":
                                continue
                            line[key] = normalize_measurement(line[key])
                        location_id = line["locationId"]
                        state_name = line["name"]
                        state_time = line["stateTime"]
                        try:
                            state_value = json.loads(line["value"])
                        except Exception as e:
                            import traceback
                            botengine.get_logger(f"{__name__}").warning(
                                "|trigger_event() Failed to parse value as JSON for location time state. error={}; trace={}".format(e, traceback.format_exc())
                            )
                            state_value = line["value"]
                        if location_id not in formatted:
                            formatted[location_id] = {}
                        if state_name not in formatted[location_id]:
                            formatted[location_id][state_name] = {}
                        formatted[location_id][state_name][state_time] = state_value

                    events[reference] = formatted

                else:
                    import csv
                    import io
                    csv_file_like_object = io.StringIO(data.decode('utf-8'))
                    reader = csv.DictReader(csv_file_like_object)

                    formatted = []

                    for line in reader:
                        for key in line:
                            line[key] = normalize_measurement(line[key])
                        formatted = line

                    events[reference] = {"data": formatted}

            for reference in events:
                controller.async_data_request_ready(botengine, reference, events[reference])

            # if imported:
            #     for d in data:
            #         reference = None
            #         if "key" in d:
            #             reference = d["key"]

            #         if reference not in events:
            #             events[reference] = {}

            #         botengine.get_logger(f"{__name__}").info(
            #             "|trigger_event() Downloading {} ({} bytes)...".format(
            #                 d["deviceId"], d["dataLength"]
            #             )
            #         )
            #         r = botengine.send_data_request(d["url"], timeout=60, stream=True)
            #         events[reference][d["deviceId"]] = lz4.block.decompress(
            #             r.content, uncompressed_size=d["dataLength"]
            #         )

            #     data_events = {}

            #     for reference, value in events.items():
            #         if reference not in data_events:
            #             data_events[reference] = {}

            #         for device_id, decompressed_content in value.items():
            #             data_events[reference][
            #                 controller.get_device(botengine, device_id)
            #             ] = decompressed_content

            #     for reference in data_events:
            #         controller.async_data_request_ready(
            #             botengine, reference, data_events[reference]
            #         )

    # MESSAGES - Not supported

    # DOCUMENTS
    if (
        botengine.get_bot_type() == botengine.BOT_TYPE_ORGANIZATION_RAG
        and trigger_type in [botengine.TRIGGER_UNPAUSED, botengine.TRIGGER_DOCUMENTS]
    ):
        # if trigger_type & botengine.TRIGGER_DOCUMENTS != 0:
        request_id = botengine.get_documents_request_id()
        document = botengine.get_document_block()
        controller.sync_documents(botengine, document, request_id)

    botengine.get_logger(f"{__name__}").info("<trigger_event()")


# ===============================================================================
# Organization Intelligence Timers
# ===============================================================================
def _organization_intelligence_fired(botengine, argument_tuple):
    """
    Entry point into this bot
    Organization intelligence timer or alarm fired
    :param botengine: BotEngine Environment
    :param argument_tuple: (intelligence_id, argument)
    """
    botengine.get_logger(f"{__name__}").info(">_organization_intelligence_fired()")
    controller = load_controller(botengine)

    try:
        controller.run_organization_intelligence(
            botengine, argument_tuple[0], argument_tuple[1]
        )
    except Exception as e:
        import traceback

        botengine.get_logger(f"{__name__}").error(
            "|_organization_intelligence_fired() {}; {}".format(
                str(e), traceback.format_exc()
            )
        )

    botengine.save_variable("controller", controller, required_for_each_execution=True)
    botengine.get_logger(f"{__name__}").info("<_organization_intelligence_fired()")


def start_organization_intelligence_timer(
    botengine, seconds, intelligence_id, argument, reference
):
    """
    Start a relative organization intelligence timer
    :param botengine: BotEngine environment
    :param seconds: Seconds from the start of the current execution to make this timer fire
    :param intelligence_id: ID of the intelligence module to trigger when this timer fires
    :param argument: Arbitrary argument to pass into the intelligence module's timer_fired() method when this timer fires
    :param reference: Unique reference name that lets us later cancel this timer if needed
    """
    botengine.get_logger(f"{__name__}").info(">start_organization_intelligence_timer()")
    botengine.get_logger(f"{__name__}").info(
        "|start_organization_intelligence_timer() seconds={} reference={}".format(
            seconds, reference
        )
    )
    if reference is not None and reference != "":
        botengine.cancel_timers(reference)
    botengine.start_timer_s(
        int(seconds),
        _organization_intelligence_fired,
        (intelligence_id, argument),
        reference,
    )
    botengine.get_logger(f"{__name__}").info("<start_organization_intelligence_timer()")


def start_organization_intelligence_timer_ms(
    botengine, milliseconds, intelligence_id, argument, reference
):
    """
    Start a relative organization intelligence timer
    :param botengine: BotEngine environment
    :param milliseconds: Milliseconds from the start of the current execution to make this timer fire
    :param intelligence_id: ID of the intelligence module to trigger when this timer fires
    :param argument: Arbitrary argument to pass into the intelligence module's timer_fired() method when this timer fires
    :param reference: Unique reference name that lets us later cancel this timer if needed
    """
    botengine.get_logger(f"{__name__}").info(
        ">start_organization_intelligence_timer_ms()"
    )
    botengine.get_logger(f"{__name__}").info(
        "|start_organization_intelligence_timer_ms() milliseconds={} reference={}".format(
            milliseconds, reference
        )
    )
    if reference is not None and reference != "":
        botengine.cancel_timers(reference)
    botengine.start_timer_ms(
        int(milliseconds),
        _organization_intelligence_fired,
        (intelligence_id, argument),
        reference,
    )
    botengine.get_logger(f"{__name__}").info(
        "<start_organization_intelligence_timer_ms()"
    )


def set_organization_intelligence_alarm(
    botengine, timestamp_ms, intelligence_id, argument, reference
):
    """
    Set an absolute organization intelligence alarm
    :param botengine: BotEngine environment
    :param timestamp: Absolute timestamp in milliseconds at which to trigger this alarm
    :param intelligence_id: ID of the intelligence module to trigger when this alarm fires
    :param argument: Arbitrary argument to pass into the intelligence module's timer_fired() method when this timer fires
    :param reference: Unique reference name that lets us later cancel this timer if needed
    """
    botengine.get_logger(f"{__name__}").info(">set_organization_intelligence_alarm()")
    botengine.get_logger(f"{__name__}").info(
        "|set_organization_intelligence_alarm() timestamp_ms={} reference={}".format(
            timestamp_ms, reference
        )
    )
    if reference is not None and reference != "":
        botengine.cancel_timers(reference)
    botengine.set_alarm(
        int(timestamp_ms),
        _organization_intelligence_fired,
        (intelligence_id, argument),
        reference,
    )
    botengine.get_logger(f"{__name__}").info("|set_organization_intelligence_alarm()")


def cancel_organization_intelligence_timers(botengine, reference):
    """
    Cancel all organization intelligence timers and alarms with the given reference
    :param botengine: BotEngine environment
    :param reference: Unique reference name for which to cancel all timers and alarms
    """
    botengine.cancel_timers(reference)


def is_organization_timer_running(botengine, reference):
    """
    Determine if the timer with the given reference is running
    :param botengine: BotEngine environment
    :param reference: Unique reference name for the timer
    :return: True if the timer is running
    """
    return botengine.is_timer_running(reference)


# ===========================================================================
# Documents
# ===========================================================================
def get_document_property_updates(botengine):
    """
    Get the document updates provided by any specific microservice

    Example:
    {
      "documentId": 0,
      "properties": [
        {
          "name": "some",
          "value": "thing" # If empty remove this property
        }
      ]
    }

    :param botengine: BotEngine environment
    :return: Document

    """
    botengine.get_logger(f"{__name__}").debug(">get_documents_property_update()")
    controller = load_controller(botengine)

    document = {}

    # Extract document property updates from all intelligence_modules
    for organization in controller.organizations.values():
        for intelligence_module in organization.intelligence_modules.keys():
            document_property_updates = organization.intelligence_modules[
                intelligence_module
            ].get_document_property_updates(botengine)

            botengine.get_logger(f"{__name__}").debug(
                "|get_document_property_updates() intelligence_module: {} - {}".format(
                    intelligence_module, document_property_updates
                )
            )

            _append_document_property_updates(
                botengine, document, document_property_updates
            )

    botengine.get_logger(f"{__name__}").info(
        "|get_document_property_updates() Document: {}".format(document)
    )
    botengine.get_logger(f"{__name__}").debug("<get_document_property_updates()")
    return document


def get_documents_questions(botengine):
    """
    Get the document questions provided by any specific microservice

    Example:
    [
      {
        "documentId": 0,
        "questions": [
          "What is this?"
        ],
        "questionKeys": [
          "summary"
        ]
      }
    ]

    :param botengine: BotEngine environment
    :return: List of documents

    """
    botengine.get_logger(f"{__name__}").debug(">get_documents_questions()")
    controller = load_controller(botengine)

    documents = []

    # Extract document questions from all intelligence_modules
    for organization in controller.organizations.values():
        for intelligence_module in organization.intelligence_modules.keys():
            documents_questions = organization.intelligence_modules[
                intelligence_module
            ].get_documents_questions(botengine)

            botengine.get_logger(f"{__name__}").debug(
                "|get_documents_questions() intelligence_module: {} - {}".format(
                    intelligence_module, documents_questions
                )
            )

            _append_documents_questions(botengine, documents, documents_questions)

    botengine.get_logger(f"{__name__}").info(
        "|get_documents_questions() Documents: {}".format(documents)
    )
    botengine.get_logger(f"{__name__}").debug("<get_documents_questions()")
    return documents


def _append_document_property_updates(botengine, document, document_property_updates):
    """
    Append document property updates to the existing document updates
    :param botengine: BotEngine environment
    :param document: Existing document updates
    :param document_property_updates: New document updates
    """
    botengine.get_logger(f"{__name__}").info(">_append_document_property_updates()")
    botengine.get_logger(f"{__name__}").info(
        "|_append_document_property_updates() document={}".format(document)
    )
    botengine.get_logger(f"{__name__}").info(
        "|_append_document_property_updates() document_property_updates={}".format(
            document_property_updates
        )
    )
    if "documentId" in document_property_updates:
        if document == {}:
            document["documentId"] = document_property_updates["documentId"]
            document["properties"] = document_property_updates.get("properties", [])
            botengine.get_logger(f"{__name__}").info(
                "|_append_document_property_updates() First update"
            )
        else:
            botengine.get_logger(f"{__name__}").info(
                "|_append_document_property_updates() Combine updates"
            )
            document["properties"].extend(
                document_property_updates.get("properties", [])
            )

    botengine.get_logger(f"{__name__}").info(
        "<_append_document_property_updates() document={}".format(document)
    )


def _append_documents_questions(botengine, documents, documents_questions):
    """
    Append document questions to the existing document updates
    :param botengine: BotEngine environment
    :param documents: Existing document updates
    :param documents_questions: New document updates
    """
    botengine.get_logger(f"{__name__}").debug(">_append_documents_questions()")
    for document_question in documents_questions:
        if "output_schema" in document_question:
            document_question["outputSchema"] = document_question["output_schema"]
            del document_question["output_schema"]
    if len(documents) == 0:
        botengine.get_logger(f"{__name__}").debug(
            "|_append_documents_questions() First update"
        )
        documents.extend(documents_questions)
    else:
        botengine.get_logger(f"{__name__}").debug(
            "|_append_documents_questions() Combine updates"
        )
        for document_question in documents_questions:
            new_updates = any(
                [
                    existing_updates
                    for existing_updates in documents
                    if existing_updates["documentId"] != document_question["documentId"]
                ]
            )
            if new_updates:
                botengine.get_logger(f"{__name__}").debug(
                    "|_append_documents_questions() New document updates"
                )
                documents.append(document_question)
            else:
                botengine.get_logger(f"{__name__}").debug(
                    "|_append_documents_questions() Existing document updates"
                )
                existing_document_questions = [
                    existing_updates
                    for existing_updates in documents
                    if existing_updates["documentId"] == document_question["documentId"]
                ][0]
                for question in existing_document_questions["questions"]:
                    if any(
                        [
                            question == document_question
                            for document_question in document_question["questions"]
                        ]
                    ):
                        break
                    else:
                        existing_document_questions["questions"].extend(
                            [
                                document_question
                                for document_question in document_question["questions"]
                            ]
                        )
                for question_key in existing_document_questions.get("questionKeys", []):
                    if any(
                        [
                            question_key == document_question
                            for document_question in document_question.get(
                                "questionKeys", []
                            )
                        ]
                    ):
                        break
                    else:
                        existing_document_questions["questionKeys"].extend(
                            [
                                document_question
                                for document_question in document_question.get(
                                    "questionKeys", []
                                )
                            ]
                        )

    botengine.get_logger(f"{__name__}").debug(
        "<_append_documents_questions() documents={}".format(documents)
    )
