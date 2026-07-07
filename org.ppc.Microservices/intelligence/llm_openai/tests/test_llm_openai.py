import logging
from unittest.mock import patch

from intelligence.intelligence import Intelligence  # type: ignore
from intelligence.llm_openai.organization_llm_openai_microservice import (
    MAX_RETRY_ATTEMPTS,
)
from signals.llm import (  # type: ignore
    PROVIDER_API_OPENAI_CHAT_COMPLETION,
    PROVIDER_API_OPENAI_RESPONSE,
)
from organization.organization import Organization  # type: ignore

from botengine_pytest import BotEnginePyTest

# Module path for patching the logger
_MUT_LOGGER = "intelligence.llm_openai.organization_llm_openai_microservice.OrganizationLLMOpenAIMicroservice"


class MockRequestingMicroservice(Intelligence):
    """Mock microservice that requests LLM completions and receives responses."""

    def __init__(self, botengine, parent):
        Intelligence.__init__(self, botengine, parent)
        self.last_response = None
        self.last_reference = None
        self.last_argument = None
        self.llm_response_count = 0
        self.last_usage_provider = None
        self.last_usage_model = None
        self.last_usage_data = None
        self.last_usage_cost = None

    def initialize(self, botengine):
        pass

    def new_version(self, botengine):
        pass

    def llm_response(self, botengine, response, reference, argument):
        self.last_response = response
        self.last_reference = reference
        self.last_argument = argument
        self.llm_response_count += 1

    def track_llm_usage(self, botengine, provider, model, usage, cost_usd=None):
        self.last_usage_provider = provider
        self.last_usage_model = model
        self.last_usage_data = usage
        self.last_usage_cost = cost_usd

    def track_statistics(self, botengine, ms):
        pass


