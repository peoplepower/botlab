'''
Created on March 27, 2019

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
'''

import bot


class Intelligence:
    """
    Base Intelligence Module Class / Interface for Organizations
    """
    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, like an Organization
        """
        import uuid
        self.intelligence_id = str(uuid.uuid4())
        self.parent = parent
        
        # LLM argument storage: Maps reference -> (timestamp_ms, argument)
        # Used to store arguments passed to llm_chat() for retrieval in llm_response()
        # Format: {reference: (timestamp_ms, argument)}
        # Auto-purged after 30 minutes to prevent memory leaks
        self._llm_arguments = {}
        
        # LLM usage tracking: Tracks token usage and costs per microservice
        # Format: {
        #     "requests": int,              # Total number of LLM requests
        #     "prompt_tokens": int,         # Total prompt tokens used
        #     "completion_tokens": int,     # Total completion tokens used
        #     "total_tokens": int,          # Total tokens (prompt + completion)
        #     "cost_usd": float,            # Total cost in USD (only if provided by provider)
        #     "by_provider": {              # Usage broken down by provider
        #         provider_name: {
        #             "requests": int,
        #             "total_tokens": int,
        #             "cost_usd": float
        #         }
        #     },
        #     "by_model": {                 # Usage broken down by model
        #         model_name: {
        #             "requests": int,
        #             "total_tokens": int,
        #             "cost_usd": float
        #         }
        #     }
        # }
        self.llm_usage = {
            "requests": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "by_provider": {},
            "by_model": {},
        }
        
    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        return
    
    def destroy(self, botengine):
        """
        This device or object is getting permanently deleted - it is no longer in the user's account.
        :param botengine: BotEngine environment
        """
        return
    
    def new_version(self, botengine):
        """
        Upgraded to a new bot version
        :param botengine: BotEngine environment
        """
        # Added January 2, 2026 - LLM argument storage
        if not hasattr(self, '_llm_arguments'):
            self._llm_arguments = {}
        
        # Added January 2, 2026 - LLM usage tracking
        if not hasattr(self, 'llm_usage'):
            self.llm_usage = {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cost_usd": 0.0,
                "by_provider": {},
                "by_model": {},
            }
        
        return

    def question_answered(self, botengine, question):
        """
        The user answered a question
        :param botengine: BotEngine environment
        :param question: Question object
        """
        return
    
    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Message Received
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Content of the message
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)
    
    def schedule_fired(self, botengine, schedule_id):
        """
        The bot executed on a hard coded schedule specified by our runtime.json file
        :param botengine: BotEngine environment
        :param schedule_id: Schedule ID that is executing from our list of runtime schedules
        """
        return
        
    def timer_fired(self, botengine, argument):
        """
        The bot's intelligence timer fired
        :param botengine: Current botengine environment
        :param argument: Argument applied when setting the timer
        """
        return
    
    def llm_response(self, botengine, response, reference, argument):
        """
        Called automatically when LLM responds
        
        Override this method in your microservice to handle LLM responses.
        Token usage is automatically tracked by the provider microservice before this method is called.
        
        The argument passed to llm_chat() is automatically cleaned up from memory when this method is called.
        
        :param botengine: BotEngine environment
        :param response: LLM response (OpenAI format)
        :param reference: Reference that was passed to llm_chat()
        :param argument: Argument that was passed to llm_chat()
        """
        # Clean up stored argument now that we've received the response
        if hasattr(self, "_llm_arguments") and reference in self._llm_arguments:
            del self._llm_arguments[reference]
        
        return

    def async_data_request_ready(self, botengine, reference, content):
        """
        A botengine.request_data() asynchronous request for CSV data is ready.

        This is part of a very scalable method to extract large amounts of data from the server for the purpose of
        machine learning services. If a service needs to extract a large amount of data for one or multiple devices,
        the developer should call botengine.request_data(..) and also allow the bot to trigger off of trigger type 2048.
        The bot can exit its current execution. The server will independently gather all the necessary data and
        capture it into a LZ4-compressed CSV file on the server which is available for one day and accessible only by
        the bot through a public HTTPS URL identified by a cryptographic token. The bot then gets triggered and
        downloads the CSV data, passing the data throughout the environment with this async_data_request_ready()
        event-driven method.

        IMPORTANT: This method executes in an asynchronous environment where you are NOT allowed to:
        - Set timers or alarms
        - Manage class variables that persist across executions
        - Perform other stateful operations

        To return to a synchronous environment where you can use timers and manage state, call:
        botengine.async_execute_again_in_n_seconds(seconds)

        Developers are encouraged to use the 'reference' argument inside calls to botengine.request_data(..). The
        reference is passed back out at the completion of the request, allowing the developer to ensure the
        data request that is now available was truly destined for their microservice.

        Your bots will need to include the following configuration for data requests to operate:
        * runtime.json should include trigger 2048
        * structure.json should include inside 'pip_install_remotely' a reference to the "lz4" Python package

        :param botengine: BotEngine environment
        :param reference: Optional reference passed into botengine.request_data(..)
        :param content: Data request content
        """
        # For backwards compatibility, call the deprecated data_request_ready method if it exists
        if hasattr(self, 'data_request_ready'):
            return self.data_request_ready(botengine, reference, content)
        return

    # ===============================================================================
    # DEPRECATED METHODS - DO NOT USE IN NEW CODE
    # ===============================================================================
    
    def data_request_ready(self, botengine, reference, content):
        """
        DEPRECATED: Use async_data_request_ready() instead.
        
        :param botengine: BotEngine environment
        :param reference: Optional reference passed into botengine.request_data(..)
        :param content: Data request content
        """
        return

    def document_updated(self, botengine, document, request_id):
        """
        Document and/or questions and answers were updated from the document processing service
        :param botengine: BotEngine environment
        :param document: Updated document
        :param request_id: Request ID
        """
        pass

    def get_document_property_updates(self, botengine):
        """
        Return document property updates
        Example:
        {
            "documentId": 0,
            "properties": [{
                "name": "processed",
                "value": "1"
            }]
        }
        :param botengine: BotEngine environment
        :return: Documents property updates
        """
        if not hasattr(self, "document_property_updates"):
            return None
        return self.document_property_updates
    
    def get_documents_questions(self, botengine):
        """
        Return a list of documents questions
        Example: 
        [
            {
                "documentId": 0,
                "questions": ["What is this?"],
                "questionKeys": ["summary"]
            }
        ]
        :param botengine: BotEngine environment
        :return: List of documents questions
        """
        if not hasattr(self, "documents_questions"):
            return None
        return self.documents_questions

    # ===============================================================================
    # Built-in LLM methods.
    # ===============================================================================
    
    def llm_chat(self, botengine, argument=None, reference=None, provider_api=None, **kwargs):
        """
        Send LLM request to a provider microservice.

        The response will be automatically routed back to this microservice's llm_response() method
        using the intelligence_id for routing (just like the timer system).

        Supports multiple provider APIs via the provider_api parameter.
        See signals/llm.py for available provider API constants and documentation links.

        Kwargs are provider-specific parameters passed directly to the provider microservice.

        Chat Completion API (default):
            self.llm_chat(botengine,
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-4o",
                temperature=0.2,
            )

        Response API:
            import signals.llm as llm
            self.llm_chat(botengine,
                provider_api=llm.PROVIDER_API_OPENAI_RESPONSE,
                input="Hello",
                model="gpt-4o",
            )

        :param botengine: BotEngine environment
        :param argument: Optional argument to provide when the response is received (like timer argument)
        :param reference: Optional reference to identify this request (like timer reference)
        :param provider_api: Provider API to use (see signals/llm.py constants). If None, defaults to Chat Completion.
        :param kwargs: Provider-specific parameters (e.g., messages, input, model, max_tokens, temperature)
        """
        import signals.llm as llm

        # Generate reference if not provided
        if reference is None:
            import uuid
            reference = str(uuid.uuid4())

        # Store argument with timestamp for later retrieval in llm_response()
        self._store_llm_argument(botengine, reference, argument)

        # Send request via signals
        llm.chat(
            botengine,
            self.parent,
            intelligence_id=self.intelligence_id,
            reference=reference,
            argument=argument,
            provider_api=provider_api,
            **kwargs
        )
    
    def _store_llm_argument(self, botengine, reference, argument):
        """
        Store argument for LLM request with timestamp for auto-purge
        
        Arguments are automatically purged:
        - When llm_response() is called (immediate cleanup)
        - After 30 minutes if no response is received (prevent memory leaks)
        
        :param botengine: BotEngine environment
        :param reference: Reference for this request
        :param argument: Argument to store
        """
        # Ensure class variable exists
        if not hasattr(self, "_llm_arguments"):
            self._llm_arguments = {}
        
        # Auto-purge entries older than 30 minutes (cleanup orphaned requests)
        current_timestamp_ms = botengine.get_timestamp()
        purge_threshold_ms = current_timestamp_ms - (30 * 60 * 1000)  # 30 minutes
        
        # Remove old entries
        self._llm_arguments = {
            ref: (ts, arg) 
            for ref, (ts, arg) in self._llm_arguments.items() 
            if ts > purge_threshold_ms
        }
        
        # Store new argument with timestamp
        self._llm_arguments[reference] = (current_timestamp_ms, argument)
    
    def _get_llm_argument(self, botengine, reference):
        """
        Get stored argument for LLM request (for internal use or debugging)
        
        Note: The argument is automatically passed to llm_response() by the provider,
        so this method is typically not needed. It's available for edge cases or debugging.
        
        :param botengine: BotEngine environment
        :param reference: Reference for this request
        :return: Stored argument, or None if not found or expired
        """
        if not hasattr(self, "_llm_arguments"):
            return None
        
        if reference in self._llm_arguments:
            timestamp_ms, argument = self._llm_arguments[reference]
            # Check if expired (shouldn't happen due to auto-purge, but double-check)
            current_timestamp_ms = botengine.get_timestamp()
            if current_timestamp_ms - timestamp_ms > (30 * 60 * 1000):
                del self._llm_arguments[reference]
                return None
            return argument
        
        return None
    
    def _get_provider_from_llm_response(self, response):
        """
        Extract provider name from LLM response
        
        Provider microservices should always include "provider" in the response metadata.
        This fallback inference is only used if the provider field is missing (should be rare).
        
        :param response: LLM response dict
        :return: Provider name (e.g., "openai", "anthropic", "caredaily")
        """
        # Primary method: Check for provider in response metadata (provider microservices should always include this)
        if "provider" in response:
            return response["provider"]
        
        # Fallback: Infer from response structure (only used if provider metadata is missing)
        # NOTE: This is not super future-proof. Provider microservices should always
        # include the "provider" field in their response metadata. This fallback may fail for:
        # - New providers not listed here
        # - Providers that change their ID format
        # - Custom/internal providers
        if "id" in response:
            response_id = response.get("id", "")
            if response_id.startswith("chatcmpl-"):
                return "openai"
            if response_id.startswith("msg-"):
                return "anthropic"
            # Add more provider ID patterns here as needed, but prefer fixing the provider microservice
            # to include the "provider" field instead
        
        # If we can't determine the provider, return "unknown"
        # This should rarely happen if provider microservices are implemented correctly
        return "unknown"
    
    # ===============================================================================
    # Built-in statistics methods.
    # ===============================================================================
    def reset_statistics(self, botengine):
        """
        Reset statistics
        :param botengine: BotEngine environment
        """
        self._init_statistics()
        return

    def track_statistics(self, botengine, time_elapsed_ms):
        """
        Track statistics for this microservice
        :param botengine: BotEngine environment
        """
        # Catch-all in case subclass forgets to call super().initialize()
        if not hasattr(self, "statistics"):
            self._init_statistics()
        self.statistics["calls"] += 1
        self.statistics["time"] += time_elapsed_ms
        return

    def get_statistics(self, botengine):
        """
        get statistics
        :param botengine: BotEngine environment
        """
        if not hasattr(self, "statistics"):
            self._init_statistics()
        return self.statistics
    
    #===============================================================================
    # Built-in Timer and Alarm methods.
    #===============================================================================
    def start_timer_ms(self, botengine, milliseconds, argument=None, reference=""):
        """
        Start a relative timer in milliseconds
        :param botengine: BotEngine environment
        :param seconds: Time in milliseconds for the timer to fire
        :param argument: Optional argument to provide when the timer fires.
        :param reference: Optional reference to use to manage this timer.
        """
        # We seed the reference with this intelligence ID to make it unique against all other intelligence modules.
        bot.start_organization_intelligence_timer_ms(botengine, milliseconds, self.intelligence_id, argument, self.intelligence_id + str(reference))

    def start_timer_s(self, botengine, seconds, argument=None, reference=""):
        """
        Helper function with an explicit "_s" at the end, to start a timer in seconds
        :param botengine: BotEngine environment
        :param seconds: Time in seconds for the timer to fire
        :param argument: Optional argument to provide when the timer fires.
        :param reference: Optional reference to use to manage this timer.
        """
        self.start_timer(botengine, seconds, argument, str(reference))

    def start_timer(self, botengine, seconds, argument=None, reference=""):
        """
        Start a relative timer in seconds
        :param botengine: BotEngine environment
        :param seconds: Time in seconds for the timer to fire
        :param argument: Optional argument to provide when the timer fires.
        :param reference: Optional reference to use to manage this timer.
        """
        bot.start_organization_intelligence_timer(botengine, seconds, self.intelligence_id, argument, self.intelligence_id + str(reference))

    def is_timer_running(self, botengine, reference=""):
        """
        Check if a timer or alarm with the given reference is running
        :param botengine: BotEngine environment
        :param reference: Reference
        :return: True if timers or alarms with the given reference are running.
        """
        return botengine.is_timer_running(self.intelligence_id + str(reference))

    def timer_timestamp_ms(self, botengine, reference=""):
        """
        Get the timer or alarm's timestamp in milliseconds
        :param reference:
        :return:
        """
        return botengine.timer_timestamp_ms(self.intelligence_id + str(reference))

    def cancel_timers(self, botengine, reference=""):
        """
        Cancel timers with the given reference
        :param botengine: BotEngine environment
        :param reference: Cancel all timers with the given reference
        """
        botengine.cancel_timers(self.intelligence_id + str(reference))
    
    def set_alarm(self, botengine, timestamp_ms, argument=None, reference=""):
        """
        Set an absolute alarm
        :param botengine: BotEngine environment
        :param timestamp_ms: Absolute time in milliseconds for the timer to fire
        :param argument: Optional argument to provide when the timer fires.
        :param reference: Optional reference to use to manage this timer.
        """
        # We seed the reference with this intelligence ID to make it unique against all other intelligence modules.
        bot.set_organization_intelligence_alarm(botengine, timestamp_ms, self.intelligence_id, argument, self.intelligence_id + str(reference))

    def is_alarm_running(self, botengine, reference=""):
        """
        Check if a timer or alarm with the given reference is running
        :param botengine: BotEngine environment
        :param reference: Reference
        :return: True if timers or alarms with the given reference are running.
        """
        return botengine.is_timer_running(self.intelligence_id + str(reference))

    def cancel_alarms(self, botengine, reference=""):
        """
        Cancel alarms with the given reference
        :param botengine: BotEngine environment
        :param reference: Cancel all alarms with the given reference
        """
        # It's not a mistake that this is forwarding to `cancel_timers`.
        # They're all the same thing underneath, and this is a convenience method help to avoid confusion and questions.
        botengine.cancel_timers(self.intelligence_id + str(reference))

    def cancel_timer(self, botengine, reference=""):
        """
        Convenience method for cancel_timers() to maintain backward compatibility
        :param botengine: BotEngine environment
        :param reference: Cancel all timers with the given reference
        """
        self.cancel_timers(botengine, reference)

    def cancel_alarm(self, botengine, reference=""):
        """
        Convenience method for cancel_alarms() to maintain backward compatibility
        :param botengine: BotEngine environment
        :param reference: Cancel all alarms with the given reference
        """
        self.cancel_alarms(botengine, reference)

    # ===============================================================================
    # Private methods
    # ===============================================================================

    def _init_statistics(self):
        self.statistics = {
            "calls": 0,
            "time": 0,
        }
    
    # ===============================================================================
    # Built-in LLM usage tracking methods (like statistics).
    # ===============================================================================
    
    def _init_llm_usage(self):
        """
        Initialize LLM usage tracking - called automatically like _init_statistics()
        """
        self.llm_usage = {
            "requests": 0,              # Total number of LLM requests
            "prompt_tokens": 0,         # Total prompt tokens used
            "completion_tokens": 0,     # Total completion tokens used
            "total_tokens": 0,          # Total tokens (prompt + completion)
            "cost_usd": 0.0,            # Total cost in USD
            "by_provider": {},          # Usage broken down by provider
            "by_model": {},             # Usage broken down by model
        }
    
    def track_llm_usage(self, botengine, provider, model, usage, cost_usd=None):
        """
        Track LLM usage for this microservice
        
        This method is called automatically by the provider microservice before llm_response().
        Do not call this method directly - it's handled automatically.
        
        :param botengine: BotEngine environment
        :param provider: Provider name (e.g., "openai", "anthropic")
        :param model: Model name (e.g., "gpt-4", "claude-3")
        :param usage: Usage dict with "prompt_tokens", "completion_tokens", "total_tokens"
        :param cost_usd: Optional cost in USD if provided by the LLM response (most providers don't include this)
        """
        # Catch-all in case subclass forgets to call super().initialize()
        if not hasattr(self, "llm_usage"):
            self._init_llm_usage()
        
        self.llm_usage["requests"] += 1
        self.llm_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        self.llm_usage["completion_tokens"] += usage.get("completion_tokens", 0)
        self.llm_usage["total_tokens"] += usage.get("total_tokens", 0)
        
        # Only track cost if explicitly provided (most LLM providers don't include cost in response)
        if cost_usd is not None:
            self.llm_usage["cost_usd"] += cost_usd
        
        # Track by provider
        if provider not in self.llm_usage["by_provider"]:
            self.llm_usage["by_provider"][provider] = {
                "requests": 0,
                "total_tokens": 0,
                "cost_usd": 0.0
            }
        self.llm_usage["by_provider"][provider]["requests"] += 1
        self.llm_usage["by_provider"][provider]["total_tokens"] += usage.get("total_tokens", 0)
        if cost_usd is not None:
            self.llm_usage["by_provider"][provider]["cost_usd"] += cost_usd
        
        # Track by model
        if model not in self.llm_usage["by_model"]:
            self.llm_usage["by_model"][model] = {
                "requests": 0,
                "total_tokens": 0,
                "cost_usd": 0.0
            }
        self.llm_usage["by_model"][model]["requests"] += 1
        self.llm_usage["by_model"][model]["total_tokens"] += usage.get("total_tokens", 0)
        if cost_usd is not None:
            self.llm_usage["by_model"][model]["cost_usd"] += cost_usd
    
    def get_llm_usage(self, botengine):
        """
        Get LLM usage statistics for this microservice - just like get_statistics()
        
        :param botengine: BotEngine environment
        :return: Dict with usage statistics
        """
        if not hasattr(self, "llm_usage"):
            self._init_llm_usage()
        return self.llm_usage.copy()  # Return copy to prevent external modification
    
    def reset_llm_usage(self, botengine):
        """
        Reset LLM usage statistics - just like reset_statistics()
        
        :param botengine: BotEngine environment
        """
        self._init_llm_usage()
    
