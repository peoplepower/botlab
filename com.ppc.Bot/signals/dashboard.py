"""
Created on September 19, 2019

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""

# Titles of the cards
# Do not just change the title of these cards. You must delete previous cards before creating new cards with the new title.
CARD_TITLE_NOW = _("NOW")
CARD_TITLE_SERVICES = _("ALERTS")
CARD_TITLE_TODAY = _("TODAY")

# Do not use this.
CARD_TITLE_SERVICES_DEPRECATED = _("SERVICES")

# Types of cards
CARD_TYPE_NOW = 0
CARD_TYPE_SERVICES = 1
CARD_TYPE_TODAY = 2

# Card Weights - lower numbers float to the top
CARD_TYPE_NOW_WEIGHT = 0
CARD_TYPE_SERVICES_WEIGHT = 10
CARD_TYPE_TODAY_WEIGHT = 5

# Status fields for color coding
STATUS_HIDDEN = -1
STATUS_GOOD = 0
STATUS_WARNING = 1
STATUS_LEARNING = 1
STATUS_CRITICAL = 2

# Timestamped commands
COMMAND_DELETE = -2
COMMAND_SET_STATUS_HIDDEN = -1
COMMAND_SET_STATUS_GOOD = 0
COMMAND_SET_STATUS_WARNING = 1
COMMAND_SET_STATUS_CRITICAL = 2

# State variable names
DASHBOARD_HEADER_PROPERTY_NAME = "dashboard_header"
DASHBOARD_STATUS_PROPERTY_NAME = "now"

# Empty location - typically ignore this location
DASHBOARD_PRIORITY_EMPTY = 0

# Home is running just fine
DASHBOARD_PRIORITY_OKAY = 1

# Home is learning
DASHBOARD_PRIORITY_LEARNING = 2

# Incomplete installation (devices, people, etc.)
DASHBOARD_PRIORITY_INCOMPLETE = 3

# Problems with the system (offline devices, low battery, abnormal device behaviors)
DASHBOARD_PRIORITY_SYSTEM_PROBLEM = 4

# Subjective warning (abnormal trends, sleeping too much, bathroom usage)
DASHBOARD_PRIORITY_SUBJECTIVE_WARNING = 5

# Critical alert (falls, didn't wake up, water leak)
DASHBOARD_PRIORITY_CRITICAL_ALERT = 6

# Alert status for dashboard headers
ALERT_STATUS_IGNORE = 0      # Explicit "no alert semantics" / neutral
ALERT_STATUS_ACTIVE = 1      # Header represents an active alert
ALERT_STATUS_CANCELLED = 2   # Header represents a cancelled alert


def update_dashboard_header(
    botengine,
    location_object,
    name,
    priority,
    percent_good=100,
    title=None,
    comment=None,
    icon=None,
    icon_font=None,
    resolution_object=None,
    conversation_object=None,
    future_timestamp_ms=None,
    ttl_ms=None,
    external_partner=None,
    user_id=None,
    alert_status=None,
):
    """
    Update the dashboard header with the unique name.
    The conversation_object, once created with conversation.create_conversation(), will contain a resolution object and an optional feedback object.
    If you pass in a conversation object, the conversation's resolution and feedback will be used in the app.

    If you want to override the resolution object with your own while driving a conversation, make sure the conversation knows about it inside create_conversation().

        {
            # Unique identifying name
            "name": name,

            # Priority of this dashboard header, which dictates color
            "priority": priority,

            # Title at the top of the dashboard
            "title": title,

            # Comment to display under the title
            "comment": comment,

            # Icon
            "icon": icon,

            # Icon font package
            "icon_font": icon_font,

            # Auto-Populated by a Conversation: True to show the emergency call button
            "call": False,

            # If the emergency call button is present, this flag allows the user to contact the emergency call center.
            "ecc": False,

            # Question ID for the resolution question
            "resolution": {
                "question": "CHANGE STATUS >",

                # Title at the top of the action sheet
                "title": "Change Status",

                # To answer this question, send a data stream message to this address ...
                "datastream_address": "conversation_resolved",

                # ... and include this content merged with the 'content' from the selected option
                "content": {
                    "microservice_id": "26e636d2-c9e6-4caa-a2dc-a9738505c9f2",
                    "conversation_id": "68554d0f-da4a-408c-80fb-0c8f60b0ebc3",
                }

                # The options are already ordered by virtue of being in a list.
                "response_options": [
                    {
                        "text": "Resolved",
                        "ack": "Okay, resolving the notification...",
                        "icon": "thumbs-up",
                        "icon_font": "far",
                        "content": {
                            "answer": 0
                        },
                    },
                    {
                        "text": "False Alarm",
                        "ack": "Okay, marking this a false alarm...",
                        "icon": "thumbs-up",
                        "icon_font": "far",
                        "content": {
                            "answer": 1
                        },
                    }
                ]
            },

            # Question IDs for feedback
            "feedback": {
                # Question for quantified thumbs-up / thumbs-down feedback
                "quantified": "Did we do a good job?",

                # Question for the open-ended text box
                "verbatim": "What do you think caused the alert?",

                # To answer this question, send a data stream message to this address ...
                "datastream_address": "conversation_feedback_quantified",

                # ... and include this content - you fill in the 'quantified', 'verbatim', and optional 'user_id' fields.
                "content": {
                    "microservice_id": "26e636d2-c9e6-4caa-a2dc-a9738505c9f2",
                    "conversation_id": "68554d0f-da4a-408c-80fb-0c8f60b0ebc3",

                    # You'll fill these fields out in the app.
                    "quantified": <0=bad; 1=good>,
                    "verbatim": "Open-ended text field.",
                    "user_id": 1234
                }
            },

            # Internal usage: Future timestamp to apply this header
            "future_timestamp_ms": <timestamp in milliseconds>

            # Internal usage only: Conversation object reference, so we don't keep a dashboard header around for a conversation that expired.
            "conversation_object": <conversation_object>,

            # Internal usage only: Percentage good, to help rank two identical priority headers against each other. Lower percentages get shown first because they're not good.
            "percent": <0-100 weight>

            # External use by partners: Indicates if this header should be implemented on external partner dashboards
            "external_partner": <True/False>,

            # Optional: User ID this dashboard header is associated with (subject of, or actor on, the alert).
            # Distinct from the nested feedback.content.user_id, which identifies the app user submitting feedback.
            "user_id": <int>,

            # Optional: Alert status for this header.
            # 0 = ALERT_STATUS_IGNORE  (explicit "no alert semantics" / neutral)
            # 1 = ALERT_STATUS_ACTIVE  (header represents an active alert)
            # 2 = ALERT_STATUS_CANCELLED (header represents a cancelled alert)
            "alert_status": <0 | 1 | 2>
        }

    :param botengine: BotEngine environment
    :param location_object: Location Object
    :param name: Identifier to later remove or update this dashboard header content
    :param priority: DASHBOARD_PRIORITY_* from dashboard.py
    :param percent_good: 0-100 scale. A lower number conveys worse information and is shown first when comparing 2 identically weighted priority dashboard headers
    :param title: Short title for the dashboard
    :param comment: Short comment for the dashboard
    :param icon: Icon
    :param icon_font: Icon font package to select the icon from, see ICON_FONT_* in utilities.py
    :param resolution_object: Manually specify a resolution question object. This will always override any conversation_object. You could make your own resolution
    :param conversation_object: Optional conversation to manage
    :param future_timestamp_ms: Timestamp at which to apply this header
    :param ttl_ms: Time to live in milliseconds, after which this dashboard header will be automatically deleted
    :param external_partner: True if this header should be shown on external partner dashboards
    :param user_id: Optional int identifying the user this dashboard header is associated with. None omits the field; otherwise persisted as-is.
    :param alert_status: Optional alert status enum for this header. None omits the field. Use ALERT_STATUS_IGNORE (0), ALERT_STATUS_ACTIVE (1), or ALERT_STATUS_CANCELLED (2). Explicit 0 is preserved (distinct from absent).
    """
    content = {
        "name": name,
        "priority": priority,
        "percent": percent_good,
        "updated_ms": botengine.get_timestamp(),
    }

    if title is not None:
        content["title"] = title

    if comment is not None:
        content["comment"] = comment

    if icon is not None:
        content["icon"] = icon

    if icon_font is not None:
        content["icon_font"] = icon_font

    if future_timestamp_ms is not None:
        content["future_timestamp_ms"] = future_timestamp_ms

    if conversation_object is not None:
        content["conversation_object"] = conversation_object

    # Include TTL in the update payload so consumers (e.g., tests/UI) can inspect it directly
    if ttl_ms is not None:
        content["ttl_ms"] = ttl_ms
    
    if external_partner is not None:
        content["external_partner"] = external_partner

    if user_id is not None:
        content["user_id"] = user_id

    if alert_status is not None:
        content["alert_status"] = alert_status

    if resolution_object is not None:
        # Flush questions so we make sure our questions all have question ID's
        botengine.flush_questions()
        content["resolution"] = resolution_object

    location_object.distribute_datastream_message(
        botengine, "update_dashboard_header", content, internal=True, external=False
    )

    if ttl_ms is not None:
        starting_time_ms = botengine.get_timestamp()
        if future_timestamp_ms is not None:
            starting_time_ms = future_timestamp_ms

        delete_dashboard_header(
            botengine,
            location_object,
            name,
            future_timestamp_ms=starting_time_ms + ttl_ms,
        )


def refresh_dashboard_header(botengine, location_object):
    """
    Simply refresh the dashboard header.
    One way this can be used is if a conversation wraps up and we previously had a dashboard item related to that conversation,
    the dashboard header microservice will automatically delete headers associated with that now-inactive conversation,
    which acts as a safety net in case the microservice itself dropped the ball on deleting its own header during a conversation.
    :param botengine:
    :param location_object:
    :return:
    """
    location_object.distribute_datastream_message(
        botengine, "update_dashboard_header", {}, internal=True, external=False
    )


def delete_dashboard_header(botengine, location_object, name, future_timestamp_ms=None):
    """
    Remove the dashboard header content
    :param botengine: BotEngine envirionment
    :param location_object: Location object
    :param name: Unique name of the dashboard header to delete
    :param future_timestamp_ms: Future timestamp in which to automatically delete this dashboard header
    :return:
    """
    content = {"name": name}

    if future_timestamp_ms is not None:
        content["future_timestamp_ms"] = future_timestamp_ms

    location_object.distribute_datastream_message(
        botengine, "update_dashboard_header", content, internal=True, external=False
    )


def set_status(
    botengine,
    location_object,
    unique_identifier,
    comment,
    status=STATUS_GOOD,
    comment_weight=50,
    device_id=None,
    icon=None,
    icon_font=None,
    url=None,
    section_title=CARD_TITLE_NOW,
    section_weight=CARD_TYPE_NOW_WEIGHT,
    set_status_good_timestamp_ms=None,
    set_status_warning_timestamp_ms=None,
    set_status_critical_timestamp_ms=None,
    delete_timestamp_ms=None,
    status_comments=None,
):
    """
    Set content for a status-style card.
    These are the multiple rows of information at the the top of the dashboard that say what is happening right now.
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param unique_identifier: Unique identifier for this content
    :param comment: Comment to display. If None then this content gets deleted.
    :param status: Status for color-coding the content
    :param comment_weight: Weight of the comment relative to other comments inside this card.
    :param device_id: Optional device ID to create a link to a device that is having a problem
    :param icon: Optional icon for the content
    :param icon_font: Optional style for the icon font. Default is FontAwesome Regular. See the ICON_FONT_* descriptions in com.ppc.Bot/utilities/utilities.py
    :param url: Optional URL to open upon clicking on this status item
    :param section_title: Title of the section, in case we want multiple NOW-style cards
    :param section_weight: Weight of the section, in case we want to change it
    :return: Dashboard JSON content to be saved and used in updating later
    """
    alarms = {}
    comments = {}

    element = {
        "status": status,
        "comment": comment,
        "weight": comment_weight,
        "id": unique_identifier,
        "icon": icon,
        "alarms": alarms,
        "comments": comments,
    }

    if icon_font is not None:
        element["icon_font"] = icon_font

    if device_id is not None:
        element["device_id"] = device_id

    if url is not None:
        element["url"] = url

    content = {
        "type": CARD_TYPE_NOW,
        "title": section_title,
        "weight": section_weight,
        "content": element,
    }

    # Convert string timestamps to integers
    if isinstance(set_status_good_timestamp_ms, str):
        set_status_good_timestamp_ms = int(float(set_status_good_timestamp_ms))
    if isinstance(set_status_warning_timestamp_ms, str):
        set_status_warning_timestamp_ms = int(float(set_status_warning_timestamp_ms))
    if isinstance(set_status_critical_timestamp_ms, str):
        set_status_critical_timestamp_ms = int(float(set_status_critical_timestamp_ms))
    if isinstance(delete_timestamp_ms, str):
        delete_timestamp_ms = int(float(delete_timestamp_ms))

    if set_status_good_timestamp_ms is not None:
        alarms[set_status_good_timestamp_ms] = COMMAND_SET_STATUS_GOOD

    if set_status_warning_timestamp_ms is not None:
        alarms[set_status_warning_timestamp_ms] = COMMAND_SET_STATUS_WARNING
        comments[set_status_warning_timestamp_ms] = (
            status_comments.get(STATUS_WARNING) if status_comments else None
        )

    if set_status_critical_timestamp_ms is not None:
        alarms[set_status_critical_timestamp_ms] = COMMAND_SET_STATUS_CRITICAL
        comments[set_status_critical_timestamp_ms] = (
            status_comments.get(STATUS_CRITICAL) if status_comments else None
        )

    if delete_timestamp_ms is not None:
        alarms[delete_timestamp_ms] = COMMAND_DELETE

    location_object.distribute_datastream_message(
        botengine, "update_dashboard_content", content, internal=True, external=False
    )
    return content


def update_status_content(botengine, location_object, content):
    """
    Retrieve the content from the last set_status() call. You can update it in your microservice however you want.
    When you're ready to apply an update, just pass that updated JSON content back into this method.
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param content: Updated JSON dashboard content to set
    :return: Updated JSON content
    """
    location_object.distribute_datastream_message(
        botengine, "update_dashboard_content", content, internal=True, external=False
    )
    return content


def delete_status(
    botengine, location_object, unique_identifier, section_title=CARD_TITLE_NOW
):
    """
    Delete content within a status-style card
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param unique_identifier: Unique identifier for this content
    :param section_title: Section title in case we need to delete the section
    :return: None
    """
    content = {
        "type": CARD_TYPE_NOW,
        "title": section_title,
        "content": {"id": unique_identifier, "comment": None},
    }

    location_object.distribute_datastream_message(
        botengine, "update_dashboard_content", content, internal=True, external=False
    )
    return None


def set_today(
    botengine,
    location_object,
    unique_identifier,
    comment,
    status=STATUS_GOOD,
    comment_weight=50,
    device_id=None,
    icon=None,
    icon_font=None,
    url=None,
    section_title=CARD_TITLE_TODAY,
    section_weight=CARD_TYPE_TODAY_WEIGHT,
    set_status_good_timestamp_ms=None,
    set_status_warning_timestamp_ms=None,
    set_status_critical_timestamp_ms=None,
    delete_timestamp_ms=None,
    status_comments=None,
):
    """
    Set content for a today-style card.
    These are rows of information in the dashboard that describe what has happened today.
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param unique_identifier: Unique identifier for this content
    :param comment: Comment to display. If None then this content gets deleted.
    :param status: Status for color-coding the content
    :param comment_weight: Weight of the comment relative to other comments inside this card.
    :param device_id: Optional device ID to create a link to a device that is having a problem
    :param icon: Optional icon for the content
    :param icon_font: Optional style for the icon font. Default is FontAwesome Regular. See the ICON_FONT_* descriptions in com.ppc.Bot/utilities/utilities.py
    :param url: Optional URL to open upon clicking on this status item
    :param section_title: Title of the section, in case we want multiple TODAY-style cards
    :param section_weight: Weight of the section, in case we want to change it
    :return: Dashboard JSON content to be saved and used in updating later
    """
    alarms = {}
    comments = {}

    element = {
        "status": status,
        "comment": comment,
        "weight": comment_weight,
        "id": unique_identifier,
        "icon": icon,
        "alarms": alarms,
        "comments": comments,
    }

    if icon_font is not None:
        element["icon_font"] = icon_font

    if device_id is not None:
        element["device_id"] = device_id

    if url is not None:
        element["url"] = url

    content = {
        "type": CARD_TYPE_TODAY,
        "title": section_title,
        "weight": section_weight,
        "content": element,
    }

    # Convert string timestamps to integers
    if isinstance(set_status_good_timestamp_ms, str):
        set_status_good_timestamp_ms = int(float(set_status_good_timestamp_ms))
    if isinstance(set_status_warning_timestamp_ms, str):
        set_status_warning_timestamp_ms = int(float(set_status_warning_timestamp_ms))
    if isinstance(set_status_critical_timestamp_ms, str):
        set_status_critical_timestamp_ms = int(float(set_status_critical_timestamp_ms))
    if isinstance(delete_timestamp_ms, str):
        delete_timestamp_ms = int(float(delete_timestamp_ms))

    if set_status_good_timestamp_ms is not None:
        alarms[set_status_good_timestamp_ms] = COMMAND_SET_STATUS_GOOD

    if set_status_warning_timestamp_ms is not None:
        alarms[set_status_warning_timestamp_ms] = COMMAND_SET_STATUS_WARNING
        comments[set_status_warning_timestamp_ms] = (
            status_comments.get(STATUS_WARNING) if status_comments else None
        )

    if set_status_critical_timestamp_ms is not None:
        alarms[set_status_critical_timestamp_ms] = COMMAND_SET_STATUS_CRITICAL
        comments[set_status_critical_timestamp_ms] = (
            status_comments.get(STATUS_CRITICAL) if status_comments else None
        )

    if delete_timestamp_ms is not None:
        alarms[delete_timestamp_ms] = COMMAND_DELETE

    location_object.distribute_datastream_message(
        botengine, "update_dashboard_content", content, internal=True, external=False
    )
    return content


def update_today_content(botengine, location_object, content):
    """
    Retrieve the content from the last set_today() call. You can update it in your microservice however you want.
    When you're ready to apply an update, just pass that updated JSON content back into this method.
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param content: Updated JSON dashboard content to set
    :return: Updated JSON content
    """
    location_object.distribute_datastream_message(
        botengine, "update_dashboard_content", content, internal=True, external=False
    )
    return content


def delete_today(
    botengine, location_object, unique_identifier, section_title=CARD_TITLE_TODAY
):
    """
    Delete content within a today-style card
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param unique_identifier: Unique identifier for this content
    :param section_title: Section title in case we need to delete the section
    :return: None
    """
    content = {
        "type": CARD_TYPE_TODAY,
        "title": section_title,
        "content": {"id": unique_identifier, "comment": None},
    }

    location_object.distribute_datastream_message(
        botengine, "update_dashboard_content", content, internal=True, external=False
    )
    return None


def set_service(
    botengine,
    location_object,
    unique_identifier,
    title,
    comment,
    icon,
    icon_font=None,
    status=STATUS_GOOD,
    percent=100.0,
    active=True,
    description=None,
    status_text=None,
    question_id=None,
    collection_id=None,
    section_id=None,
    comment_weight=50,
    section_title=CARD_TITLE_SERVICES,
    section_weight=CARD_TYPE_SERVICES_WEIGHT,
    display_info=None,
):
    """
    Set content for a service-style card.
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param unique_identifier: Unique identifier for this content
    :param title: Title of the content
    :param comment: Comment to display. If None then this content gets deleted
    :param icon: Icon name to render from http://peoplepowerco.com/icons or http://fontawesome.com
    :param icon_font: Icon font package to use. See the ICON_FONT_* descriptions in com.ppc.Bot/utilities/utilities.py
    :param status: Status for color-coding the content
    :param percent: DEPRECATED. Percent complete.
    :param active: True if this element is active, False if it is disabled
    :param status_text: Optional status text to show in the app
    :param question_id: Optional Question ID to link to
    :param collection_id: Optional Collection ID to link to
    :param section_id: Optional Section ID to link to
    :param comment_weight: Weight of this comment relative to other comments
    :param section_title: Title of the section, in case we want multiple NOW-style cards
    :param section_weight: Weight of the section, in case we want to change it
    :param display_info: Optional display info to show in the app
        :param display_home_area: Optional home area to show in the app
    """
    if comment is not None:
        element = {
            "title": title,
            "comment": comment,
            "icon": icon,
            "status": status,
            "percent": min(max(percent, 0), 100) if percent is not None else 100,
            "active": active,
            "id": unique_identifier,
            "weight": comment_weight,
        }

        if icon_font is not None:
            element["icon_font"] = icon_font

        if question_id is not None:
            element["question_id"] = question_id

        if collection_id is not None:
            element["collection_id"] = collection_id

        if section_id is not None:
            element["section_id"] = section_id

        if description is not None:
            element["description"] = description

        if status_text is not None:
            element["status_text"] = status_text
        elif active:
            element["status_text"] = _("RUNNING")
        else:
            element["status_text"] = _("DISABLED")
        if display_info is not None:
            element["display_info"] = display_info

    else:
        element = None

    content = {
        "type": CARD_TYPE_SERVICES,
        "title": section_title,
        "weight": section_weight,
        "content": element,
    }

    location_object.distribute_datastream_message(
        botengine, "update_dashboard_content", content, internal=True, external=False
    )


def delete_service(
    botengine, location_object, unique_identifier, section_title=CARD_TITLE_SERVICES
):
    """
    Delete content within a service-style card
    :param botengine: BotEngine environment
    :param location_object: Location object
    :param unique_identifier: Unique identifier for this content
    :param section_title: Title of the section in case we need to delete it
    """
    content = {
        "type": CARD_TYPE_SERVICES,
        "title": section_title,
        "content": {"id": unique_identifier, "comment": None},
    }

    location_object.distribute_datastream_message(
        botengine, "update_dashboard_content", content, internal=True, external=False
    )


def oneshot_resolution_object(
    botengine,
    name,
    dashboard_button=_("UPDATE STATUS >"),
    actionsheet_title=_("Update Status"),
    resolution_button=_("Resolve"),
    ack=_("Okay, resolving the notification..."),
    icon="thumbs-up",
    icon_font="far",
    response_options=None,
):
    """
    Generate a one-shot resolution object JSON structure.
    The resolution will actually be handled by the location_dashboardheader_microservice through a datastream message "resolve_dashboard" and content
    :param botengine: BotEngine environment
    :param name: Name of the dashboard item to clear once resolved
    :param dashboard_button: Dashboard button text, default is "UPDATE STATUS >"
    :param actionsheet_title: Title of the bottom action sheet, default is "Update Status"
    :param resolution_button: Text on the only action sheet button which will resolve this dashboard item, default is "Resolve"
    :param ack: Acknowledgment text to transition back to the dashboard, default is "Okay, resolving the notification..."
    :param icon: Icon to accompany the ack while transitioning back to the dashboard, default is "thumbs-up"
    :param icon_font: Icon font for the icon, default is "far" (fontawesome regular). See utilities for font icon pack names.
    :param response_options: Advanced option to completely override most of the settings and replace the "response_options" list with the provided custom list of options. Please review the response_options JSON format.
    :return: JSON object
    """
    if response_options is None:
        response_options = [
            {
                "text": resolution_button,
                "ack": ack,
                "icon": icon,
                "icon_font": icon_font,
                "content": {"answer": 0},
            }
        ]

    return {
        # Question to place on the front page of the app
        "button": dashboard_button,
        # Title at the top of the bottom modal action sheet
        "title": actionsheet_title,
        # To answer this question, send a data stream message to this address ...
        "datastream_address": "resolve_dashboard_header",
        # ... and include this content merged with the 'content' from the selected option
        "content": {
            # Name of the dashboard item to resolve, to be received and handled in the datastream message from the app
            "name": name
        },
        "response_options": response_options,
    }


def updated_dashboard_headers(
    botengine, location_object, published_header, all_headers
):
    """
    Announce to other microservices that we've updated our dashboard headers and provide the recent stack of headers

    :param botengine: BotEngine
    :param location_object: Location Object
    :param published_header: Dashboard header we've published
    :param all_headers: Dictionary of all headers in the stack
    """
    content = {"published_header": published_header, "all_headers": all_headers}

    location_object.distribute_datastream_message(
        botengine,
        "updated_dashboard_headers",
        content=content,
        internal=True,
        external=False,
    )


def updated_dashboard_status(botengine, location_object, status_content):
    """
    Announce to other microservices that we've updated the dashboard status (NOW cards)

    :param botengine: BotEngine
    :param location_object: Location Object
    :param status_content: Dashboard status content that was published (the 'now' state)
    """
    content = {"status_content": status_content}

    location_object.distribute_datastream_message(
        botengine,
        "updated_dashboard_status",
        content=content,
        internal=True,
        external=False,
    )


def updated_dashboard_today(botengine, location_object, today_content):
    """
    Announce to other microservices that we've updated the dashboard today cards

    :param botengine: BotEngine
    :param location_object: Location Object
    :param today_content: Dashboard today content that was published (the 'today' state)
    """
    content = {"today_content": today_content}

    location_object.distribute_datastream_message(
        botengine,
        "updated_dashboard_today",
        content=content,
        internal=True,
        external=False,
    )