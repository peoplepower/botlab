"""
Created on January 1, 2023

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: Parth Agrawal

DEPRECATED: This microservice is deprecated.
==============================================================================
Please use the modern LLM architecture instead:
    - Use Intelligence.llm_chat() method (built into the base class)
    - Override llm_response() to handle responses
    - See com.ppc.Bot/intelligence/intelligence.py for details

Migration Guide:
    OLD (deprecated):
        distribute_datastream_message(botengine, "submit_chatgpt_chat_completion", {...})
        def openai(self, botengine, content): # Handle response
    
    NEW (modern):
        self.llm_chat(botengine, messages=[{"role": "user", "content": "..."}])
        def llm_response(self, botengine, response, reference, argument): # Handle response

Benefits of the new approach:
    - Automatic routing via intelligence_id (no manual key matching)
    - Consistent with timer pattern (familiar to developers)
    - Provider-agnostic (works with any LLM provider microservice)
    - Automatic token usage tracking
    - Cleaner, simpler code
==============================================================================
"""

from intelligence.intelligence import Intelligence # type: ignore


class LocationChatGPTMicroservice(Intelligence):
    """
    ChatGPT Microservice

    This microservice is responsible for handling ChatGPT requests.
    """

    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, either a location or a device object.
        """
        Intelligence.__init__(self, botengine, parent)
        pass
