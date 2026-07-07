"""
Created on June 28, 2016

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""

# Narrative priority levels
NARRATIVE_PRIORITY_DEBUG = -2
NARRATIVE_PRIORITY_ANALYTIC = -1
NARRATIVE_PRIORITY_DETAIL = 0
NARRATIVE_PRIORITY_INFO = 1
NARRATIVE_PRIORITY_WARNING = 2
NARRATIVE_PRIORITY_CRITICAL = 3

# Narrative types
# High-frequency 'observation' entries for explainable AI and accountability
NARRATIVE_TYPE_OBSERVATION = 0

# Low-frequency 'journal' entries for SUMMARIZED exec-level communications to humans
NARRATIVE_TYPE_JOURNAL = 4

# High-frequency 'insight' entries for real-time CRITICAL exec-level communications to humans
NARRATIVE_TYPE_INSIGHT = 5


class Narrative:
    """
    This class is instantiated as a narrative object that can be updated later.
    """

    def __init__(self, narrative_id, narrative_time, admin):
        """
        Constructor
        :param narrative_id: Narrative ID
        :param narrative_time: Narrative timestamp
        :param to_admin: True if this is to the admin, False if it's to a user
        """
        # Narrative ID
        self.narrative_id = narrative_id

        # Narrative Timestamp
        self.narrative_time = narrative_time

        # To admin
        self.admin = admin

    def resolve(self, botengine):
        """
        Resolve this narrative
        :param botengine: BotEngine environment
        """
        response = botengine.narrate(
            update_narrative_id=self.narrative_id,
            update_narrative_timestamp=self.narrative_time,
            admin=self.admin,
            status=2,
        )

        if response is not None:
            self.narrative_id = response["narrativeId"]
            self.narrative_time = response["narrativeTime"]

    def get_narrative_content(self, botengine):
        """
        Get the content of this narrative
        :param botengine: BotEngine environment
        :return: Narrative content dict, or None if not found
        """
        narrative_content = botengine.get_narration(self.narrative_id, self.admin)

        return narrative_content

    def update_target_json(self, botengine, key, value=None):
        """
        Update a key-value pair in the target JSON of this narrative
        :param botengine: BotEngine environment
        :param key: Key to update
        :param value: Value to set
        :return: None
        """
        narrative_content = self.get_narrative_content(botengine)

        if narrative_content is None:
            return

        else:
            if "target" not in narrative_content:
                narrative_content["target"] = {}
            if value is None:
                del narrative_content["target"][key]
            else:
                narrative_content["target"][key] = value

            response = botengine.narrate(
                update_narrative_id=self.narrative_id,
                update_narrative_timestamp=self.narrative_time,
                admin=self.admin,
                extra_json_dict=narrative_content["target"],
            )

            if response is not None:
                self.narrative_id = response["narrativeId"]
                self.narrative_time = response["narrativeTime"]

    def update_description(self, botengine, description):
        """
        Update the description of an existing narrative
        :param botengine: BotEngine environment
        :param description: New description
        """
        response = botengine.narrate(
            update_narrative_id=self.narrative_id,
            update_narrative_timestamp=self.narrative_time,
            admin=self.admin,
            description=description,
        )

        if response is not None:
            self.narrative_id = response["narrativeId"]
            self.narrative_time = response["narrativeTime"]

    def update(
        self,
        botengine,
        title=None,
        description=None,
        priority=None,
        icon=None,
        icon_font=None,
        status=None,
        narrative_type=None,
        file_ids=None,
        extra_json_dict=None,
        event_type=None,
    ):
        """
        Update any combination of changeable attributes on this narrative in a single API call.
        If extra_json_dict is provided, it merges into the existing target JSON.
        :param botengine: BotEngine environment
        :param title: New title
        :param description: New description
        :param priority: New priority level
        :param icon: New icon name
        :param icon_font: New icon font package
        :param status: New status (0=initial, 1=deleted, 2=resolved, 3=reopened)
        :param narrative_type: New narrative type
        :param file_ids: List of file IDs
        :param extra_json_dict: Dict to merge into existing target JSON
        :param event_type: Event type identifier
        """
        kwargs = {
            "update_narrative_id": self.narrative_id,
            "update_narrative_timestamp": self.narrative_time,
            "admin": self.admin,
        }

        if title is not None:
            kwargs["title"] = title
        if description is not None:
            kwargs["description"] = description
        if priority is not None:
            kwargs["priority"] = priority
        if icon is not None:
            kwargs["icon"] = icon
        if icon_font is not None:
            kwargs["icon_font"] = icon_font
        if status is not None:
            kwargs["status"] = status
        if narrative_type is not None:
            kwargs["narrative_type"] = narrative_type
        if file_ids is not None:
            kwargs["file_ids"] = file_ids
        if event_type is not None:
            kwargs["event_type"] = event_type

        if extra_json_dict is not None:
            narrative_content = self.get_narrative_content(botengine)
            if narrative_content is None:
                return

            target = narrative_content.get("target", {})
            target.update(extra_json_dict)
            kwargs["extra_json_dict"] = target

        response = botengine.narrate(**kwargs)

        if response is not None:
            self.narrative_id = response["narrativeId"]
            self.narrative_time = response["narrativeTime"]

    def delete(self, botengine):
        """
        Delete this narrative
        :param botengine: BotEngine environment
        """
        botengine.delete_narration(self.narrative_id, self.narrative_time)
