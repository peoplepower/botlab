"""
Created on December 18, 2025

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Destry Teeter
"""

import utilities.utilities as utilities

USER_STATUS_LOCATION_PROPERTIES_KEY_PREFIX = "zendesk_user_status_"

USER_STATUS_SUSPENDED = -1
USER_STATUS_NOT_FOUND = 0
USER_STATUS_RELEASED = 1


def request_customer_support(
    botengine,
    location_object,
    ticket_type,
    ticket_priority,
    subject,
    comment,
    data=None,
    custom_fields=None,
    brand="default",
    user_id=None,
    template="",
    language=None,
    voip_call=None,
):
    """
    Request customer support via ZenDesk
    :param botengine: BotEngine environment
    :param location_object: Location object to check for user status properties
    :param ticket_type: botengine.TICKET_TYPE_*
    :param ticket_priority: botengine.TICKET_PRIORITY_*
    :param subject: Subject line
    :param comment: Comment to customer support
    :param data: Additional data to send to customer support
    :param custom_fields: Additional custom fields to send to customer support
    :param brand: Brand name
    :param user_id: User ID
    :param template: Velocity template name.  Default is "comment.vm"
    :param language: Language code. Default is "en"
    :param voip_call: Provide a VoIP link in ticket (if service is available)
    :return:
    """
    botengine.get_logger(f"{__name__}").info(">request_customer_support()")
    import properties

    allowed = properties.get_property(
        botengine, "ZENDESK_TICKET_CREATION_ALLOWED", complain_if_missing=False
    )
    if not allowed:
        botengine.get_logger(f"{__name__}").info(
            "<request_customer_support() Ticket creation not allowed by domain or oganization"
        )
        return

    if user_id is None:
        botengine.get_logger(f"{__name__}").info(
            "<request_customer_support() No user ID specified for ticket creation"
        )
        return

    zendesk_user_status_property_key = USER_STATUS_LOCATION_PROPERTIES_KEY_PREFIX + str(
        user_id
    )
    zendesk_user_status = (
        location_object.get_location_property(
            botengine, zendesk_user_status_property_key
        )
        or 0
    )
    if zendesk_user_status == USER_STATUS_SUSPENDED:
        botengine.get_logger(f"{__name__}").warning(
            "<request_customer_support() User is suspended from ticket creation"
        )
        return

    botengine.request_customer_support(
        ticket_type=ticket_type,
        ticket_priority=ticket_priority,
        subject=subject,
        comment=comment,
        data=data,
        custom_fields=custom_fields,
        brand=brand,
        user_id=user_id,
        template=template,
        language=language,
        voip_call=voip_call,
    )
    botengine.get_logger(f"{__name__}").info("<request_customer_support()")
