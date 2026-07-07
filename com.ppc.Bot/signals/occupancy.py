"""
Created on August 20, 2020

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

Implement this method in your microsevices to receive occupancy_status_updated signals:

    def occupancy_status_updated(self, botengine, status, reason, last_status, last_reason):
        '''
        AI Occupancy Status updated
        :param botengine: BotEngine
        :param status: Current occupancy status
        :param reason: Current occupancy reason
        :param last_status: Last occupancy status
        :param last_reason: Last occupancy reason
        '''
        return


Implement this method in your microsevices to receive occupancy wakeup_time_predicted signals:

    def wakeup_time_predicted(self, botengine, content):
        '''
        AI Occupancy Status updated
        :param botengine: BotEngine
        :param content: content['wakeup_time'] : Predicted occupancy wakeup time
        '''
        return


Implement these methods in your microservices to receive specific occupancy transition signals:

    def occupancy_status_may_go_away(self, botengine):
        '''
        Occupant(s) may be leaving soon (H2A transition state)
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_did_go_away(self, botengine):
        '''
        Occupant(s) left and location is now ABSENT
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_did_go_vacation(self, botengine):
        '''
        Location entered VACATION status (extended absence)
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_may_come_home(self, botengine):
        '''
        Occupant(s) expected to arrive home soon (A2H transition state)
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_did_come_home(self, botengine):
        '''
        Occupant(s) arrived home and location is now PRESENT
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_will_sleep(self, botengine):
        '''
        Occupant(s) expected to go to sleep soon (H2S transition state)
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_did_sleep(self, botengine):
        '''
        Occupant(s) went to sleep and location is now in SLEEP status
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_will_wake(self, botengine):
        '''
        Occupant(s) expected to wake up soon (S2H transition state)
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_did_wake(self, botengine):
        '''
        Occupant(s) woke up and location is now PRESENT
        :param botengine: BotEngine
        '''
        return

    def occupancy_status_did_timeout_wake(self, botengine):
        '''
        Sleep flow "gave up" and forced a transition to PRESENT due to timeout.

        This signal fires when the sleep flow state machine times out waiting for
        evidence of wakeup (motion, bathroom activity, out of bed, etc.) and forces
        a transition to PRESENT to get on with the day.

        This is distinct from occupancy_status_did_wake which fires for ALL wakeups.
        Use this signal to:
        - Skip generating reports that would be based on hallucinated data
        - Suppress morning inactivity alerts (no one is actually inactive)
        - Log analytics about potential issues (devices offline, person away, etc.)
        - Avoid sending misleading communications to family

        :param botengine: BotEngine
        '''
        return

    def occupancy_status_did_wake_from_nap(self, botengine):
        '''
        Occupant(s) woke up from a nap and location is now PRESENT
        :param botengine: BotEngine
        '''
        return

@author: David Moss
"""
# TODO: Refactor to use datastream message structure instead of individual methods for each signal

import utilities.utilities as utilities

def switching_occupancy_status(botengine, location_object, status, reason, last_status, last_reason):
    """
    Preparing to switch occupancy status

    Situation is the update_occupancy_status() goes out to the entire microservice ecosystem,
    and there's no way to control the order of execution. We have some cosmetic situations
    where the dashboard is updated with redundant information that we should exclude, like
    the location_occupancy_narrative_microservice.py declaring "Appears to be asleep since.." with an 'occupancy' 
    dashboard ID, and the location_sleep_quantification_microservice.py 
    declaring "Went to bed around.." with a 'sleep' dashboard ID.

    :param botengine: BotEngine environment
    :param location_object: Location Object
    :param status: New status
    :param reason: New reason
    :param last_status: Last status
    :param last_reason: Last reason
    :return:
    """
    location_object.distribute_datastream_message(botengine, "switching_occupancy_status", content={"status": status, "reason": reason, "last_status": last_status, "last_reason": last_reason}, internal=True, external=False)