class TestLLMOpenAIMicroservice:
    def _setup(self):
        """Common setup for tests."""
        botengine = BotEnginePyTest({})
        botengine.reset()

        organization = Organization(botengine, 0)
        organization.new_version(botengine)
        organization.initialize(botengine)

        mut = organization.intelligence_modules[
            "intelligence.llm_openai.organization_llm_openai_microservice"
        ]
        return botengine, organization, mut

    def _add_mock_microservice(self, botengine, organization):
        """Add a mock requesting microservice to the organization."""
        mock = MockRequestingMicroservice(botengine, organization)
        module_key = "intelligence.mock_requesting_microservice"
        organization.intelligence_modules[module_key] = mock
        return mock

    def _make_chat_request_content(
        self, intelligence_id, reference="ref_1", messages=None, **kwargs
    ):
        """Build a valid llm_chat_request content dict (Chat Completion API)."""
        content = {
            "intelligence_id": intelligence_id,
            "reference": reference,
            "messages": messages or [{"role": "user", "content": "Hello"}],
        }
        content.update(kwargs)
        return content

    def _make_response_api_content(
        self, intelligence_id, reference="ref_1", input_text=None, **kwargs
    ):
        """Build a valid llm_chat_request content dict for the Response API."""
        content = {
            "intelligence_id": intelligence_id,
            "reference": reference,
            "provider_api": PROVIDER_API_OPENAI_RESPONSE,
            "input": input_text or "Hello",
        }
        content.update(kwargs)
        return content

    # ===========================================================================
    # Initialization
    # ===========================================================================

    def test_llm_openai_initialization(self):
        """Should initialize with empty mappings and pending requests."""
        botengine, organization, mut = self._setup()
        assert mut is not None
        assert mut._llm_request_mappings == {}
        assert mut._pending_requests == {}

    def test_new_version_initializes_pending_requests(self):
        """new_version() should initialize _pending_requests if missing."""
        botengine, organization, mut = self._setup()

        # Simulate an older version that lacks _pending_requests
        if hasattr(mut, "_pending_requests"):
            delattr(mut, "_pending_requests")

        mut.new_version(botengine)
        assert mut._pending_requests == {}

    # ===========================================================================
    # Validation
    # ===========================================================================

    def test_llm_chat_request_missing_intelligence_id(self):
        """Request without intelligence_id should be rejected."""
        botengine, organization, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        content = {
            "reference": "ref_1",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        with patch.object(logger, "error") as mock_error:
            mut.llm_chat_request(botengine, content)
            mock_error.assert_called_once()

        assert len(mut._pending_requests) == 0
        assert len(mut._llm_request_mappings) == 0

    def test_llm_chat_request_missing_reference(self):
        """Request without reference should be rejected."""
        botengine, organization, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        content = {
            "intelligence_id": "some_id",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        with patch.object(logger, "error") as mock_error:
            mut.llm_chat_request(botengine, content)
            mock_error.assert_called_once()

        assert len(mut._pending_requests) == 0
        assert len(mut._llm_request_mappings) == 0

    def test_llm_chat_request_missing_messages(self):
        """Request without messages should be rejected."""
        botengine, organization, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        content = {
            "intelligence_id": "some_id",
            "reference": "ref_1",
        }
        with patch.object(logger, "error") as mock_error:
            mut.llm_chat_request(botengine, content)
            mock_error.assert_called_once()

        assert len(mut._pending_requests) == 0
        assert len(mut._llm_request_mappings) == 0

    # ===========================================================================
    # Valid request processing
    # ===========================================================================

    def test_llm_chat_request_valid(self):
        """Valid request should store mapping and pending request."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        # Should store request mapping
        assert "ref_1" in mut._llm_request_mappings
        ts, int_id, arg = mut._llm_request_mappings["ref_1"]
        assert int_id == mock.intelligence_id

        # Should store pending request
        assert "ref_1" in mut._pending_requests
        pending = mut._pending_requests["ref_1"]
        assert pending["intelligence_id"] == mock.intelligence_id
        assert pending["retry_attempts"] == 0
        assert pending["openai_params"]["messages"] == [
            {"role": "user", "content": "Hello"}
        ]

    def test_llm_chat_request_default_model(self):
        """Without model in request or org property, should use DEFAULT_LLM_MODEL."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        pending = mut._pending_requests["ref_1"]
        assert pending["openai_params"]["model"] == "gpt-4o-mini"

    def test_llm_chat_request_model_from_request(self):
        """Model specified in request should override default."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id, model="gpt-4o")
        mut.llm_chat_request(botengine, content)

        pending = mut._pending_requests["ref_1"]
        assert pending["openai_params"]["model"] == "gpt-4o"

    def test_llm_chat_request_model_from_org_property(self):
        """Model from organization property should override default when not in request."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        botengine.organization_properties["LLM_OPENAI_DEFAULT_MODEL"] = "gpt-4-turbo"

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        pending = mut._pending_requests["ref_1"]
        assert pending["openai_params"]["model"] == "gpt-4-turbo"

    def test_llm_chat_request_model_request_overrides_org_property(self):
        """Model in request should override organization property."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        botengine.organization_properties["LLM_OPENAI_DEFAULT_MODEL"] = "gpt-4-turbo"

        content = self._make_chat_request_content(mock.intelligence_id, model="gpt-4o")
        mut.llm_chat_request(botengine, content)

        pending = mut._pending_requests["ref_1"]
        assert pending["openai_params"]["model"] == "gpt-4o"

    def test_llm_chat_request_optional_params(self):
        """Optional parameters (max_tokens, temperature) should be passed through."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(
            mock.intelligence_id,
            max_tokens=1000,
            temperature=0.5,
        )
        mut.llm_chat_request(botengine, content)

        pending = mut._pending_requests["ref_1"]
        assert pending["openai_params"]["max_tokens"] == 1000
        assert pending["openai_params"]["temperature"] == 0.5

    def test_llm_chat_request_extra_kwargs(self):
        """Extra kwargs should be passed through to openai_params."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(
            mock.intelligence_id,
            response_format={"type": "json_object"},
        )
        mut.llm_chat_request(botengine, content)

        pending = mut._pending_requests["ref_1"]
        assert pending["openai_params"]["response_format"] == {"type": "json_object"}

    def test_llm_chat_request_stores_argument(self):
        """Argument from request content should be stored in mapping and pending request."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(
            mock.intelligence_id,
            argument={"task": "summarize"},
        )
        mut.llm_chat_request(botengine, content)

        # Check mapping
        ts, int_id, arg = mut._llm_request_mappings["ref_1"]
        assert arg == {"task": "summarize"}

        # Check pending request
        pending = mut._pending_requests["ref_1"]
        assert pending["argument"] == {"task": "summarize"}

    # ===========================================================================
    # Duplicate request management
    # ===========================================================================

    def test_duplicate_request_within_cooldown_blocked(self):
        """Duplicate request within 10-second cooldown should be blocked."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)
        assert "ref_1" in mut._pending_requests

        # Send duplicate 5 seconds later (within 10s cooldown)
        botengine.set_timestamp(botengine.get_timestamp() + 5000)
        mut.llm_chat_request(botengine, content)

        # Pending request should still exist with only 0 retry attempts
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 0

    def test_duplicate_request_after_cooldown_allowed(self):
        """Duplicate request after 10-second cooldown should be allowed (replaces old request)."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        original_timestamp = mut._pending_requests["ref_1"]["timestamp_ms"]
        assert original_timestamp == botengine.get_timestamp()

        # Send duplicate 11 seconds later (after 10s cooldown)
        new_time = botengine.get_timestamp() + 11000
        botengine.set_timestamp(new_time)
        mut.llm_chat_request(botengine, content)

        # Should have been replaced with new timestamp
        assert mut._pending_requests["ref_1"]["timestamp_ms"] == new_time
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 0

    # ===========================================================================
    # Datastream routing
    # ===========================================================================

    def test_datastream_updated_routes_llm_chat_request(self):
        """datastream_updated should route to llm_chat_request method."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.datastream_updated(botengine, "llm_chat_request", content)

        assert "ref_1" in mut._pending_requests

    def test_datastream_updated_routes_openai(self):
        """datastream_updated should route to openai method."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        # First, make a request so there's a mapping
        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        # Simulate OpenAI response via datastream
        response = {
            "key": "ref_1",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "choices": [{"message": {"content": "Hello!"}}],
        }
        mut.datastream_updated(botengine, "openai", response)

        assert mock.llm_response_count == 1

    def test_datastream_updated_unknown_address(self):
        """datastream_updated with unknown address should not raise."""
        botengine, organization, mut = self._setup()
        # Should not raise
        mut.datastream_updated(botengine, "unknown_address", {})

    # ===========================================================================
    # OpenAI response routing
    # ===========================================================================

    def test_openai_response_routes_to_microservice(self):
        """OpenAI response should be routed back to the originating microservice."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        # Make request
        content = self._make_chat_request_content(
            mock.intelligence_id,
            argument={"task": "test"},
        )
        mut.llm_chat_request(botengine, content)

        # Simulate response
        response = {
            "key": "ref_1",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "choices": [{"message": {"content": "Response text"}}],
        }
        mut.openai(botengine, response)

        # Verify response routing
        assert mock.llm_response_count == 1
        assert mock.last_reference == "ref_1"
        assert mock.last_argument == {"task": "test"}
        assert mock.last_response["provider"] == "openai"
        assert mock.last_response["choices"][0]["message"]["content"] == "Response text"

    def test_openai_response_tracks_usage(self):
        """OpenAI response should track LLM usage on the originating microservice."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        response = {
            "key": "ref_1",
            "model": "gpt-4o-mini",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
            "cost_usd": 0.005,
        }
        mut.openai(botengine, response)

        assert mock.last_usage_provider == "openai"
        assert mock.last_usage_model == "gpt-4o-mini"
        assert mock.last_usage_data == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        assert mock.last_usage_cost == 0.005

    def test_openai_response_cleans_pending_request(self):
        """Successful response should remove the pending request."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)
        assert "ref_1" in mut._pending_requests

        response = {"key": "ref_1", "model": "gpt-4o-mini", "usage": {}}
        mut.openai(botengine, response)

        assert "ref_1" not in mut._pending_requests

    def test_openai_response_missing_key(self):
        """Response without key should be rejected."""
        botengine, organization, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        response = {"model": "gpt-4o-mini", "usage": {}}
        with patch.object(logger, "error") as mock_error:
            mut.openai(botengine, response)
            mock_error.assert_called_once()

    def test_openai_response_no_mapping(self):
        """Response with no stored mapping should be handled gracefully."""
        botengine, organization, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        response = {"key": "unknown_ref", "model": "gpt-4o-mini", "usage": {}}
        with patch.object(logger, "warning") as mock_warning:
            mut.openai(botengine, response)
            mock_warning.assert_called()

    def test_openai_response_microservice_not_found(self):
        """Response for a removed microservice should be handled gracefully."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)
        intelligence_id = mock.intelligence_id
        logger = logging.getLogger(_MUT_LOGGER)

        content = self._make_chat_request_content(intelligence_id)
        mut.llm_chat_request(botengine, content)

        # Remove the mock microservice
        del organization.intelligence_modules[
            "intelligence.mock_requesting_microservice"
        ]

        response = {"key": "ref_1", "model": "gpt-4o-mini", "usage": {}}
        with patch.object(logger, "error") as mock_error:
            mut.openai(botengine, response)
            mock_error.assert_called_once()

    # ===========================================================================
    # Timer handling
    # ===========================================================================

    def test_timer_fired_timeout(self):
        """Timeout timer should trigger retry scheduling."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        # Simulate timeout timer firing
        mut.timer_fired(botengine, {"type": "llm_timeout", "reference": "ref_1"})

        # Should have incremented retry attempts
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 1

    def test_timer_fired_retry(self):
        """Retry timer should re-attempt the OpenAI request."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        # Mark as timed out first
        mut._pending_requests["ref_1"]["retry_attempts"] = 1

        # Simulate retry timer firing
        mut.timer_fired(botengine, {"type": "llm_retry", "reference": "ref_1"})

        # Should still have the pending request (re-attempted)
        assert "ref_1" in mut._pending_requests

    def test_timer_fired_non_dict_argument(self):
        """Timer with non-dict argument should be ignored."""
        botengine, organization, mut = self._setup()

        # Should not raise
        mut.timer_fired(botengine, "some_string_argument")
        mut.timer_fired(botengine, None)

    def test_timeout_max_retries_exceeded(self):
        """After MAX_RETRY_ATTEMPTS, request should be abandoned."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)
        logger = logging.getLogger(_MUT_LOGGER)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        # Set retry count to max - 1
        mut._pending_requests["ref_1"]["retry_attempts"] = MAX_RETRY_ATTEMPTS - 1

        # Trigger one more timeout
        with patch.object(logger, "error") as mock_error:
            mut._handle_request_timeout(botengine, "ref_1")
            mock_error.assert_called_once()

        # Should have been removed (given up)
        assert "ref_1" not in mut._pending_requests

    def test_timeout_incremental_retries(self):
        """Each timeout should increment retry_attempts."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        assert mut._pending_requests["ref_1"]["retry_attempts"] == 0

        mut._handle_request_timeout(botengine, "ref_1")
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 1

        mut._handle_request_timeout(botengine, "ref_1")
        assert mut._pending_requests["ref_1"]["retry_attempts"] == 2

    def test_timeout_nonexistent_reference(self):
        """Timeout for a reference that no longer exists should be a no-op."""
        botengine, organization, mut = self._setup()
        # Should not raise
        mut._handle_request_timeout(botengine, "nonexistent_ref")

    def test_retry_nonexistent_reference(self):
        """Retry for a reference that no longer exists should be a no-op."""
        botengine, organization, mut = self._setup()
        # Should not raise
        mut._handle_request_retry(botengine, "nonexistent_ref")

    # ===========================================================================
    # Request mapping
    # ===========================================================================

    def test_store_and_get_request_mapping(self):
        """Should store and retrieve request mappings."""
        botengine, organization, mut = self._setup()

        mut._store_request_mapping(botengine, "ref_1", "int_id_1", {"arg": 1})

        intelligence_id, argument = mut._get_request_mapping(botengine, "ref_1")
        assert intelligence_id == "int_id_1"
        assert argument == {"arg": 1}

    def test_get_request_mapping_not_found(self):
        """Missing mapping should return (None, None)."""
        botengine, organization, mut = self._setup()

        intelligence_id, argument = mut._get_request_mapping(botengine, "nonexistent")
        assert intelligence_id is None
        assert argument is None

    def test_request_mapping_auto_purge(self):
        """Mappings older than 30 minutes should be auto-purged when storing new ones."""
        botengine, organization, mut = self._setup()

        # Store an old mapping
        mut._store_request_mapping(botengine, "old_ref", "old_id", None)

        # Advance time by 31 minutes
        botengine.set_timestamp(botengine.get_timestamp() + 31 * 60 * 1000)

        # Store a new mapping (triggers purge)
        mut._store_request_mapping(botengine, "new_ref", "new_id", None)

        # Old mapping should be purged
        assert "old_ref" not in mut._llm_request_mappings
        # New mapping should exist
        assert "new_ref" in mut._llm_request_mappings

    def test_request_mapping_not_purged_within_window(self):
        """Mappings within 30 minutes should not be purged."""
        botengine, organization, mut = self._setup()

        mut._store_request_mapping(botengine, "recent_ref", "recent_id", None)

        # Advance time by 29 minutes (within window)
        botengine.set_timestamp(botengine.get_timestamp() + 29 * 60 * 1000)

        # Store another mapping
        mut._store_request_mapping(botengine, "new_ref", "new_id", None)

        # Recent mapping should still exist
        assert "recent_ref" in mut._llm_request_mappings

    def test_request_mapping_expiration_on_get(self):
        """Getting an expired mapping should return (None, None) and clean up."""
        botengine, organization, mut = self._setup()

        mut._store_request_mapping(botengine, "ref_1", "int_id_1", None)

        # Advance time by 31 minutes
        botengine.set_timestamp(botengine.get_timestamp() + 31 * 60 * 1000)

        intelligence_id, argument = mut._get_request_mapping(botengine, "ref_1")
        assert intelligence_id is None
        assert argument is None

        # Should have been cleaned up
        assert "ref_1" not in mut._llm_request_mappings

    # ===========================================================================
    # Make OpenAI request
    # ===========================================================================

    def test_make_openai_request_no_pending(self):
        """_make_openai_request with no pending request should be a no-op."""
        botengine, organization, mut = self._setup()
        logger = logging.getLogger(_MUT_LOGGER)

        with patch.object(logger, "error") as mock_error:
            mut._make_openai_request(botengine, "nonexistent_ref")
            mock_error.assert_called_once()

    def test_make_openai_request_sets_timeout_timer(self):
        """_make_openai_request should set a timeout timer."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        pending = mut._pending_requests["ref_1"]
        assert pending["timeout_timer_set"] is True

    # ===========================================================================
    # End-to-end flow
    # ===========================================================================

    def test_end_to_end_request_response(self):
        """Full flow: request -> OpenAI call -> response routed back."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        # 1. Send chat request
        request_content = self._make_chat_request_content(
            mock.intelligence_id,
            reference="e2e_ref",
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "What is 2+2?"},
            ],
            argument={"callback": "math"},
            temperature=0.0,
        )
        mut.llm_chat_request(botengine, request_content)

        assert "e2e_ref" in mut._pending_requests
        assert "e2e_ref" in mut._llm_request_mappings

        # 2. Simulate OpenAI response
        response = {
            "key": "e2e_ref",
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 25, "completion_tokens": 5, "total_tokens": 30},
            "cost_usd": 0.001,
            "choices": [{"message": {"role": "assistant", "content": "4"}}],
        }
        mut.openai(botengine, response)

        # 3. Verify response was routed
        assert mock.llm_response_count == 1
        assert mock.last_reference == "e2e_ref"
        assert mock.last_argument == {"callback": "math"}
        assert mock.last_response["choices"][0]["message"]["content"] == "4"
        assert mock.last_response["provider"] == "openai"

        # 4. Verify usage tracking
        assert mock.last_usage_provider == "openai"
        assert mock.last_usage_model == "gpt-4o-mini"
        assert mock.last_usage_cost == 0.001

        # 5. Verify cleanup
        assert "e2e_ref" not in mut._pending_requests

    def test_multiple_concurrent_requests(self):
        """Multiple requests with different references should be tracked independently."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        # Send two requests
        content_1 = self._make_chat_request_content(
            mock.intelligence_id,
            reference="req_1",
            messages=[{"role": "user", "content": "First"}],
            argument={"order": 1},
        )
        content_2 = self._make_chat_request_content(
            mock.intelligence_id,
            reference="req_2",
            messages=[{"role": "user", "content": "Second"}],
            argument={"order": 2},
        )
        mut.llm_chat_request(botengine, content_1)
        mut.llm_chat_request(botengine, content_2)

        assert "req_1" in mut._pending_requests
        assert "req_2" in mut._pending_requests

        # Respond to second request first
        response_2 = {
            "key": "req_2",
            "model": "gpt-4o-mini",
            "usage": {},
            "choices": [{"message": {"content": "Second response"}}],
        }
        mut.openai(botengine, response_2)

        assert mock.last_reference == "req_2"
        assert mock.last_argument == {"order": 2}
        assert "req_2" not in mut._pending_requests
        assert "req_1" in mut._pending_requests  # Still pending

        # Now respond to first
        response_1 = {
            "key": "req_1",
            "model": "gpt-4o-mini",
            "usage": {},
            "choices": [{"message": {"content": "First response"}}],
        }
        mut.openai(botengine, response_1)

        assert mock.llm_response_count == 2
        assert mock.last_reference == "req_1"
        assert "req_1" not in mut._pending_requests

    # ===========================================================================
    # Provider API tests
    # ===========================================================================

    def test_response_api_valid_request(self):
        """Response API request with 'input' should be accepted and stored."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_response_api_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        assert "ref_1" in mut._pending_requests
        assert "ref_1" in mut._llm_request_mappings
        pending = mut._pending_requests["ref_1"]
        assert pending["openai_params"]["input"] == "Hello"
        assert "messages" not in pending["openai_params"]

    def test_response_api_missing_input_rejected(self):
        """Response API request without 'input' should be rejected."""
        botengine, organization, mut = self._setup()

        content = {
            "intelligence_id": "some_id",
            "reference": "ref_1",
            "provider_api": PROVIDER_API_OPENAI_RESPONSE,
        }
        mut.llm_chat_request(botengine, content)

        assert len(mut._pending_requests) == 0
        assert len(mut._llm_request_mappings) == 0

    def test_chat_completion_missing_messages_rejected(self):
        """Chat Completion (default) request without 'messages' should be rejected."""
        botengine, organization, mut = self._setup()

        content = {
            "intelligence_id": "some_id",
            "reference": "ref_1",
            "provider_api": PROVIDER_API_OPENAI_CHAT_COMPLETION,
        }
        mut.llm_chat_request(botengine, content)

        assert len(mut._pending_requests) == 0
        assert len(mut._llm_request_mappings) == 0

    def test_openai_params_exclude_routing_fields(self):
        """Routing fields should be excluded from openai_params."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(
            mock.intelligence_id,
            argument={"task": "test"},
            provider_api=PROVIDER_API_OPENAI_CHAT_COMPLETION,
        )
        mut.llm_chat_request(botengine, content)

        params = mut._pending_requests["ref_1"]["openai_params"]
        assert "intelligence_id" not in params
        assert "reference" not in params
        assert "argument" not in params
        assert "provider_api" not in params

    def test_openai_params_include_metadata(self):
        """openai_params should include metadata with bundle_id and microservice name."""
        botengine, organization, mut = self._setup()
        mock = self._add_mock_microservice(botengine, organization)

        content = self._make_chat_request_content(mock.intelligence_id)
        mut.llm_chat_request(botengine, content)

        params = mut._pending_requests["ref_1"]["openai_params"]
        assert "metadata" in params
        assert "bundle_id" in params["metadata"]
        assert params["metadata"]["microservice"] == "MockRequestingMicroservice"
