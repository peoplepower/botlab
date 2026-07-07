"""
Created on December 25, 2025

This file is subject to the terms and conditions defined in the
file 'LICENSE.txt', which is part of this source code package.

@author: David Moss
"""

PROVIDER_API_OPENAI_CHAT_COMPLETION = 0
PROVIDER_API_OPENAI_RESPONSE = 1

def chat(botengine, organization, intelligence_id, reference, argument=None, provider_api=None, **kwargs):
    """
    Send LLM chat completion request to an LLM provider microservice.
    
    This signal function distributes an LLM chat request to provider microservices
    that are listening for "llm_chat_request" datastream messages. The provider
    microservice will handle the actual LLM API call and route the response back
    to the originating microservice using the intelligence_id.
    
    **LLM Provider Responsibility**: It is the responsibility of the LLM Provider
    microservice (e.g., OrganizationLLMOpenAIMicroservice) to implement best-effort
    retry logic when server-side issues occur. This ensures reliable delivery
    at the infrastructure level, so microservices using llm_chat() don't need to
    implement their own retry logic.
    
    **Retry Best Practices** (should be implemented by LLM Provider microservices):
    - Exponential backoff: Delays should double with each retry (e.g., 10s → 20s → 40s → 80s)
    - Maximum cap: Backoff delays should be capped (e.g., 5 minutes) to prevent excessive waits
    - Jitter: Add random variance to prevent thundering herd problems
    - Timeout windows: Each request attempt should have a reasonable timeout (e.g., 5 minutes)
    - Maximum attempts: Set a reasonable limit (e.g., 10 attempts) before giving up
    - Cleanup: Properly cancel timers and clean up state when responses arrive or max retries exceeded
    
    Kwargs can include provider-specific parameters such as:
    - model: Specify the LLM model to use (e.g., "gpt-4", "claude-3"). If not provided, the provider will use a default model.
    - max_tokens: Maximum tokens to generate. If None, uses model/provider default (recommended).
    - temperature: Sampling temperature for response variability. If None, uses model/provider default.

    Available provider APIs
    - openai: Chat Completion: https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create
    - openai: Response API: https://developers.openai.com/api/reference/resources/responses/methods/create

    **max_tokens Parameter**: 
    When max_tokens is None (default), the provider microservice will use the model's default
    behavior, which typically allows the model to generate up to the maximum available tokens
    based on the input prompt length and model context window. This is often the most appropriate
    choice as it adapts to different use cases automatically.
    
    For specific use cases, explicitly specify max_tokens based on expected response length:
    - Short answers/classifications: 50-200 tokens
    - Paragraph summaries: 200-500 tokens
    - Multi-paragraph narratives: 500-2000 tokens
    - Long-form content: 2000+ tokens (ensure model supports this)
    
    Note: Each model has maximum context windows (e.g., GPT-4: 8,192 tokens, GPT-4-32k: 32,768).
    The max_tokens value cannot exceed (context_window - input_tokens). Providers should validate
    this and cap max_tokens appropriately if needed.
    
    The system validates that exactly one LLM provider microservice is available.
    If zero providers are found, a critical warning is logged. If multiple providers
    are found, a critical error is logged to prevent duplicate requests.
    
    :param botengine: BotEngine environment
    :param organization: Organization object
    :param intelligence_id: Intelligence ID of the originating microservice (for response routing)
    :param messages: List of message dicts [{"role": "user", "content": "..."}]
    :param reference: Reference to identify this request (like timer reference)
    :param argument: Optional argument to pass back with the response
    :param provider_api: Optional parameter to specify which provider API to use (e.g., "openai_chat_completion", "openai_response"). If None, provider default is used.
    :param kwargs: Additional provider-specific parameters
    """
    botengine.get_logger(f"{__name__}").debug(">chat() intelligence_id={} reference={} provider_api={} model={}".format(intelligence_id, reference, provider_api, kwargs.get("model")))
    
    # Prepare request body
    body = {
        "intelligence_id": intelligence_id,  # For response routing
        "reference": reference,
        "argument": argument,
        "provider_api": provider_api,
    }
    
    # Add any additional kwargs
    body.update(kwargs)
    
    # Send datastream message to LLM provider microservice
    organization.distribute_datastream_message(
        botengine,
        "llm_chat_request",
        body,
        internal=True,
        external=False
    )
    
    botengine.get_logger(f"{__name__}").debug("<chat()")