def update_occupancy_status(botengine, location_object, status, reason, last_status, last_reason):
    """
    Distribute the newest occupancy status from AI occupancy algorithms
    :param botengine: BotEngine environment
    :param location_object: Location Object
    :param status: Current status
    :param reason: Current reason
    :param last_status: Last status
    :param last_reason: Last reason
    :return:
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_updated'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_updated(botengine, status, reason, last_status, last_reason)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("location.py - Error delivering occupancy_status_updated to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_updated'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_updated(botengine, status, reason, last_status, last_reason)
                    except Exception as e:
                        botengine.get_logger().warning("location.py - Error delivering occupancy_status_updated message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)



def update_wake_time(botengine, location_object, expected_wake_time_ms):
    """
    Distribute the new predicted wake up time for the next morning after occupant goes to sleep
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param expected_wake_time_ms: Absolute timestamp of when occupant is expected to wake up
    """
    location_object.distribute_datastream_message(botengine, 'wakeup_time_predicted', content={"wakeup_time_ms": expected_wake_time_ms}, internal=True, external=False)


def reset_sleep(botengine, location_object):
    """
    Reset sleep learnings
    :param botengine: BotEngine environment
    :param location_object: Location object
    """
    location_object.distribute_datastream_message(botengine, "reset_sleep", None, internal=True, external=False)


def reset_absent(botengine, location_object):
    """
    Reset absence detection
    :param botengine: BotEngine environment
    :param location_object: Location object
    """
    location_object.distribute_datastream_message(botengine, "reset_absent", None, internal=True, external=False)


def occupancy_status_may_go_away(botengine, location_object):
    """
    Distribute notification that occupant(s) may be leaving soon (H2A transition state)
    
    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_may_go_away'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_may_go_away(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_may_go_away to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_may_go_away'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_may_go_away(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_may_go_away message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_did_go_away(botengine, location_object):
    """
    Distribute notification that occupant(s) left and location is now ABSENT
    
    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_did_go_away'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_did_go_away(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_go_away to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_did_go_away'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_did_go_away(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_go_away message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_did_go_vacation(botengine, location_object):
    """
    Distribute notification that occupant(s) are on vacation (extended absence)
    
    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_did_go_vacation'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_did_go_vacation(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_go_vacation to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_did_go_vacation'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_did_go_vacation(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_go_vacation message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_may_come_home(botengine, location_object):
    """
    Distribute notification that occupant(s) are expected to arrive home soon (A2H transition state)
    
    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_may_come_home'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_may_come_home(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_may_come_home to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_may_come_home'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_may_come_home(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_may_come_home message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_did_come_home(botengine, location_object):
    """
    Distribute notification that occupant(s) arrived home and location is now PRESENT
    
    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_did_come_home'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_did_come_home(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_come_home to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_did_come_home'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_did_come_home(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_come_home message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_will_sleep(botengine, location_object):
    """
    Distribute notification that occupant(s) are expected to go to sleep soon (H2S transition state)
    
    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_will_sleep'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_will_sleep(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_will_sleep to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_will_sleep'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_will_sleep(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_will_sleep message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_did_sleep(botengine, location_object):
    """
    Distribute notification that occupant(s) went to sleep and location is now in SLEEP status
    
    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_did_sleep'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_did_sleep(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_sleep to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_did_sleep'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_did_sleep(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_sleep message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_will_wake(botengine, location_object):
    """
    Distribute notification that occupant(s) are expected to wake up soon (S2H transition state)
    
    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_will_wake'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_will_wake(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_will_wake to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_will_wake'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_will_wake(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_will_wake message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_did_wake(botengine, location_object):
    """
    Distribute notification that occupant(s) woke up and location is now PRESENT

    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_did_wake'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_did_wake(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_wake to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_did_wake'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_did_wake(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_wake message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def occupancy_status_did_timeout_wake(botengine, location_object):
    """
    Distribute notification that sleep flow "gave up" and forced transition to PRESENT.

    This signal fires when the sleep flow state machine times out waiting for evidence
    of wakeup (motion, bathroom activity, out of bed, etc.) and forces a transition to
    PRESENT to get on with the day.

    Use this signal to:
    - Skip generating reports that would be based on hallucinated data
    - Suppress morning inactivity alerts (no one is actually inactive)
    - Log analytics about potential issues (devices offline, person away, etc.)
    - Avoid sending misleading communications to family

    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_did_timeout_wake'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_did_timeout_wake(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_timeout_wake to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_did_timeout_wake'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_did_timeout_wake(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_timeout_wake message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)

def occupancy_status_did_wake_from_nap(botengine, location_object):
    """
    Distribute notification that occupant(s) woke up from NAP and location is now PRESENT

    :param botengine: BotEngine environment
    :param location_object: Location Object
    """
    # Location microservices
    for microservice in location_object.intelligence_modules:
        if hasattr(location_object.intelligence_modules[microservice], 'occupancy_status_did_wake_from_nap'):
            try:
                import time
                t = time.time()
                location_object.intelligence_modules[microservice].occupancy_status_did_wake_from_nap(botengine)
                location_object.intelligence_modules[microservice].track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_wake_from_nap to location microservice (continuing execution): " + str(e))
                import traceback
                botengine.get_logger().error(traceback.format_exc())
                utilities.pause_playback(botengine)

    # Device microservices
    for device_id in location_object.devices:
        if hasattr(location_object.devices[device_id], "intelligence_modules"):
            for microservice in location_object.devices[device_id].intelligence_modules:
                if hasattr(location_object.devices[device_id].intelligence_modules[microservice], 'occupancy_status_did_wake_from_nap'):
                    try:
                        location_object.devices[device_id].intelligence_modules[microservice].occupancy_status_did_wake_from_nap(botengine)
                    except Exception as e:
                        botengine.get_logger().warning("occupancy.py - Error delivering occupancy_status_did_wake_from_nap message to device microservice (continuing execution): " + str(e))
                        import traceback
                        botengine.get_logger().error(traceback.format_exc())
                        utilities.pause_playback(botengine)


def is_absence_detection_available(botengine, location_object):
    """
    Absence detection is available if we have a combination of activity sensors inside the space,
    combined with a sensor on the perimeter.

    :param botengine: BotEngine
    :param location_object: Location Object
    :return: True if absence detection should be available based on the device composition of this location
    """
    from devices.radar.radar import RadarDevice
    from devices.motion.motion import MotionDevice
    from devices.entry.entry import EntryDevice

    perimeter_sensors = 0
    activity_sensors = 0

    for device_object in list(location_object.devices.values()):
        if not device_object.is_connected:
            # Must be connected
            continue

        if utilities._isinstance(device_object, RadarDevice):
            if device_object.near_exit:
                perimeter_sensors += 1
            else:
                activity_sensors += 1

        elif utilities._isinstance(device_object, MotionDevice):
            if device_object.is_goal_id(MotionDevice.GOAL_MOTION_PROTECT_HOME):
                activity_sensors += 1

        elif utilities._isinstance(device_object, EntryDevice):
            if device_object.is_goal_id(EntryDevice.GOAL_PERIMETER_NORMAL):
                perimeter_sensors += 1

    return perimeter_sensors > 0 and activity_sensors > 0



