"""
Created on January 2, 2026

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""

from intelligence.intelligence import Intelligence  # type: ignore

import utilities.utilities as utilities  # type: ignore
import properties  # type: ignore
import bundle  # type: ignore
import random
from signals.llm import (  # type: ignore
    PROVIDER_API_OPENAI_CHAT_COMPLETION,
    PROVIDER_API_OPENAI_RESPONSE,
)

# Default LLM model - can be overridden by organization property "LLM_OPENAI_DEFAULT_MODEL"
DEFAULT_LLM_MODEL = "gpt-4o-mini"

# Retry constants
LLM_TIMEOUT_S = 5 * 60  # 5 minutes timeout for LLM responses
MAX_RETRY_ATTEMPTS = 10  # Maximum retry attempts
MIN_BACKOFF_S = 30  # Minimum backoff delay (first retry)
MAX_BACKOFF_S = 300  # Maximum backoff delay (5 minutes)


class OrganizationLLMOpenAIMicroservice(Intelligence):
    """
    OpenAI LLM Provider Microservice for Organizations
    
    This microservice handles LLM requests for the OpenAI provider at the organization level.
    It listens for 'llm_chat_request' datastream messages and routes responses back to the 
    originating microservice using the intelligence_id.
    
    See com.ppc.Microservices/intelligence/llm_openai/location_llm_openai_microservice.py
    for full documentation on retry logic, timeout handling, and duplicate request management.
    """

    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent Organization object
        """
        Intelligence.__init__(self, botengine, parent)
        
        # Class variables for LLM request mapping (auto-purged after 30 minutes)
        # Maps reference -> (timestamp_ms, intelligence_id, argument)
        self._llm_request_mappings = {}
        
        # Pending request state for retry/timeout tracking
        self._pending_requests = {}

    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        pass

    def destroy(self, botengine):
        """
        This microservice is getting permanently deleted
        :param botengine: BotEngine environment
        """
        pass

    def new_version(self, botengine):
        """
        Upgraded to a new bot version
        :param botengine: BotEngine environment
        """
        # Initialize _pending_requests if it doesn't exist
        if not hasattr(self, '_pending_requests'):
            self._pending_requests = {}

    def timer_fired(self, botengine, argument):
        """
        The bot's intelligence timer fired
        :param botengine: BotEngine environment
        :param argument: Argument applied when setting the timer
        """
        if isinstance(argument, dict):
            timer_type = argument.get("type")
            reference = argument.get("reference")
            
            if timer_type == "llm_timeout" and reference:
                if reference in self._pending_requests:
                    botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                        "|timer_fired() LLM timeout for reference={}".format(reference)
                    )
                    self._handle_request_timeout(botengine, reference)
            elif timer_type == "llm_retry" and reference:
                self._handle_request_retry(botengine, reference)

    def datastream_updated(self, botengine, address, content):
        """
        Data Stream Message Received
        :param botengine: BotEngine environment
        :param address: Data Stream address
        :param content: Content of the message
        """
        if hasattr(self, address):
            getattr(self, address)(botengine, content)

    #===========================================================================
    # Data Stream Message Handlers
    #===========================================================================

    def llm_chat_request(self, botengine, content):
        """
        Handle LLM chat completion request
        
        This method receives LLM chat requests from other microservices and
        forwards them to the OpenAI API via botengine.
        
        :param botengine: BotEngine environment
        :param content: Request content containing:
            - intelligence_id: ID of originating microservice (for response routing)
            - reference: Reference for this request
            - argument: Optional argument to pass back with response
            - provider_api: Optional parameter to specify which provider API to use (e.g., "openai_chat_completion", "openai_response"). If None, provider default is used.
            
            Provider-specific parameters (e.g., for OpenAI):
            - messages: List of message dicts
            - model: Model name (optional, defaults to gpt-4)
            - max_tokens: Maximum tokens (optional)
            - temperature: Temperature (optional)
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info(">llm_chat_request() content={}".format(content))
        
        intelligence_id = content.get('intelligence_id')
        reference = content.get('reference')
        provider_api = content.get('provider_api', PROVIDER_API_OPENAI_CHAT_COMPLETION)
        
        # Validate required fields
        if intelligence_id is None:
            logger.error("<llm_chat_request() Missing intelligence_id")
            return
    
        if reference is None:
            logger.error("<llm_chat_request() Missing reference")
            return
        
        if provider_api == PROVIDER_API_OPENAI_CHAT_COMPLETION:
            # Requires "messages" parameter
            if content.get('messages') is None:
                logger.error("<llm_chat_request() Missing messages for Chat Completion")
                return
        elif provider_api == PROVIDER_API_OPENAI_RESPONSE:
            # Requires "input" parameter
            if content.get('input') is None:
                logger.error("<llm_chat_request() Missing input for Response API")
                return
        
        LLM_FEATURES_ALLOWED = properties.get_property(botengine, "LLM_FEATURES_ALLOWED", False)
        if not LLM_FEATURES_ALLOWED:
            logger.warning("<llm_chat_request() LLM features are not allowed by configuration. Request will be ignored.")
            return
        
        # Prepare OpenAI API request
        current_timestamp_ms = botengine.get_timestamp()
        
        # Duplicate request management with 10-second cooldown
        # This prevents runaway loops while allowing legitimate retries/re-runs
        if reference in self._pending_requests:
            existing_request = self._pending_requests[reference]
            existing_timestamp_ms = existing_request["timestamp_ms"]
            age_ms = current_timestamp_ms - existing_timestamp_ms
            age_seconds = age_ms / 1000.0
            
            if age_seconds < 10.0:
                # Request is too recent - enforce cooldown period
                # Update timestamp to reset the 10-second window (prevents rapid-fire requests)
                existing_request["timestamp_ms"] = current_timestamp_ms
                logger.warning(
                    utilities.Color.YELLOW +
                    "|llm_chat_request() Duplicate request BLOCKED for reference={} "
                    "(age: {:.1f}s < 10s cooldown). Timestamp reset to enforce cooldown.".format(reference, age_seconds) +
                    utilities.Color.END
                )
                return
            else:
                # Request is old enough - replace it
                # This handles cases where the previous request failed, timed out, or the bot restarted
                logger.warning(
                    utilities.Color.YELLOW +
                    "|llm_chat_request() Duplicate request ALLOWED for reference={} "
                    "(age: {:.1f}s >= 10s cooldown). Replacing previous request.".format(reference, age_seconds) +
                    utilities.Color.END
                )
                
                # Cancel any existing timers for the old request
                if existing_request.get("timeout_timer_set"):
                    try:
                        self.cancel_timer(botengine, f"llm_timeout_{reference}")
                        logger.info("|llm_chat_request() Cancelled old timeout timer for reference={}".format(reference))
                    except Exception as e:
                        logger.warning("|llm_chat_request() Error cancelling timeout timer: {}".format(e))
                
                # Also try to cancel retry timer (may or may not exist)
                try:
                    self.cancel_timer(botengine, f"llm_retry_{reference}")
                    logger.info("|llm_chat_request() Cancelled old retry timer for reference={}".format(reference))
                except Exception:
                    pass  # Retry timer may not exist, that's fine
                
                # Remove old request (will be replaced below with fresh request)
                del self._pending_requests[reference]
        
        # Build OpenAI parameters - model is REQUIRED by OpenAI API
        # See: https://app.peoplepowerco.com/cloud/apidocs/bots.html#tag/Bot-AI-APIs/operation/Send%20a%20request%20for%20chat%20completion
        # Try to get model from: 1) request, 2) organization property, 3) default constant
        model = content.get('model')
        if model is None:
            # Try organization property first
            model = properties.get_property(botengine, "LLM_OPENAI_DEFAULT_MODEL", False)
            if model is None:
                # Fall back to default constant
                model = DEFAULT_LLM_MODEL
                logger.debug("|llm_chat_request() Using default model: {}".format(model))
            else:
                logger.debug("|llm_chat_request() Using model from organization property: {}".format(model))
        else:
            logger.debug("|llm_chat_request() Using model from request: {}".format(model))
        openai_params = {
            k:v for k,v in content.items() if k not in [
                'intelligence_id',
                'reference',
                'argument',
                'provider_api',
            ]
        }
        openai_params["model"] = model
        openai_params["metadata"] = {
            "bundle_id": botengine.get_bundle_id(),
        }
        microservice = self.parent.get_microservice_by_id(botengine, intelligence_id)
        if microservice is not None:
            openai_params["metadata"]["microservice"] = type(microservice).__name__
        
        # Get OpenAI organization ID if configured
        openai_organization_id = self._get_openai_organization_id(botengine)
        
        # Store intelligence_id and reference mapping for response routing
        # Use reference as the key (which OpenAI will return in response)
        self._store_request_mapping(botengine, reference, intelligence_id, content.get('argument'))
        
        # Store pending request state for timeout/retry tracking
        self._pending_requests[reference] = {
            "timestamp_ms": current_timestamp_ms,
            "intelligence_id": intelligence_id,
            "argument": content.get('argument'),
            "provider_api": provider_api,
            "openai_params": openai_params,
            "openai_organization_id": openai_organization_id,
            "retry_attempts": 0,
            "timeout_timer_set": False
        }
        
        logger.info(
            "|llm_chat_request() Created new request for reference={} (retry_attempts=0)".format(reference)
        )
        
        # Make initial request to OpenAI
        self._make_openai_request(botengine, reference)
        
        logger.info("<llm_chat_request()")

    def openai(self, botengine, content):
        """
        Receive OpenAI API response and route back to originating microservice
        
        :param botengine: BotEngine environment
        :param content: OpenAI response
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        logger.info("")
        logger.info(utilities.Color.GREEN + utilities.Color.BOLD + "=" * 80 + utilities.Color.END)
        logger.info(utilities.Color.GREEN + utilities.Color.BOLD + "SUCCESS: ORG LLM_OPENAI Received 'openai' datastream response!" + utilities.Color.END)
        logger.info(utilities.Color.GREEN + utilities.Color.BOLD + "=" * 80 + utilities.Color.END)
        logger.info(utilities.Color.GREEN + ">openai() content keys={}".format(list(content.keys()) if isinstance(content, dict) else "N/A") + utilities.Color.END)
        
        # Extract reference from response
        reference = content.get('key')
        if reference is None:
            logger.error("<openai() Missing key in response")
            return
        
        # Cancel timeout timer and remove from pending requests
        if reference in self._pending_requests:
            pending = self._pending_requests[reference]
            if pending.get("timeout_timer_set"):
                self.cancel_timer(botengine, f"llm_timeout_{reference}")
            del self._pending_requests[reference]
        
        # Look up originating microservice
        intelligence_id, argument = self._get_request_mapping(botengine, reference)
        if intelligence_id is None:
            logger.warning("|openai() No mapping found for reference={}".format(reference))
            return
        
        # Add provider metadata
        response_with_metadata = content.copy()
        response_with_metadata["provider"] = "openai"
        
        # Route response back to originating microservice
        organization = self.parent
        microservice = organization.get_microservice_by_id(botengine, intelligence_id)
        if microservice is None:
            logger.error("|openai() Microservice with intelligence_id={} not found".format(intelligence_id))
            return
        
        # Track usage BEFORE calling llm_response()
        usage = content.get("usage", {})
        model = content.get("model", "unknown")
        cost_usd = content.get("cost_usd")
        
        try:
            if hasattr(microservice, "track_llm_usage"):
                microservice.track_llm_usage(botengine, "openai", model, usage, cost_usd=cost_usd)
        except Exception as e:
            logger.warning("|openai() Error tracking LLM usage: {}".format(e))
        
        # Call llm_response() on originating microservice
        if hasattr(microservice, "llm_response"):
            try:
                import time
                t = time.time()
                microservice.llm_response(botengine, response_with_metadata, reference, argument)
                if hasattr(microservice, "track_statistics"):
                    microservice.track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                import traceback
                logger.error("|openai() Error routing response to microservice: {} trace={}".format(e, traceback.format_exc()))
        else:
            logger.warning("|openai() Microservice {} does not implement llm_response()".format(microservice.__class__.__name__))
        
        logger.info("<openai()")

    def llm_openai_run_test(self, botengine, content):
        """
        LLM OpenAI test signal - allows triggering a request to OpenAI for testing purposes
        :param botengine: BotEngine environment
        :param content: Content of the message
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">llm_openai_run_test()"
        )
        if content is None:
            content = {}

        test_case = content.get("test_case", "")
        if test_case == "chat_completion":
            reference = content.get("reference", "test_reference_{}".format(random.randint(1000, 9999)))
            data = content.get("params", {})
            openai_organization_id = content.get("openai_organization_id", self._get_openai_organization_id(botengine))
            if "metadata" not in data:
                data["metadata"] = {}
            data["metadata"].update({
                "test_case": "chat_completion",
                "bundle_id": botengine.get_bundle_id(),
            })
            microservice = self.parent.get_microservice_by_id(botengine, self.intelligence_id)
            if microservice is not None:
                data["metadata"]["microservice"] = type(microservice).__name__
            response = botengine.send_request_for_chat_completion(
                key=reference,  # Use reference as key so we can match it in response
                data=data,
                openai_organization_id=openai_organization_id,
                openai_path=0
            )
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                "|llm_openai_run_test() Test chat completion request sent to OpenAI with reference={}. Immediate HTTP response: {}".format(reference, response)
            )
        if test_case == "response":
            reference = content.get("reference", "test_reference_{}".format(random.randint(1000, 9999)))
            data = content.get("params", {})
            openai_organization_id = content.get("openai_organization_id", self._get_openai_organization_id(botengine))
            if "metadata" not in data:
                data["metadata"] = {}
            data["metadata"].update({
                "test_case": "response",
                "bundle_id": botengine.get_bundle_id(),
            })
            microservice = self.parent.get_microservice_by_id(botengine, self.intelligence_id)
            if microservice is not None:
                data["metadata"]["microservice"] = type(microservice).__name__
            response = botengine.send_request_for_chat_completion(
                key=reference,  # Use reference as key so we can match it in response
                data=data,
                openai_organization_id=openai_organization_id,
                openai_path=1
            )
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                "|llm_openai_run_test() Test response request sent to OpenAI with reference={}. Immediate HTTP response: {}".format(reference, response)
            )
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<llm_openai_run_test()"
        )

    #===========================================================================
    # OpenAI Helpers
    #===========================================================================

    def _get_openai_organization_id(self, botengine):
        """
        Get OpenAI Organization ID from properties
        :param botengine: BotEngine environment
        :return: Organization ID or None
        """
        organization_id = None
        if properties.get_property(botengine, "OPEN_AI_ORGANIZATIONS", False) is not None:
            for cloud_address in properties.get_property(botengine, "OPEN_AI_ORGANIZATIONS", False):
                if cloud_address in bundle.CLOUD_ADDRESS:
                    organization_id = properties.get_property(botengine, "OPEN_AI_ORGANIZATIONS", False)[cloud_address]
                    break
        return organization_id
    
    def _store_request_mapping(self, botengine, reference, intelligence_id, argument):
        """Store mapping from reference to intelligence_id for response routing"""
        current_timestamp_ms = botengine.get_timestamp()
        purge_threshold_ms = current_timestamp_ms - (30 * 60 * 1000)  # 30 minutes
        
        # Auto-purge old entries
        self._llm_request_mappings = {
            ref: (ts, int_id, arg) 
            for ref, (ts, int_id, arg) in self._llm_request_mappings.items() 
            if ts > purge_threshold_ms
        }
        
        # Store new mapping
        self._llm_request_mappings[reference] = (current_timestamp_ms, intelligence_id, argument)
    
    def _get_request_mapping(self, botengine, reference):
        """Get stored mapping"""
        if reference in self._llm_request_mappings:
            timestamp_ms, intelligence_id, argument = self._llm_request_mappings[reference]
            # Check expiration
            if botengine.get_timestamp() - timestamp_ms > (30 * 60 * 1000):
                del self._llm_request_mappings[reference]
                return (None, None)
            return (intelligence_id, argument)
        return (None, None)
    
    def _make_openai_request(self, botengine, reference):
        """Make the actual OpenAI API request"""
        if reference not in self._pending_requests:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error("|_make_openai_request() No pending request for reference={}".format(reference))
            return
        
        pending = self._pending_requests[reference]
        openai_params = pending["openai_params"]
        openai_organization_id = pending["openai_organization_id"]
        retry_attempts = pending["retry_attempts"]
        
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info("|_make_openai_request() attempt={} reference={}".format(retry_attempts, reference))

        # Map provider_api to openai_path for the server API
        provider_api = pending.get("provider_api", PROVIDER_API_OPENAI_CHAT_COMPLETION)

        try:
            response = botengine.send_request_for_chat_completion(
                key=reference,
                data=openai_params,
                openai_organization_id=openai_organization_id,
                openai_path=provider_api
            )
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info("|_make_openai_request() Request sent (reference={}). Immediate response: {}".format(reference, response))
        except Exception as e:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error("|_make_openai_request() Exception: {}".format(e))
            self._handle_request_timeout(botengine, reference)
            return
        
        # Set timeout timer
        if not pending.get("timeout_timer_set"):
            self.start_timer_s(
                botengine,
                LLM_TIMEOUT_S,
                argument={"type": "llm_timeout", "reference": reference},
                reference=f"llm_timeout_{reference}"
            )
            pending["timeout_timer_set"] = True
    
    def _handle_request_timeout(self, botengine, reference):
        """Handle timeout when LLM response doesn't arrive"""
        if reference not in self._pending_requests:
            return
        
        pending = self._pending_requests[reference]
        pending["retry_attempts"] += 1
        retry_attempts = pending["retry_attempts"]
        
        botengine.get_logger(f"{__name__}.{__class__.__name__}").warning("|_handle_request_timeout() Timeout for reference={}, retry {}/{}".format(reference, retry_attempts, MAX_RETRY_ATTEMPTS))
        
        # Check max retries
        if retry_attempts >= MAX_RETRY_ATTEMPTS:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error("|_handle_request_timeout() Max retries exceeded for reference={}. Giving up.".format(reference))
            if pending.get("timeout_timer_set"):
                self.cancel_timer(botengine, f"llm_timeout_{reference}")
            del self._pending_requests[reference]
            return
        
        # Calculate exponential backoff with jitter
        base_delay_s = MIN_BACKOFF_S * (2 ** (retry_attempts - 1))
        delay_s = min(base_delay_s, MAX_BACKOFF_S)
        jitter_s = random.randint(0, min(30, delay_s // 2))
        delay_s = delay_s + jitter_s
        
        botengine.get_logger(f"{__name__}.{__class__.__name__}").warning("|_handle_request_timeout() Retry {} for reference={} in {}s".format(retry_attempts, reference, delay_s))
        
        pending["timeout_timer_set"] = False
        
        # Schedule retry
        self.start_timer_s(
            botengine,
            delay_s,
            argument={"type": "llm_retry", "reference": reference},
            reference=f"llm_retry_{reference}"
        )
    
    def _handle_request_retry(self, botengine, reference):
        """Handle scheduled retry"""
        if reference not in self._pending_requests:
            return
        
        pending = self._pending_requests[reference]
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info("|_handle_request_retry() Executing retry for reference={} (attempts={})".format(reference, pending["retry_attempts"]))
        
        # Retry the request
        self._make_openai_request(botengine, reference)


