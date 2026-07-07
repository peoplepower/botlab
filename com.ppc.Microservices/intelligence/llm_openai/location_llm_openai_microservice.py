"""
Created on December 25, 2025

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
    REUSABLE_PROMPTS_STATE_NAME,
)

# Default LLM model - can be overridden by organization property "LLM_OPENAI_DEFAULT_MODEL"
DEFAULT_LLM_MODEL = "gpt-4o-mini"

# Retry constants
LLM_TIMEOUT_S = 5 * 60  # 5 minutes timeout for LLM responses
MAX_RETRY_ATTEMPTS = 10  # Maximum retry attempts
MIN_BACKOFF_S = 30  # Minimum backoff delay (first retry) - 30 seconds to give server time to respond
MAX_BACKOFF_S = 300  # Maximum backoff delay (5 minutes)
# Exponential backoff: delays double each retry (30s, 60s, 120s, 240s, 300s max)
# with jitter to prevent thundering herd


class LocationLLMOpenAIMicroservice(Intelligence):
    """
    OpenAI LLM Provider Microservice
    
    This microservice handles LLM requests for the OpenAI provider.
    It listens for 'llm_chat_request' datastream messages and routes
    responses back to the originating microservice using the intelligence_id.
    
    **Retry Responsibility**: This LLM Provider microservice implements best-effort
    retry logic to ensure reliable delivery when server-side issues occur. This is
    the standard pattern for all LLM Provider microservices - they are responsible
    for handling transient failures, timeouts, and network issues.
    
    **Retry Best Practices** (implemented here):
    - Exponential backoff: Delays double with each retry (30s → 60s → 120s → 240s → 300s max)
    - Jitter: Random variance added to prevent thundering herd problems
    - Maximum cap: Backoff delays are capped at 5 minutes to prevent excessive wait times
    - Timeout windows: Each request attempt has a 5-minute timeout window
    - Maximum attempts: Up to 10 retry attempts before giving up
    
    **Duplicate Request Management** (10-second cooldown):
    - If duplicate request < 10 seconds old: BLOCKED (timestamp reset to enforce cooldown)
    - If duplicate request >= 10 seconds old: ALLOWED (replaces old request, cancels old timers)
    - This prevents runaway loops (which cost money) while allowing legitimate retries
    
    The microservice:
    - Receives LLM chat requests via 'llm_chat_request' datastream
    - Makes requests to OpenAI API via botengine.send_request_for_chat_completion()
    - Receives responses via 'openai' datastream
    - Routes responses back to originating microservice using intelligence_id
    - Automatically tracks token usage and costs
    - Implements retry/timeout logic for reliable delivery
    """

    def __init__(self, botengine, parent):
        """
        Instantiate this object
        :param parent: Parent object, either a location or a device object.
        """
        Intelligence.__init__(self, botengine, parent)
        
        # Class variables for LLM request mapping (auto-purged after 30 minutes)
        # Maps reference -> (timestamp_ms, intelligence_id, argument)
        self._llm_request_mappings = {}
        
        # Pending request state for retry/timeout tracking
        # Maps reference -> {
        #   "timestamp_ms": int,
        #   "intelligence_id": str,
        #   "argument": dict,
        #   "openai_params": dict,
        #   "openai_organization_id": str or None,
        #   "retry_attempts": int,
        #   "timeout_timer_set": bool
        # }
        self._pending_requests = {}

    def initialize(self, botengine):
        """
        Initialize
        :param botengine: BotEngine environment
        """
        pass

    def destroy(self, botengine):
        """
        This device or object is getting permanently deleted - it is no longer in the user's account.
        :param botengine: BotEngine environment
        """
        pass

    def new_version(self, botengine):
        """
        Upgraded to a new bot version
        :param botengine: BotEngine environment
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        
        # Initialize _pending_requests if it doesn't exist (for existing installations)
        if not hasattr(self, '_pending_requests'):
            self._pending_requests = {}
        
        # DEBUG: Log OPEN_AI_ORGANIZATIONS property to verify configuration
        logger.info("")
        logger.info(utilities.Color.CYAN + utilities.Color.BOLD + "=" * 80 + utilities.Color.END)
        logger.info(utilities.Color.CYAN + utilities.Color.BOLD + "DEBUG: Checking OpenAI Configuration" + utilities.Color.END)
        logger.info(utilities.Color.CYAN + utilities.Color.BOLD + "=" * 80 + utilities.Color.END)
        
        try:
            import bundle
            openai_orgs = properties.get_property(botengine, "OPEN_AI_ORGANIZATIONS", False)
            logger.info(utilities.Color.CYAN + "OPEN_AI_ORGANIZATIONS property: {}".format(openai_orgs) + utilities.Color.END)
            
            if openai_orgs is not None:
                logger.info(utilities.Color.CYAN + "CLOUD_ADDRESS from bundle: {}".format(bundle.CLOUD_ADDRESS) + utilities.Color.END)
                
                org_id_found = None
                for cloud_address in openai_orgs:
                    logger.info(utilities.Color.CYAN + "  Checking cloud_address: {} (in bundle? {})".format(
                        cloud_address, cloud_address in bundle.CLOUD_ADDRESS
                    ) + utilities.Color.END)
                    if cloud_address in bundle.CLOUD_ADDRESS:
                        org_id_found = openai_orgs[cloud_address]
                        break
                
                if org_id_found:
                    logger.info(utilities.Color.GREEN + utilities.Color.BOLD + "SUCCESS: OpenAI Organization ID found: {}".format(org_id_found) + utilities.Color.END)
                else:
                    logger.warning(utilities.Color.YELLOW + utilities.Color.BOLD + "WARNING: OPEN_AI_ORGANIZATIONS exists but no matching cloud_address found!" + utilities.Color.END)
            else:
                logger.warning(utilities.Color.YELLOW + utilities.Color.BOLD + "WARNING: OPEN_AI_ORGANIZATIONS property is None or not set!" + utilities.Color.END)
        except Exception as e:
            logger.error(utilities.Color.RED + utilities.Color.BOLD + "ERROR checking OpenAI config: {}".format(e) + utilities.Color.END)
        
        logger.info(utilities.Color.CYAN + utilities.Color.BOLD + "=" * 80 + utilities.Color.END)
        logger.info("")

        # Sync reusable prompts from organization properties to location state
        self._sync_reusable_prompts(botengine)

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
            logger.info("|llm_chat_request() Received chat completion request for intelligence_id={} reference={} provider_api={}".format(intelligence_id, reference, provider_api))
        elif provider_api == PROVIDER_API_OPENAI_RESPONSE:
            # Requires "input" parameter
            if content.get('input') is None:
                logger.error("<llm_chat_request() Missing input for Response API")
                return
            logger.info("|llm_chat_request() Received response API request for intelligence_id={} reference={} provider_api={}".format(intelligence_id, reference, provider_api))
        
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
            "location_id": f"{botengine.get_location_id()}",
            "organization_id": f"{botengine.get_organization_id()}",
            "test_location": f"{botengine.is_test_location()}",
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
        
        This method receives responses from the OpenAI API and routes them back
        to the originating microservice using the intelligence_id stored when
        the request was made.
        
        The response arrives asynchronously via the 'openai' datastream message
        after the server processes the LLM request.
        
        :param botengine: BotEngine environment
        :param content: OpenAI response containing:
            - key: Reference that was passed as key to send_request_for_chat_completion()
            - id: OpenAI response ID
            - model: Model used
            - choices: Response choices
            - usage: Token usage information
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        
        # DEBUG: Colored output to clearly show response received
        logger.info("")
        logger.info(utilities.Color.GREEN + utilities.Color.BOLD + "=" * 80 + utilities.Color.END)
        logger.info(utilities.Color.GREEN + utilities.Color.BOLD + "SUCCESS: LLM_OPENAI Received 'openai' datastream response!" + utilities.Color.END)
        logger.info(utilities.Color.GREEN + utilities.Color.BOLD + "=" * 80 + utilities.Color.END)
        logger.info(utilities.Color.GREEN + ">openai() content keys={}".format(list(content.keys()) if isinstance(content, dict) else "N/A") + utilities.Color.END)
        
        # Extract reference from response (OpenAI returns it as "key")
        reference = content.get('key')
        if reference is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error("<openai() Missing key in response")
            return
        
        # Cancel timeout timer and remove from pending requests (response received successfully)
        if reference in self._pending_requests:
            pending = self._pending_requests[reference]
            if pending.get("timeout_timer_set"):
                self.cancel_timer(botengine, f"llm_timeout_{reference}")
            del self._pending_requests[reference]
        
        # Look up originating microservice by intelligence_id
        intelligence_id, argument = self._get_request_mapping(botengine, reference)
        if intelligence_id is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "|openai() No mapping found for reference={}. Response may be orphaned.".format(reference)
            )
            return
        
        # Add provider metadata to response
        response_with_metadata = content.copy()
        response_with_metadata["provider"] = "openai"
        
        # Route response back to originating microservice (just like timer system)
        location = self.parent
        microservice = location.get_microservice_by_id(botengine, intelligence_id)
        if microservice is None:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                "|openai() Microservice with intelligence_id={} not found. Cannot route response.".format(intelligence_id)
            )
            return
        
        # Track usage BEFORE calling llm_response() so it always happens automatically
        usage = content.get("usage", {})
        model = content.get("model", "unknown")
        provider = "openai"
        
        # Extract cost if provided in response (OpenAI doesn't provide this, but other providers might)
        cost_usd = content.get("cost_usd")
        
        try:
            microservice.track_llm_usage(botengine, provider, model, usage, cost_usd=cost_usd)
        except Exception as e:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "|openai() Error tracking LLM usage: {}".format(e)
            )
        
        # Now call llm_response() on the originating microservice
        if hasattr(microservice, "llm_response"):
            try:
                import time
                t = time.time()
                microservice.llm_response(botengine, response_with_metadata, reference, argument)
                microservice.track_statistics(botengine, (time.time() - t) * 1000)
            except Exception as e:
                import traceback
                botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                    "|openai() Error routing response to microservice: {} trace={}".format(e, traceback.format_exc())
                )
        else:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "|openai() Microservice {} does not implement llm_response() method.".format(microservice.__class__.__name__)
            )
        
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info("<openai()")
    
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

    def _sync_reusable_prompts(self, botengine):
        """
        Check the OPENAI_REUSABLE_PROMPTS feature flag and manage the location state.

        When the feature flag is True, the ``openai_reusable_prompts`` state is
        preserved (individual microservices populate it via the
        ``llm_reusable_prompt_updated`` signal).  When the flag is False or
        absent the state is cleared so no service accidentally picks up stale
        prompt IDs.

        :param botengine: BotEngine environment
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")
        enabled = properties.get_property(botengine, "OPENAI_REUSABLE_PROMPTS", False)

        if not enabled:
            # Feature disabled — wipe any existing mapping
            existing = botengine.get_state(REUSABLE_PROMPTS_STATE_NAME)
            if existing is not None:
                self.parent.delete_location_property_separately(botengine, REUSABLE_PROMPTS_STATE_NAME)
                logger.info("|_sync_reusable_prompts() Feature disabled — cleared openai_reusable_prompts")
        else:
            logger.info("|_sync_reusable_prompts() Feature enabled")

    # ------------------------------------------------------------------
    # Reusable Prompt signal handler
    # ------------------------------------------------------------------

    def llm_reusable_prompt_updated(self, botengine, content):
        """
        Handle add / update / remove of a reusable prompt mapping.

        Microservices send this signal (via ``signals.llm.update_reusable_prompt``
        or ``signals.llm.remove_reusable_prompt``) to register their OpenAI
        Reusable Prompt IDs.  The mapping is persisted with
        ``set_location_property_separately`` so it can grow without bloating
        the main location_properties dict.

        Content for add/update::

            {
                "prompt_key": "report_section_content_daily",
                "prompt_id": "pmpt_abc123",
                "version": "1",
                "variables": ["current_date_str", "section_title"]
            }

        Content for remove::

            {
                "prompt_key": "report_section_content_daily",
                "deleted": True
            }

        :param botengine: BotEngine environment
        :param content: Signal content dict
        """
        logger = botengine.get_logger(f"{__name__}.{__class__.__name__}")

        # Guard: feature must be enabled
        enabled = properties.get_property(botengine, "OPENAI_REUSABLE_PROMPTS", False)
        if not enabled:
            logger.warning("|llm_reusable_prompt_updated() Ignoring — OPENAI_REUSABLE_PROMPTS feature flag is disabled")
            return

        prompt_key = content.get("prompt_key")
        if not prompt_key:
            logger.error("|llm_reusable_prompt_updated() Missing prompt_key")
            return

        # Load current mapping (stored separately)
        mapping = botengine.get_state(REUSABLE_PROMPTS_STATE_NAME) or {}

        if content.get("deleted"):
            if prompt_key in mapping:
                del mapping[prompt_key]
                logger.info("|llm_reusable_prompt_updated() Removed prompt '{}'".format(prompt_key))
            else:
                logger.debug("|llm_reusable_prompt_updated() Prompt '{}' not found — nothing to remove".format(prompt_key))
        else:
            prompt_id = content.get("prompt_id")
            if not prompt_id:
                logger.error("|llm_reusable_prompt_updated() Missing prompt_id for key '{}'".format(prompt_key))
                return

            mapping[prompt_key] = {
                "id": prompt_id,
                "version": content.get("version"),
                "variables": content.get("variables", []),
            }
            mapping[prompt_key] = {k:v for k,v in mapping[prompt_key].items() if v is not None}  # Remove None values for cleanliness
            logger.info("|llm_reusable_prompt_updated() Registered prompt '{}' => {} [{}]".format(prompt_key, prompt_id, content.get("version", "current")))

        # Persist
        self.parent.set_location_property_separately(
            botengine,
            REUSABLE_PROMPTS_STATE_NAME,
            mapping,
            overwrite=True,
            track=False,
        )

    def _get_openai_organization_id(self, botengine):
        """
        Attempt to return the OpenAI Organization ID from properties.
        
        :param botengine: BotEngine environment
        :return: Organization ID, or None if not configured
        """
        organization_id = None
        if properties.get_property(botengine, "OPEN_AI_ORGANIZATIONS", False) is not None:
            for cloud_address in properties.get_property(botengine, "OPEN_AI_ORGANIZATIONS", False):
                if cloud_address in bundle.CLOUD_ADDRESS:
                    organization_id = properties.get_property(botengine, "OPEN_AI_ORGANIZATIONS", False)[cloud_address]
                    break
        
        return organization_id
    
    def _store_request_mapping(self, botengine, reference, intelligence_id, argument):
        """
        Store mapping from reference to intelligence_id and argument for response routing
        
        :param botengine: BotEngine environment
        :param reference: Request reference
        :param intelligence_id: Originating microservice intelligence_id
        :param argument: Optional argument to pass back
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            ">_store_request_mapping() Storing mapping for reference={} intelligence_id={}".format(reference, intelligence_id)
        )
        current_timestamp_ms = botengine.get_timestamp()
        purge_threshold_ms = current_timestamp_ms - (30 * 60 * 1000)  # 30 minutes
        
        # Remove old entries
        self._llm_request_mappings = {
            ref: (ts, int_id, arg) 
            for ref, (ts, int_id, arg) in self._llm_request_mappings.items() 
            if ts > purge_threshold_ms
        }

        self._llm_request_mappings[reference] = (current_timestamp_ms, intelligence_id, argument)
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "<_store_request_mapping()"
        )
    
    def _get_request_mapping(self, botengine, reference):
        """
        Get stored mapping from reference to intelligence_id and argument
        
        :param botengine: BotEngine environment
        :param reference: Request reference
        :return: Tuple of (intelligence_id, argument) or (None, None) if not found
        """
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|_get_request_mapping() Retrieving mapping for reference={}".format(reference)
        )
        botengine.get_logger(f"{__name__}.{__class__.__name__}").debug(
            "|_get_request_mapping() Current mappings: {}".format(self._llm_request_mappings)
        )
        try:
            timestamp_ms, intelligence_id, argument = self._llm_request_mappings.pop(reference)
            # Check if expired (older than 30 minutes) - this is a safety check to prevent stale mappings from lingering indefinitely
            current_timestamp_ms = botengine.get_timestamp()
            if current_timestamp_ms - timestamp_ms > (30 * 60 * 1000):
                botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                    "|_get_request_mapping() Mapping for reference={} has expired after more than 30 minutes. Removing.".format(reference)
                )
                return (None, None)
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                "<_get_request_mapping() Found mapping for reference={}: intelligence_id={}".format(reference, intelligence_id)
            )
            return (intelligence_id, argument)
        except Exception as e:
            import traceback
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                "|_get_request_mapping() No mapping found for reference={}. e={}; trace={}".format(reference, e, traceback.format_exc())
            )
        return (None, None)
    
    def _make_openai_request(self, botengine, reference):
        """
        Make the actual OpenAI API request
        
        :param botengine: BotEngine environment
        :param reference: Request reference
        """
        if reference not in self._pending_requests:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                "|_make_openai_request() No pending request found for reference={}".format(reference)
            )
            return
        
        pending = self._pending_requests[reference]
        openai_params = pending["openai_params"]
        openai_organization_id = pending["openai_organization_id"]
        intelligence_id = pending["intelligence_id"]
        retry_attempts = pending["retry_attempts"]
        
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|_make_openai_request() attempt={} organization_id={} reference={} intelligence_id={}".format(
                retry_attempts, openai_organization_id, reference, intelligence_id
            )
        )
        
        # Map provider_api to openai_path for the server API
        # PROVIDER_API_OPENAI_CHAT_COMPLETION (0) = openai_path 0
        # PROVIDER_API_OPENAI_RESPONSE (1) = openai_path 1
        provider_api = pending.get("provider_api", PROVIDER_API_OPENAI_CHAT_COMPLETION)

        try:
            response = botengine.send_request_for_chat_completion(
                key=reference,  # Use reference as key so we can match it in response
                data=openai_params,
                openai_organization_id=openai_organization_id,
                openai_path=provider_api
            )
            
            # Log the immediate response (usually just an acknowledgment, not the actual LLM response)
            # The actual LLM response will arrive later via the 'openai' datastream message
            botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                "|_make_openai_request() Request sent to server (reference={}). "
                "The LLM response will arrive asynchronously via the 'openai' datastream. "
                "Immediate HTTP response: {}".format(reference, response)
            )
            
        except Exception as e:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                "|_make_openai_request() Exception sending request: {}".format(e)
            )
            # Treat immediate exception as a timeout - will retry
            self._handle_request_timeout(botengine, reference)
            return
        
        # Set timeout timer to check if response arrives
        if not pending.get("timeout_timer_set"):
            self.start_timer(
                botengine,
                LLM_TIMEOUT_S,
                argument={"type": "llm_timeout", "reference": reference},
                reference=f"llm_timeout_{reference}"
            )
            pending["timeout_timer_set"] = True
    
    def _handle_request_timeout(self, botengine, reference):
        """
        Handle timeout when LLM response doesn't arrive
        
        :param botengine: BotEngine environment
        :param reference: Request reference
        """
        if reference not in self._pending_requests:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "|_handle_request_timeout() No pending request found for reference={}".format(reference)
            )
            return
        
        pending = self._pending_requests[reference]
        pending["retry_attempts"] += 1
        retry_attempts = pending["retry_attempts"]
        
        botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
            "|_handle_request_timeout() Timeout detected for reference={}, retry attempt {}/{}".format(
                reference, retry_attempts, MAX_RETRY_ATTEMPTS
            )
        )
        
        # Check if we've exceeded max retries
        if retry_attempts >= MAX_RETRY_ATTEMPTS:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                "|_handle_request_timeout() Max retries ({}) exceeded for reference={}. Giving up. "
                "The server may not be processing requests or sending responses via the 'openai' datastream.".format(
                    MAX_RETRY_ATTEMPTS, reference
                )
            )

            # Extract routing info BEFORE cleanup
            intelligence_id = pending.get("intelligence_id")
            argument = pending.get("argument")

            # Clean up timers
            if pending.get("timeout_timer_set"):
                self.cancel_timer(botengine, f"llm_timeout_{reference}")

            # Clean up pending request
            del self._pending_requests[reference]

            # Notify originating microservice of failure so it can fall back to non-LLM behavior
            if intelligence_id:
                microservice = self.parent.get_microservice_by_id(botengine, intelligence_id)
                if microservice and hasattr(microservice, "llm_response"):
                    try:
                        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
                            "|_handle_request_timeout() Sending failure response to {} for reference={}".format(
                                microservice.__class__.__name__, reference
                            )
                        )
                        # Send None response - the calling microservice should handle this as a failure
                        # and fall back to non-LLM functionality
                        microservice.llm_response(botengine, None, reference, argument)
                    except Exception as e:
                        botengine.get_logger(f"{__name__}.{__class__.__name__}").error(
                            "|_handle_request_timeout() Error sending failure response: {}".format(e)
                        )

            return
        
        # Calculate exponential backoff delay: doubles each retry up to MAX_BACKOFF_S
        # Retry 1: 30s, Retry 2: 60s, Retry 3: 120s, Retry 4: 240s, Retry 5+: 300s (capped)
        base_delay_s = MIN_BACKOFF_S * (2 ** (retry_attempts - 1))
        delay_s = min(base_delay_s, MAX_BACKOFF_S)
        # Add jitter (up to 50% of delay, max 30s) to prevent thundering herd
        jitter_s = random.randint(0, min(30, delay_s // 2))
        delay_s = delay_s + jitter_s
        
        botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
            "|_handle_request_timeout() Retry attempt {} for reference={} in {} seconds".format(
                retry_attempts, reference, delay_s
            )
        )
        
        # Reset timeout timer flag (will be set again in _make_openai_request)
        pending["timeout_timer_set"] = False
        
        # Schedule retry
        self.start_timer(
            botengine,
            delay_s,
            argument={"type": "llm_retry", "reference": reference},
            reference=f"llm_retry_{reference}"
        )
    
    def _handle_request_retry(self, botengine, reference):
        """
        Handle scheduled retry of an LLM request
        
        :param botengine: BotEngine environment
        :param reference: Request reference
        """
        if reference not in self._pending_requests:
            botengine.get_logger(f"{__name__}.{__class__.__name__}").warning(
                "|_handle_request_retry() No pending request found for reference={}".format(reference)
            )
            return
        
        pending = self._pending_requests[reference]
        retry_attempts = pending["retry_attempts"]
        botengine.get_logger(f"{__name__}.{__class__.__name__}").info(
            "|_handle_request_retry() Executing retry for reference={} (retry_attempts={})".format(
                reference, retry_attempts
            )
        )
        
        # Retry the request
        self._make_openai_request(botengine, reference)

