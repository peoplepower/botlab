# Zendesk Signal

This module provides integration with Zendesk for customer support ticket creation within the BotLab Core platform.

## Overview

The `zendesk.py` signal enables bots to request customer support tickets via Zendesk, with configurable ticket types, priorities, and custom fields. It also enforces domain or organization-level restrictions and user status checks before ticket creation.

## Key Features

- **Ticket Creation**: Request support tickets with subject, comment, and additional data.
- **User Status Checks**: Prevents ticket creation for suspended users.
- **Domain/Organization Control**: Honors global settings to allow or disallow ticket creation.
- **Custom Fields**: Supports custom fields and templates for tickets.
- **Brand and Language Support**: Specify brand and language for each ticket.

## Usage

Import and call the `request_customer_support` function:

```python
from signals.zendesk import zendesk

zendesk.request_customer_support(
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
	voip_call=None
)
```

### Parameters

- `botengine`: BotEngine environment instance.
- `location_object`: The location context for the ticket.
- `ticket_type`: Ticket type (e.g., `botengine.TICKET_TYPE_*`).
- `ticket_priority`: Ticket priority (e.g., `botengine.TICKET_PRIORITY_*`).
- `subject`: Subject line for the ticket.
- `comment`: Description or comment for support.
- `data`: (Optional) Additional data for support.
- `custom_fields`: (Optional) Custom fields for Zendesk.
- `brand`: (Optional) Brand name (default: `"default"`).
- `user_id`: (Required) User ID for the ticket.
- `template`: (Optional) Velocity template name.
- `language`: (Optional) Language code.
- `voip_call`: (Optional) VoIP link for the ticket.

## Notes

- Ticket creation is only allowed if enabled by the domain or organization.
- Suspended users cannot create tickets, implemented by com.ppc.Microservices/intelligence/zendesk service
